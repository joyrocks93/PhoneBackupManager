"""
duplicate_detector.py
Multi-strategy duplicate detection for backup files.

Strategy (in order):
  1. Check if destination path exists and sizes match
  2. If sizes match, compare modification dates
  3. If dates differ, compute SHA-256 hash of source stream
  4. If hash matches existing DB record → skip
  5. If filename collision but different content → rename with suffix
"""

import hashlib
import os
import logging
from typing import Optional, Tuple

from app.database.database import get_db

logger = logging.getLogger(__name__)

HASH_CHUNK = 4 * 1024 * 1024  # 4 MB


class DuplicateDetector:

    def __init__(self, device_id: str, use_hashing: bool = False):
        self._device_id = device_id
        self._use_hashing = use_hashing
        self._db = get_db()

    # ── Main entry point ──────────────────────────────────────────────────

    def check(
        self,
        source_path: str,     # virtual path on device
        dest_path: str,       # full path on PC
        file_size: int,
        modified_date: Optional[str],
        source_hash_fn=None,  # callable() → str (expensive, only called if needed)
    ) -> Tuple[str, Optional[str]]:
        """
        Returns:
          ("skip", None)        - file already backed up, identical
          ("copy", dest_path)   - file should be copied to dest_path
          ("rename", new_path)  - same name, different content → use new_path
        """
        # 1. Check database first (fastest)
        if self._db.is_file_backed_up(self._device_id, source_path, file_size):
            logger.debug(f"DB hit (skip): {source_path}")
            return ("skip", None)

        # 2. Check if destination file exists on disk
        if not os.path.exists(dest_path):
            return ("copy", dest_path)

        dest_size = os.path.getsize(dest_path)

        # 3. Different size → definitely not same file (use same path = overwrite forbidden)
        if dest_size != file_size:
            new_path = self._make_unique_path(dest_path)
            return ("rename", new_path)

        # 4. Same size — check date if available
        if modified_date:
            dest_mtime = os.path.getmtime(dest_path)
            import datetime
            try:
                src_dt = datetime.datetime.fromisoformat(modified_date)
                dest_dt = datetime.datetime.fromtimestamp(dest_mtime)
                # If dates match within 2 seconds → skip
                if abs((src_dt - dest_dt).total_seconds()) < 2:
                    logger.debug(f"Date match (skip): {source_path}")
                    return ("skip", None)
            except Exception:
                pass

        # 5. Same size, date mismatch/unknown — hash if enabled
        if self._use_hashing and source_hash_fn:
            src_hash = source_hash_fn()
            if src_hash:
                dest_hash = _hash_file(dest_path)
                if src_hash == dest_hash:
                    logger.debug(f"Hash match (skip): {source_path}")
                    return ("skip", None)
                else:
                    new_path = self._make_unique_path(dest_path)
                    logger.debug(f"Hash mismatch (rename): {source_path} → {new_path}")
                    return ("rename", new_path)

        # 6. Fallback: same size, can't confirm — skip conservatively
        logger.debug(f"Size match, no hash (skip): {source_path}")
        return ("skip", None)

    def _make_unique_path(self, dest_path: str) -> str:
        """Generate IMG_1234_1.jpg, IMG_1234_2.jpg ... until unique."""
        base, ext = os.path.splitext(dest_path)
        counter = 1
        while True:
            candidate = f"{base}_{counter}{ext}"
            if not os.path.exists(candidate):
                return candidate
            counter += 1
            if counter > 9999:
                import uuid
                return f"{base}_{uuid.uuid4().hex[:8]}{ext}"


def _hash_file(path: str) -> Optional[str]:
    """Compute SHA-256 of an existing PC file."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(HASH_CHUNK):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def hash_stream(stream, chunk_size: int = HASH_CHUNK) -> str:
    """
    Compute SHA-256 of data read from a stream-like object.
    The stream must support read(n) → bytes.
    """
    h = hashlib.sha256()
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        h.update(chunk)
    return h.hexdigest()
