"""
scanner.py
Recursively scans an MTP device for media files.
Runs in a QThread worker; emits progress signals.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Iterator, Set

from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".gif",
                    ".bmp", ".tiff", ".raw", ".dng", ".arw", ".cr2", ".nef"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".3gp", ".webm",
                    ".flv", ".wmv", ".m4v", ".ts", ".mpeg", ".mpg"}


@dataclass
class MediaFile:
    """Represents a media file found on the device."""
    object_id: str
    filename: str
    virtual_path: str          # full path on device e.g. "DCIM/Camera/IMG.jpg"
    size: int
    modified: Optional[datetime]
    created: Optional[datetime]
    is_photo: bool
    is_video: bool
    extension: str

    @property
    def is_whatsapp(self) -> bool:
        return "whatsapp" in self.virtual_path.lower()

    @property
    def is_screenshot(self) -> bool:
        p = self.virtual_path.lower()
        return "screenshot" in p or "screenshots" in p

    @property
    def is_download(self) -> bool:
        p = self.virtual_path.lower()
        return p.startswith("download") or "/download" in p


@dataclass
class ScanResult:
    photos: List[MediaFile] = field(default_factory=list)
    videos: List[MediaFile] = field(default_factory=list)
    total_size: int = 0
    scan_duration_s: float = 0.0
    errors: int = 0

    @property
    def all_files(self) -> List[MediaFile]:
        return self.photos + self.videos

    @property
    def photo_count(self) -> int:
        return len(self.photos)

    @property
    def video_count(self) -> int:
        return len(self.videos)

    @property
    def total_count(self) -> int:
        return len(self.photos) + len(self.videos)


class ScannerSignals(QObject):
    progress  = Signal(int, str)      # (files_found, current_path)
    finished  = Signal(object)        # ScanResult
    error     = Signal(str)


class Scanner:
    """
    Media file scanner for MTP devices.
    Can be called directly or via ScanWorker for background use.
    """

    def __init__(self):
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def scan(
        self,
        wpd_device,
        progress_cb=None,
    ) -> ScanResult:
        """
        Recursively scan the device for media files.
        progress_cb(count, current_path) called periodically.
        """
        import time
        self._cancelled = False
        settings = get_settings()
        allowed_ext = settings.allowed_extensions()
        excluded = set(settings.excluded_folders)
        min_size = settings.min_file_size_bytes
        max_size = settings.max_file_size_bytes

        result = ScanResult()
        start = time.time()
        count = 0

        try:
            for obj in wpd_device.walk(excluded_paths=excluded):
                if self._cancelled:
                    break
                ext = _get_ext(obj.name)
                if ext not in allowed_ext:
                    continue

                # Size filters
                if min_size > 0 and obj.size < min_size:
                    continue
                if max_size > 0 and obj.size > max_size:
                    continue

                is_photo = ext in IMAGE_EXTENSIONS
                is_video = ext in VIDEO_EXTENSIONS

                mf = MediaFile(
                    object_id=obj.object_id,
                    filename=obj.name,
                    virtual_path=obj.virtual_path,
                    size=obj.size,
                    modified=obj.modified,
                    created=obj.created,
                    is_photo=is_photo,
                    is_video=is_video,
                    extension=ext,
                )

                # Apply filters
                if not settings.include_whatsapp and mf.is_whatsapp:
                    continue
                if not settings.include_downloads and mf.is_download:
                    continue

                if is_photo:
                    result.photos.append(mf)
                elif is_video:
                    result.videos.append(mf)

                result.total_size += obj.size
                count += 1
                if progress_cb and count % 10 == 0:
                    progress_cb(count, obj.virtual_path)

        except Exception as e:
            logger.error(f"Scan error: {e}", exc_info=True)
            result.errors += 1

        result.scan_duration_s = time.time() - start
        logger.info(
            f"Scan complete: {result.photo_count} photos, {result.video_count} videos, "
            f"{result.total_size / (1024**3):.2f} GB in {result.scan_duration_s:.1f}s"
        )
        return result


class ScanWorker(QRunnable):
    """QRunnable that runs Scanner in a thread pool."""

    def __init__(self, wpd_device, signals: ScannerSignals):
        super().__init__()
        self._device = wpd_device
        self.signals = signals
        self._scanner = Scanner()

    def run(self):
        try:
            result = self._scanner.scan(
                self._device,
                progress_cb=lambda n, p: self.signals.progress.emit(n, p),
            )
            self.signals.finished.emit(result)
        except Exception as e:
            logger.error(f"ScanWorker error: {e}", exc_info=True)
            self.signals.error.emit(str(e))

    def cancel(self):
        self._scanner.cancel()


def _get_ext(filename: str) -> str:
    idx = filename.rfind(".")
    if idx == -1:
        return ""
    return filename[idx:].lower()
