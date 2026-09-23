"""
backup_manager.py
Orchestrates a complete backup session.
State machine: IDLE → SCANNING → READY → BACKING_UP → PAUSED → DONE/CANCELLED/FAILED

Runs in a QThread; emits Qt signals for UI updates.
"""

import logging
import os
import shutil
import threading
import time
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Optional, List

from PySide6.QtCore import QThread, Signal

from app.backup.scanner import Scanner, ScanResult, MediaFile
from app.backup.duplicate_detector import DuplicateDetector
from app.backup.transfer_manager import transfer_file
from app.backup.verifier import verify_copy
from app.database.database import get_db
from app.config.settings import get_settings
from app.device.device_manager import PhoneDevice

logger = logging.getLogger(__name__)


class BackupState(Enum):
    IDLE        = auto()
    SCANNING    = auto()
    READY       = auto()
    BACKING_UP  = auto()
    PAUSED      = auto()
    DONE        = auto()
    CANCELLED   = auto()
    FAILED      = auto()


class BackupSignals:
    """Container – BackupWorker inherits from QThread which has its own signal mechanism."""
    pass


class BackupWorker(QThread):
    """
    Runs the full backup session in a background thread.
    Emits fine-grained signals for the progress UI.
    """

    # Scan phase
    scan_started    = Signal()
    scan_progress   = Signal(int, str)          # (count, current_path)
    scan_finished   = Signal(object)            # ScanResult

    # Backup phase
    backup_started  = Signal(int, int)          # (total_files, total_bytes)
    file_started    = Signal(str, int, int)     # (filename, file_num, total_files)
    file_progress   = Signal(int, int)          # (bytes_written, file_total_bytes)
    file_done       = Signal(str, bool, bool)   # (filename, copied, skipped)
    backup_progress = Signal(int, int, int, int, float)  # (copied, skipped, failed, bytes, speed_bps)
    backup_finished = Signal(object)            # BackupSummary
    error           = Signal(str)
    status_changed  = Signal(str)               # human-readable status message

    def __init__(
        self,
        phone: PhoneDevice,
        wpd_device,
        backup_folder: str,
        org_mode: str = "preserve",
        parent=None,
    ):
        super().__init__(parent)
        self._phone     = phone
        self._wpd       = wpd_device
        self._dest_root = backup_folder
        self._org_mode  = org_mode
        self._state     = BackupState.IDLE
        self._pause_event = threading.Event()
        self._pause_event.set()   # not paused initially
        self._cancel_flag = False
        self._scan_result: Optional[ScanResult] = None
        self._session_id: Optional[int] = None

    # ── Control ──────────────────────────────────────────────────────────────

    def pause(self):
        self._pause_event.clear()
        self._state = BackupState.PAUSED
        self.status_changed.emit("Backup paused.")
        logger.info("Backup paused.")

    def resume(self):
        self._pause_event.set()
        self._state = BackupState.BACKING_UP
        self.status_changed.emit("Backup resumed.")
        logger.info("Backup resumed.")

    def cancel(self):
        self._cancel_flag = True
        self._pause_event.set()   # unblock if paused
        self.status_changed.emit("Cancelling backup…")
        logger.info("Backup cancel requested.")

    def _check_cancel(self) -> bool:
        return self._cancel_flag

    def _wait_if_paused(self):
        self._pause_event.wait()

    # ── QThread.run ──────────────────────────────────────────────────────────

    def run(self):
        settings = get_settings()
        db = get_db()

        # ── 1. Scan ──────────────────────────────────────────────────────────
        self._state = BackupState.SCANNING
        self.scan_started.emit()
        self.status_changed.emit("Scanning device for media files…")

        scanner = Scanner()
        try:
            result = scanner.scan(
                self._wpd,
                progress_cb=lambda n, p: self.scan_progress.emit(n, p),
            )
        except Exception as e:
            logger.error(f"Scan failed: {e}", exc_info=True)
            self.error.emit(f"Scan failed: {e}")
            self._state = BackupState.FAILED
            return

        if self._cancel_flag:
            self._state = BackupState.CANCELLED
            return

        self._scan_result = result
        self.scan_finished.emit(result)

        if result.total_count == 0:
            self.status_changed.emit("No media files found.")
            self._state = BackupState.DONE
            return

        # ── 2. Storage check ─────────────────────────────────────────────────
        required = result.total_size
        try:
            free = shutil.disk_usage(self._dest_root).free
            if free < required * 1.05:  # 5% safety margin
                msg = (
                    f"Not enough storage!\n"
                    f"Required: {_fmt_size(required)}\n"
                    f"Available: {_fmt_size(free)}"
                )
                self.error.emit(msg)
                self._state = BackupState.FAILED
                return
        except Exception as e:
            logger.warning(f"Disk check failed: {e}")

        # ── 3. Create DB session ──────────────────────────────────────────────
        self._session_id = db.create_session(
            device_id=self._phone.pnp_id,
            device_name=self._phone.name,
            backup_folder=self._dest_root,
            org_mode=self._org_mode,
        )
        db.update_session(self._session_id, total_files=result.total_count,
                          total_bytes=result.total_size)

        # ── 4. Backup ─────────────────────────────────────────────────────────
        self._state = BackupState.BACKING_UP
        self.backup_started.emit(result.total_count, result.total_size)
        self.status_changed.emit("Starting backup…")

        detector = DuplicateDetector(
            device_id=self._phone.pnp_id,
            use_hashing=settings.hash_verification,
        )

        total_files = result.total_count
        copied = skipped = failed = 0
        bytes_copied = 0
        speed_bytes: List[float] = []
        speed_window = 5.0  # seconds

        all_files = result.all_files
        file_num = 0

        for mf in all_files:
            if self._cancel_flag:
                break
            self._wait_if_paused()
            if self._cancel_flag:
                break

            file_num += 1
            self.file_started.emit(mf.filename, file_num, total_files)

            # Resolve destination path
            dest_path = self._resolve_dest(mf)

            # Duplicate check
            action, effective_dest = detector.check(
                source_path=mf.virtual_path,
                dest_path=dest_path,
                file_size=mf.size,
                modified_date=mf.modified.isoformat() if mf.modified else None,
            )

            if action == "skip":
                skipped += 1
                db.record_file(
                    session_id=self._session_id,
                    device_id=self._phone.pnp_id,
                    source_path=mf.virtual_path,
                    dest_path=dest_path,
                    filename=mf.filename,
                    file_size=mf.size,
                    modified_date=mf.modified.isoformat() if mf.modified else None,
                    status="skipped",
                )
                db.increment_session_counters(self._session_id, skipped=1)
                self.file_done.emit(mf.filename, False, True)
                self.backup_progress.emit(copied, skipped, failed, bytes_copied, 0.0)
                continue

            actual_dest = effective_dest or dest_path
            os.makedirs(os.path.dirname(actual_dest), exist_ok=True)

            # Transfer
            t0 = time.monotonic()
            tr = transfer_file(
                wpd_device=self._wpd,
                object_id=mf.object_id,
                dest_path=actual_dest,
                file_size=mf.size,
                modified=mf.modified,
                compute_hash=settings.hash_verification,
                progress_cb=lambda bw, bt: self.file_progress.emit(bw, bt),
                cancel_check=self._check_cancel,
            )
            elapsed = time.monotonic() - t0

            if tr.success:
                # Optional post-copy verification
                verified = True
                if settings.hash_verification and tr.sha256_hash:
                    verified = verify_copy(tr.sha256_hash, actual_dest)
                    if not verified:
                        logger.warning(f"Verification failed: {mf.filename}")

                copied += 1
                bytes_copied += tr.bytes_written
                db.record_file(
                    session_id=self._session_id,
                    device_id=self._phone.pnp_id,
                    source_path=mf.virtual_path,
                    dest_path=actual_dest,
                    filename=mf.filename,
                    file_size=mf.size,
                    modified_date=mf.modified.isoformat() if mf.modified else None,
                    status="copied",
                    sha256_hash=tr.sha256_hash,
                )
                db.increment_session_counters(
                    self._session_id, copied=1,
                    bytes_copied=tr.bytes_written
                )
                speed = tr.speed_bps
                self.file_done.emit(mf.filename, True, False)
            else:
                failed += 1
                logger.error(f"Failed to copy {mf.filename}: {tr.error}")
                db.record_file(
                    session_id=self._session_id,
                    device_id=self._phone.pnp_id,
                    source_path=mf.virtual_path,
                    dest_path=actual_dest,
                    filename=mf.filename,
                    file_size=mf.size,
                    modified_date=mf.modified.isoformat() if mf.modified else None,
                    status="failed",
                )
                db.increment_session_counters(self._session_id, failed=1)
                self.file_done.emit(mf.filename, False, False)
                speed = 0.0

            self.backup_progress.emit(copied, skipped, failed, bytes_copied, speed)

        # ── 5. Finish ─────────────────────────────────────────────────────────
        if self._cancel_flag:
            self._state = BackupState.CANCELLED
            db.finish_session(self._session_id, "cancelled")
            self.status_changed.emit("Backup cancelled.")
        else:
            self._state = BackupState.DONE
            db.finish_session(self._session_id, "completed")
            self.status_changed.emit("Backup complete!")

        summary = {
            "session_id": self._session_id,
            "total":    total_files,
            "copied":   copied,
            "skipped":  skipped,
            "failed":   failed,
            "bytes":    bytes_copied,
            "state":    self._state.name,
        }
        self.backup_finished.emit(summary)
        logger.info(f"Backup finished: {summary}")

    # ── Path resolver ─────────────────────────────────────────────────────────

    def _resolve_dest(self, mf: MediaFile) -> str:
        if self._org_mode == "by_date":
            return self._dest_by_date(mf)
        return self._dest_preserve(mf)

    def _dest_preserve(self, mf: MediaFile) -> str:
        """Mirror device folder structure under backup root."""
        # virtual_path is e.g. "DCIM/Camera/IMG_001.jpg"
        safe = mf.virtual_path.replace("/", os.sep).replace("\\", os.sep)
        return os.path.join(self._dest_root, safe)

    def _dest_by_date(self, mf: MediaFile) -> str:
        """Organize as YYYY/MM/Photos/ or YYYY/MM/Videos/"""
        dt = mf.modified or mf.created or datetime.now()
        year  = dt.strftime("%Y")
        month = dt.strftime("%m")
        kind  = "Photos" if mf.is_photo else "Videos"
        return os.path.join(self._dest_root, year, month, kind, mf.filename)


def _fmt_size(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"
