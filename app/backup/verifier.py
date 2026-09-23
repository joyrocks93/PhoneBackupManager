"""
verifier.py
Post-copy SHA-256 verification of transferred files.
"""

import hashlib
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

CHUNK = 4 * 1024 * 1024


def hash_file(path: str) -> Optional[str]:
    """Compute SHA-256 of a local PC file."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(CHUNK):
                h.update(chunk)
        return h.hexdigest()
    except OSError as e:
        logger.error(f"hash_file error {path}: {e}")
        return None


def verify_copy(source_hash: str, dest_path: str) -> bool:
    """
    Verify that dest_path has the same content as a file whose
    hash we already computed during the copy.
    """
    dest_hash = hash_file(dest_path)
    if dest_hash is None:
        return False
    match = (dest_hash.lower() == source_hash.lower())
    if not match:
        logger.warning(
            f"Hash mismatch!\n  source: {source_hash}\n  dest:   {dest_hash}\n  path:   {dest_path}"
        )
    return match
