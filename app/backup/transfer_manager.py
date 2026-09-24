"""
transfer_manager.py
Handles streaming file transfer from MTP device → PC with:
  - Streaming in chunks (memory efficient for large files)
  - SHA-256 hash computation during copy (optional)
  - mtime preservation
  - Progress callbacks
"""

import ctypes
import hashlib
import logging
import os
import time
from typing import Optional, Callable

logger = logging.getLogger(__name__)

CHUNK_SIZE = 64 * 1024 * 1024   # 64 MB


class TransferResult:
    def __init__(self):
        self.success = False
        self.bytes_written = 0
        self.sha256_hash: Optional[str] = None
        self.error: Optional[str] = None
        self.duration_s: float = 0.0

    @property
    def speed_bps(self) -> float:
        if self.duration_s <= 0:
            return 0.0
        return self.bytes_written / self.duration_s


def transfer_file(
    wpd_device,
    object_id: str,
    dest_path: str,
    file_size: int,
    modified: Optional[object] = None,   # datetime or None
    compute_hash: bool = False,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    chunk_config: Optional[dict] = None,
) -> TransferResult:
    """
    Copy a single file from the MTP device to dest_path.

    progress_cb(bytes_written, total_size)
    cancel_check() → True means cancel

    Returns TransferResult with success flag, bytes written, optional hash.
    """
    result = TransferResult()
    start = time.monotonic()

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    from app.device.mtp_manager import (
        IPortableDeviceResources, IStream, PROPERTYKEY, DWORD, ULONG,
        STGM_READ, POINTER, WPD_RESOURCE_DEFAULT_FMTID
    )
    import comtypes
    import ctypes

    # Get the resource stream
    resources = wpd_device._resources
    if resources is None:
        result.error = "Device not open"
        return result

    resource_key = PROPERTYKEY()
    resource_key.fmtid = comtypes.GUID(WPD_RESOURCE_DEFAULT_FMTID)
    resource_key.pid   = 0

    chunk_size = 4 * 1024 * 1024 # default fallback
    
    if chunk_config:
        ext = os.path.splitext(dest_path)[1].lower()
        if ext in chunk_config.get("ext_videos", []):
            chunk_size = int(chunk_config.get("chunk_size_videos_mb", 8)) * 1024 * 1024
        elif ext in chunk_config.get("ext_photos", []):
            chunk_size = int(chunk_config.get("chunk_size_photos_mb", 1)) * 1024 * 1024
        else:
            chunk_size = int(chunk_config.get("chunk_size_others_mb", 16)) * 1024 * 1024

    try:
        # GetStream returns (optimal_buffer_size, IStream) because pdwOptimalBufferSize is [in,out] and ppStream is [out]
        buf_size_val, stream = resources.GetStream(object_id, resource_key, STGM_READ, chunk_size)
    except comtypes.COMError as e:
        result.error = f"GetStream failed: {e}"
        logger.error(result.error)
        return result

    actual_chunk = max(buf_size_val, chunk_size)
    buf = (ctypes.c_char * actual_chunk)()

    hasher = hashlib.sha256() if compute_hash else None

    try:
        with open(dest_path, "wb") as f:
            while True:
                if cancel_check and cancel_check():
                    result.error = "Cancelled"
                    return result

                try:
                    # IStream.Read returns fetched count because pcbRead is [out]
                    fetched_val = stream.Read(buf, actual_chunk)
                except comtypes.COMError as e:
                    result.error = f"Read error: {e}"
                    logger.error(result.error)
                    return result

                if fetched_val == 0:
                    break

                mv = memoryview(buf)[:fetched_val]
                f.write(mv)
                if hasher:
                    hasher.update(mv)
                result.bytes_written += fetched_val

                if progress_cb:
                    progress_cb(result.bytes_written, file_size)

    except OSError as e:
        result.error = f"Write error: {e}"
        logger.error(result.error)
        # Clean up partial file
        try:
            os.remove(dest_path)
        except OSError:
            pass
        return result

    # Preserve modification time
    if modified is not None:
        try:
            import datetime
            if isinstance(modified, datetime.datetime):
                mtime = modified.timestamp()
                os.utime(dest_path, (mtime, mtime))
        except Exception as e:
            logger.debug(f"Could not set mtime: {e}")

    result.success = True
    result.sha256_hash = hasher.hexdigest() if hasher else None
    result.duration_s = time.monotonic() - start
    return result
