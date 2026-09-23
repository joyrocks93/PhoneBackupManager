"""
main.py
Phone Backup Manager — application entry point.

Initialises COM, sets up logging, and launches the PySide6 GUI.
"""

import sys
import os
import logging
from datetime import datetime
from pathlib import Path

# ── Windows COM init (must happen before any comtypes imports) ────────────────
if sys.platform == "win32":
    import ctypes
    ctypes.windll.ole32.CoInitializeEx(None, 2)  # COINIT_APARTMENTTHREADED (required by Qt)

# ── Logging setup ─────────────────────────────────────────────────────────────
_LOG_DIR = Path.home() / ".phone_backup_manager" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / f"backup_{datetime.now().strftime('%Y-%m-%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("PhoneBackupManager")

# ── Suppress noisy comtypes warnings ─────────────────────────────────────────
logging.getLogger("comtypes").setLevel(logging.WARNING)


def main():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt, QCoreApplication
    from PySide6.QtGui import QIcon, QFont

    QCoreApplication.setApplicationName("Phone Backup Manager")
    QCoreApplication.setOrganizationName("PhoneBackupManager")
    QCoreApplication.setApplicationVersion("1.0.0")

    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Load settings
    from app.config.settings import get_settings
    settings = get_settings()
    theme = settings.theme

    # Apply font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Build & show main window
    from app.ui.main_window import MainWindow
    window = MainWindow(theme=theme)
    window.show()

    logger.info("Phone Backup Manager started.")
    logger.info(f"Log file: {_LOG_FILE}")

    ret = app.exec()
    logger.info("Application exiting.")

    # Cleanup COM
    if sys.platform == "win32":
        ctypes.windll.ole32.CoUninitialize()

    sys.exit(ret)


if __name__ == "__main__":
    main()
