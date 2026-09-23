"""
backup_view.py
Live backup progress page with pause/resume/cancel controls.
"""

import os
import time
import logging
from typing import Optional
from collections import deque

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QProgressBar, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont

from app.device.device_manager import PhoneDevice
from app.config.settings import get_settings
from app.backup.backup_manager import BackupWorker

logger = logging.getLogger(__name__)


def _fmt_size(b: int) -> str:
    if b < 0:
        b = 0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def _fmt_speed(bps: float) -> str:
    if bps <= 0:
        return "—"
    mbps = bps / (1024 * 1024)
    return f"{mbps:.1f} MB/s"


def _fmt_eta(seconds: float) -> str:
    if seconds <= 0 or seconds > 86400 * 7:
        return "—"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s   = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def _make_sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFrameShadow(QFrame.Shadow.Sunken)
    return f


class BackupPage(QWidget):

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main_window = main_window
        self._phone: Optional[PhoneDevice] = None
        self._worker: Optional[BackupWorker] = None
        self._wpd_device = None
        self._paused = False

        # Speed tracking
        self._speed_samples: deque = deque(maxlen=10)
        self._last_bytes = 0
        self._last_time  = 0.0
        self._total_bytes = 0
        self._bytes_copied = 0

        self._build_ui()
        self._show_idle()

    def _build_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Backup")
        title.setObjectName("section_title")
        hdr.addWidget(title)
        hdr.addStretch()
        layout.addLayout(hdr)

        # ── Status card ────────────────────────────────────────────────────
        status_card = QFrame()
        status_card.setObjectName("card")
        sc_layout = QVBoxLayout(status_card)
        sc_layout.setSpacing(16)

        # Phase label
        self._phase_lbl = QLabel("Ready to backup")
        self._phase_lbl.setObjectName("section_title")
        self._phase_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        sc_layout.addWidget(self._phase_lbl)

        # Current file
        self._current_file_lbl = QLabel("—")
        self._current_file_lbl.setObjectName("file_label")
        self._current_file_lbl.setWordWrap(True)
        sc_layout.addWidget(self._current_file_lbl)

        # File counter
        self._file_counter_lbl = QLabel("")
        self._file_counter_lbl.setObjectName("meta_label")
        sc_layout.addWidget(self._file_counter_lbl)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(12)
        sc_layout.addWidget(self._progress_bar)

        self._pct_lbl = QLabel("0%")
        self._pct_lbl.setObjectName("accent_label")
        sc_layout.addWidget(self._pct_lbl)

        # File progress bar (individual file)
        self._file_progress_bar = QProgressBar()
        self._file_progress_bar.setRange(0, 100)
        self._file_progress_bar.setValue(0)
        self._file_progress_bar.setTextVisible(False)
        self._file_progress_bar.setFixedHeight(6)
        sc_layout.addWidget(self._file_progress_bar)

        sc_layout.addWidget(_make_sep())

        # Stats grid
        stats = QHBoxLayout()
        stats.setSpacing(32)

        def stat_col(label: str, attr: str) -> QVBoxLayout:
            col = QVBoxLayout()
            col.setSpacing(2)
            val = QLabel("—")
            val.setObjectName("stat_value")
            val.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
            lbl_w = QLabel(label.upper())
            lbl_w.setObjectName("stat_label")
            col.addWidget(val)
            col.addWidget(lbl_w)
            setattr(self, attr, val)
            return col

        stats.addLayout(stat_col("Copied", "_stat_copied"))
        stats.addLayout(stat_col("Skipped", "_stat_skipped"))
        stats.addLayout(stat_col("Failed", "_stat_failed"))
        stats.addLayout(stat_col("Size", "_stat_size"))
        stats.addLayout(stat_col("Speed", "_stat_speed"))
        stats.addLayout(stat_col("ETA", "_stat_eta"))
        stats.addStretch()
        sc_layout.addLayout(stats)

        layout.addWidget(status_card)

        # ── Controls ───────────────────────────────────────────────────────
        ctrl_row = QHBoxLayout()

        self._start_btn = QPushButton("▶  START BACKUP")
        self._start_btn.setObjectName("primary_btn")
        self._start_btn.setMinimumWidth(180)
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.clicked.connect(self._on_start)

        self._pause_btn = QPushButton("⏸  Pause")
        self._pause_btn.setObjectName("secondary_btn")
        self._pause_btn.setMinimumWidth(110)
        self._pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pause_btn.clicked.connect(self._on_pause_resume)
        self._pause_btn.setVisible(False)

        self._cancel_btn = QPushButton("✕  Cancel")
        self._cancel_btn.setObjectName("danger_btn")
        self._cancel_btn.setMinimumWidth(110)
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self._on_cancel)
        self._cancel_btn.setVisible(False)

        ctrl_row.addStretch()
        ctrl_row.addWidget(self._start_btn)
        ctrl_row.addWidget(self._pause_btn)
        ctrl_row.addWidget(self._cancel_btn)
        layout.addLayout(ctrl_row)

        # ── Log area ───────────────────────────────────────────────────────
        log_card = QFrame()
        log_card.setObjectName("card")
        log_layout = QVBoxLayout(log_card)

        log_title = QLabel("Activity Log")
        log_title.setObjectName("file_label")
        log_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        log_layout.addWidget(log_title)

        self._log_scroll = QScrollArea()
        self._log_scroll.setWidgetResizable(True)
        self._log_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._log_scroll.setMaximumHeight(200)

        log_inner = QWidget()
        self._log_layout = QVBoxLayout(log_inner)
        self._log_layout.setContentsMargins(0, 0, 0, 0)
        self._log_layout.setSpacing(2)
        self._log_layout.addStretch()
        self._log_scroll.setWidget(log_inner)
        log_layout.addWidget(self._log_scroll)
        layout.addWidget(log_card)

        layout.addStretch()

        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ── State helpers ──────────────────────────────────────────────────────

    def _show_idle(self):
        self._phase_lbl.setText("Ready to Backup")
        self._current_file_lbl.setText("Select a device on the Dashboard and click Start Backup.")
        self._file_counter_lbl.setText("")
        self._progress_bar.setValue(0)
        self._file_progress_bar.setValue(0)
        self._pct_lbl.setText("0%")
        self._start_btn.setVisible(True)
        self._pause_btn.setVisible(False)
        self._cancel_btn.setVisible(False)
        self._reset_stats()

    def _reset_stats(self):
        for attr in ("_stat_copied", "_stat_skipped", "_stat_failed",
                     "_stat_size", "_stat_speed", "_stat_eta"):
            getattr(self, attr).setText("—")

    def _add_log(self, text: str, color: str = "#94A3B8"):
        from PySide6.QtWidgets import QLabel as QL
        lbl = QL(text)
        lbl.setStyleSheet(f"color: {color}; font-size: 11px; padding: 1px 0;")
        lbl.setWordWrap(True)
        # Insert before the stretch
        count = self._log_layout.count()
        self._log_layout.insertWidget(count - 1, lbl)
        # Auto-scroll
        QTimer.singleShot(50, lambda: self._log_scroll.verticalScrollBar().setValue(
            self._log_scroll.verticalScrollBar().maximum()
        ))
        # Limit log entries
        if self._log_layout.count() > 202:
            item = self._log_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    # ── Prepare ────────────────────────────────────────────────────────────

    def prepare(self, phone: PhoneDevice, scan_result=None):
        self._phone = phone
        self._scan_result = scan_result
        if scan_result:
            self._phase_lbl.setText(f"Ready — {scan_result.total_count:,} files ({_fmt_size(scan_result.total_size)})")
        else:
            self._phase_lbl.setText(f"Ready — {phone.display_name}")
        self._start_btn.setEnabled(True)
        self._start_btn.setVisible(True)

    # ── Controls ───────────────────────────────────────────────────────────

    def _on_start(self):
        phone = self._phone or self._main_window.get_current_phone()
        if not phone:
            self._add_log("No phone connected.", "#EF4444")
            return

        settings = get_settings()
        dest = settings.backup_folder
        if not dest:
            self._add_log("No backup folder selected. Set one in Settings.", "#F59E0B")
            return

        # Open WPD device
        try:
            from app.device.device_manager import get_device_manager
            dm = get_device_manager()
            self._wpd_device = dm.open_device(phone)
            self._wpd_device.open()
        except Exception as e:
            self._add_log(f"Cannot connect to device: {e}", "#EF4444")
            logger.error(f"Device open failed: {e}")
            return

        # Start worker
        self._worker = BackupWorker(
            phone=phone,
            wpd_device=self._wpd_device,
            backup_folder=dest,
            org_mode=settings.org_mode,
            parent=self,
        )
        self._connect_worker(self._worker)
        self._worker.start()

        self._start_btn.setVisible(False)
        self._pause_btn.setVisible(True)
        self._cancel_btn.setVisible(True)
        self._paused = False
        self._total_files = 0
        self._bytes_copied = 0
        self._total_bytes  = 0
        self._last_bytes   = 0
        self._last_time    = time.monotonic()
        self._speed_samples.clear()

    def _connect_worker(self, w: BackupWorker):
        w.scan_started.connect(lambda: self._phase_lbl.setText("🔍  Scanning…"))
        w.scan_progress.connect(lambda n, p: self._current_file_lbl.setText(f"Scanning: {p}"))
        w.scan_finished.connect(self._on_scan_finished)
        w.backup_started.connect(self._on_backup_started)
        w.file_started.connect(self._on_file_started)
        w.file_progress.connect(self._on_file_progress)
        w.file_done.connect(self._on_file_done)
        w.backup_progress.connect(self._on_backup_progress)
        w.backup_finished.connect(self._on_backup_finished)
        w.error.connect(lambda msg: self._add_log(f"ERROR: {msg}", "#EF4444"))
        w.status_changed.connect(lambda s: self._add_log(s))

    def _on_scan_finished(self, result):
        if result:
            self._add_log(
                f"Scan complete: {result.photo_count:,} photos, {result.video_count:,} videos "
                f"({_fmt_size(result.total_size)})", "#22C55E"
            )

    def _on_backup_started(self, total_files: int, total_bytes: int):
        self._total_files = total_files
        self._total_bytes = total_bytes
        self._phase_lbl.setText("💾  Backing up…")
        self._add_log(f"Starting backup of {total_files:,} files…", "#3B82F6")

    def _on_file_started(self, filename: str, file_num: int, total: int):
        self._current_file_lbl.setText(filename)
        self._file_counter_lbl.setText(f"{file_num:,} / {total:,} files")
        if total > 0:
            pct = int(file_num / total * 100)
            self._progress_bar.setValue(pct)
            self._pct_lbl.setText(f"{pct}%")
        self._file_progress_bar.setValue(0)

    def _on_file_progress(self, bw: int, file_total: int):
        if file_total > 0:
            pct = min(100, int(bw / file_total * 100))
            self._file_progress_bar.setValue(pct)

    def _on_file_done(self, filename: str, copied: bool, skipped: bool):
        if copied:
            self._add_log(f"✓ {filename}", "#22C55E")
        elif skipped:
            self._add_log(f"→ Skipped: {filename}", "#94A3B8")
        else:
            self._add_log(f"✗ Failed: {filename}", "#EF4444")

    def _on_backup_progress(self, copied: int, skipped: int, failed: int, bytes_cop: int, speed: float):
        # Update stats
        self._stat_copied.setText(f"{copied:,}")
        self._stat_skipped.setText(f"{skipped:,}")
        self._stat_failed.setText(str(failed) if failed else "—")
        self._stat_size.setText(_fmt_size(bytes_cop))

        # Speed (rolling average)
        now = time.monotonic()
        dt  = now - self._last_time
        if dt > 0:
            instant = (bytes_cop - self._last_bytes) / dt
            self._speed_samples.append(instant)
            avg_speed = sum(self._speed_samples) / len(self._speed_samples)
            self._stat_speed.setText(_fmt_speed(avg_speed))
            # ETA
            if avg_speed > 0 and self._total_bytes > 0:
                remaining = (self._total_bytes - bytes_cop) / avg_speed
                self._stat_eta.setText(_fmt_eta(remaining))
        self._last_bytes = bytes_cop
        self._last_time  = now

    def _on_backup_finished(self, summary: dict):
        state = summary.get("state", "DONE")
        copied  = summary.get("copied", 0)
        skipped = summary.get("skipped", 0)
        failed  = summary.get("failed", 0)
        bytes_c = summary.get("bytes", 0)

        if state == "DONE":
            self._phase_lbl.setText("✅  Backup Complete!")
            self._progress_bar.setValue(100)
            self._pct_lbl.setText("100%")
            self._add_log(
                f"Backup finished: {copied:,} copied, {skipped:,} skipped, {failed} failed. "
                f"{_fmt_size(bytes_c)} transferred.", "#22C55E"
            )
        elif state == "CANCELLED":
            self._phase_lbl.setText("⚠️  Backup Cancelled")
            self._add_log("Backup was cancelled.", "#F59E0B")
        else:
            self._phase_lbl.setText("❌  Backup Failed")
            self._add_log("Backup failed.", "#EF4444")

        # Clean up WPD
        if self._wpd_device:
            try:
                self._wpd_device.close()
            except Exception:
                pass
            self._wpd_device = None

        self._start_btn.setVisible(True)
        self._start_btn.setText("▶  BACKUP AGAIN")
        self._pause_btn.setVisible(False)
        self._cancel_btn.setVisible(False)

    def _on_pause_resume(self):
        if not self._worker:
            return
        if self._paused:
            self._worker.resume()
            self._pause_btn.setText("⏸  Pause")
            self._paused = False
        else:
            self._worker.pause()
            self._pause_btn.setText("▶  Resume")
            self._paused = True

    def _on_cancel(self):
        if self._worker:
            self._worker.cancel()
