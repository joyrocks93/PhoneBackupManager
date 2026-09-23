"""
settings.py
Persistent application settings backed by a JSON file.
"""

import json
import os
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_BACKUP_FOLDER = str(Path.home() / "Pictures" / "PhoneBackup")

DEFAULTS: dict[str, Any] = {
    "backup_folder": _DEFAULT_BACKUP_FOLDER,
    "org_mode": "preserve",          # "preserve" | "by_date"
    "include_photos": True,
    "include_videos": True,
    "include_whatsapp": True,
    "include_downloads": False,
    "include_screenshots": True,
    "auto_backup": False,
    "auto_backup_confirm": True,     # ask before starting auto backup
    "duplicate_detection": True,
    "hash_verification": False,      # verify after copy
    "theme": "dark",                 # "dark" | "light"
    "max_concurrent_transfers": 1,
    "min_file_size_kb": 0,
    "max_file_size_mb": 0,           # 0 = no limit
    "excluded_folders": [
        "Android/data",
        "Android/obb",
    ],
    "first_run": True,
    "window_width": 1100,
    "window_height": 720,
}

_CONFIG_DIR = Path.home() / ".phone_backup_manager"
_CONFIG_FILE = _CONFIG_DIR / "settings.json"


class Settings:
    """Thread-safe persistent settings store."""

    def __init__(self):
        self._data: dict[str, Any] = dict(DEFAULTS)
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self):
        try:
            _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            if _CONFIG_FILE.exists():
                with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                # Merge: stored values override defaults, new keys from defaults are added
                for k, v in DEFAULTS.items():
                    self._data[k] = stored.get(k, v)
                # Keep any extra stored keys too
                for k, v in stored.items():
                    if k not in self._data:
                        self._data[k] = v
        except Exception as e:
            logger.warning(f"Could not load settings: {e}. Using defaults.")
            self._data = dict(DEFAULTS)

    def save(self):
        try:
            _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save settings: {e}")

    # ── Accessors ─────────────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        self._data[key] = value

    def set_many(self, updates: dict[str, Any]):
        self._data.update(updates)

    # ── Convenience properties ─────────────────────────────────────────────

    @property
    def backup_folder(self) -> str:
        return self._data["backup_folder"]

    @backup_folder.setter
    def backup_folder(self, v: str):
        self._data["backup_folder"] = v

    @property
    def org_mode(self) -> str:
        return self._data["org_mode"]

    @property
    def include_photos(self) -> bool:
        return self._data["include_photos"]

    @property
    def include_videos(self) -> bool:
        return self._data["include_videos"]

    @property
    def include_whatsapp(self) -> bool:
        return self._data["include_whatsapp"]

    @property
    def include_downloads(self) -> bool:
        return self._data["include_downloads"]

    @property
    def auto_backup(self) -> bool:
        return self._data["auto_backup"]

    @property
    def duplicate_detection(self) -> bool:
        return self._data["duplicate_detection"]

    @property
    def hash_verification(self) -> bool:
        return self._data["hash_verification"]

    @property
    def theme(self) -> str:
        return self._data["theme"]

    @property
    def excluded_folders(self) -> list:
        return self._data.get("excluded_folders", [])

    @property
    def min_file_size_bytes(self) -> int:
        return self._data.get("min_file_size_kb", 0) * 1024

    @property
    def max_file_size_bytes(self) -> int:
        mb = self._data.get("max_file_size_mb", 0)
        return mb * 1024 * 1024 if mb > 0 else 0

    # ── Media extension lists ─────────────────────────────────────────────

    PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".gif", ".bmp", ".tiff", ".raw", ".dng"}
    VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".3gp", ".webm", ".flv", ".wmv", ".m4v", ".ts"}

    def allowed_extensions(self) -> set[str]:
        exts: set[str] = set()
        if self.include_photos:
            exts |= self.PHOTO_EXTENSIONS
        if self.include_videos:
            exts |= self.VIDEO_EXTENSIONS
        return exts


# Module-level singleton
_instance: Settings | None = None


def get_settings() -> Settings:
    global _instance
    if _instance is None:
        _instance = Settings()
    return _instance
