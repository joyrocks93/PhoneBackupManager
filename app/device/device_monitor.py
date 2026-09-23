"""
device_monitor.py
QThread that polls for device connect/disconnect events every 2 seconds.
Emits Qt signals when device state changes.
"""

import logging
import time
from typing import List, Set

from PySide6.QtCore import QThread, Signal

from app.device.device_manager import PhoneDevice, get_device_manager

logger = logging.getLogger(__name__)


class DeviceMonitor(QThread):
    """
    Background thread that polls for connected MTP/WPD devices.
    Emits device_connected / device_disconnected when state changes.
    """

    device_connected    = Signal(object)   # PhoneDevice
    device_disconnected = Signal(object)   # PhoneDevice
    devices_updated     = Signal(list)     # List[PhoneDevice]

    POLL_INTERVAL_S = 2.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._known_ids: Set[str] = set()
        self._known_devices: dict[str, PhoneDevice] = {}

    def run(self):
        self._running = True
        dm = get_device_manager()
        logger.info("Device monitor started.")

        while self._running:
            try:
                current = dm.refresh()
                current_ids = {d.pnp_id for d in current}

                # Newly connected
                for dev in current:
                    if dev.pnp_id not in self._known_ids:
                        logger.info(f"Device connected: {dev.name}")
                        self._known_devices[dev.pnp_id] = dev
                        self.device_connected.emit(dev)

                # Disconnected
                for pnp_id in list(self._known_ids):
                    if pnp_id not in current_ids:
                        dev = self._known_devices.pop(pnp_id, None)
                        if dev:
                            logger.info(f"Device disconnected: {dev.name}")
                            self.device_disconnected.emit(dev)

                self._known_ids = current_ids
                self.devices_updated.emit(current)

            except Exception as e:
                logger.warning(f"DeviceMonitor poll error: {e}")

            # Sleep in small increments so we can stop quickly
            for _ in range(int(self.POLL_INTERVAL_S / 0.1)):
                if not self._running:
                    break
                time.sleep(0.1)

        logger.info("Device monitor stopped.")

    def stop(self):
        self._running = False
        self.wait(3000)
