"""
device_manager.py
High-level device management façade.
Abstracts WPD/MTP device access and provides a clean API to the rest of the app.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PhoneDevice:
    """Represents a connected Android/MTP phone."""
    pnp_id: str
    name: str
    manufacturer: str = ""
    description: str = ""
    is_accessible: bool = False
    storage_ids: list = field(default_factory=list)
    connected_at: datetime = field(default_factory=datetime.now)

    @property
    def display_name(self) -> str:
        return self.name or self.manufacturer or "Unknown Device"

    @property
    def device_id(self) -> str:
        """Stable identifier based on PnP ID."""
        return self.pnp_id


class DeviceManager:
    """
    High-level façade for device access.
    Handles WPD device detection and opening.
    """

    def __init__(self):
        self._current_devices: List[PhoneDevice] = []

    def refresh(self) -> List[PhoneDevice]:
        """
        Scan for connected devices. Returns list of PhoneDevice.
        Tries WPD/MTP. Falls back gracefully.
        """
        devices: List[PhoneDevice] = []

        # Try WPD/MTP
        try:
            from app.device.mtp_manager import list_mtp_devices
            mtp_infos = list_mtp_devices()
            for info in mtp_infos:
                dev = PhoneDevice(
                    pnp_id=info.pnp_id,
                    name=info.friendly_name,
                    manufacturer=info.manufacturer,
                    description=info.description,
                    is_accessible=True,
                )
                devices.append(dev)
        except Exception as e:
            logger.warning(f"WPD device scan failed: {e}")

        self._current_devices = devices
        return devices

    def get_current_devices(self) -> List[PhoneDevice]:
        return list(self._current_devices)

    def open_device(self, phone: PhoneDevice):
        """
        Return an open WPDDevice context manager for the given phone.
        Usage:
            with device_manager.open_device(phone) as wpd:
                for obj in wpd.walk():
                    ...
        """
        from app.device.mtp_manager import open_device, MTPDeviceInfo
        info = MTPDeviceInfo(
            pnp_id=phone.pnp_id,
            friendly_name=phone.name,
            manufacturer=phone.manufacturer,
        )
        return open_device(info)


# Singleton
_dm: Optional[DeviceManager] = None


def get_device_manager() -> DeviceManager:
    global _dm
    if _dm is None:
        _dm = DeviceManager()
    return _dm
