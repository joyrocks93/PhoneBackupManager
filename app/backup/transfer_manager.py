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

CHUNK_SIZE = 1 * 1024 * 1024   # 1 MB


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

    buf_size = DWORD(CHUNK_SIZE)
    stream_ptr = POINTER(IStream)()

    try:
        resources.GetStream(object_id, resource_key, STGM_READ, ctypes.byref(buf_size), stream_ptr)
    except comtypes.COMError as e:
        result.error = f"GetStream failed: {e}"
        logger.error(result.error)
        return result

    actual_chunk = max(buf_size.value, CHUNK_SIZE)
    buf = (ctypes.c_char * actual_chunk)()

    hasher = hashlib.sha256() if compute_hash else None

    try:
        with open(dest_path, "wb") as f:
            while True:
                if cancel_check and cancel_check():
                    result.error = "Cancelled"
                    return result

                fetched = ULONG(0)
                try:
                    stream_ptr.Read(buf, actual_chunk, ctypes.byref(fetched))
                except comtypes.COMError as e:
                    if fetched.value == 0:
                        break
                    result.error = f"Read error: {e}"
                    logger.error(result.error)
                    return result

                if fetched.value == 0:
                    break

                data = bytes(buf[:fetched.value])
                f.write(data)
                if hasher:
                    hasher.update(data)
                result.bytes_written += fetched.value

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
