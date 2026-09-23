"""
dashboard.py
Dashboard page — device status, media summary, backup location picker, START BACKUP.
"""

import os
import shutil
import logging
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QSizePolicy, QGridLayout, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread
from PySide6.QtGui import QFont

from app.device.device_manager import PhoneDevice
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


def _make_card() -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    return f


def _label(text: str, obj_name: str = "", align=Qt.AlignmentFlag.AlignLeft) -> QLabel:
    lbl = QLabel(text)
    if obj_name:
        lbl.setObjectName(obj_name)
    lbl.setAlignment(align)
    return lbl


def _fmt_size(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


class ScanThread(QThread):
    """Quick scan to get media summary for dashboard."""
    finished = Signal(object)   # ScanResult

    def __init__(self, phone: PhoneDevice, parent=None):
        super().__init__(parent)
        self._phone = phone

    def run(self):
        try:
            from app.device.device_manager import get_device_manager
            from app.backup.scanner import Scanner
            dm = get_device_manager()
            with dm.open_device(self._phone) as wpd:
                scanner = Scanner()
                result = scanner.scan(wpd)
            self.finished.emit(result)
        except Exception as e:
            logger.error(f"Dashboard scan error: {e}", exc_info=True)
            self.finished.emit(None)


class DashboardPage(QWidget):

    start_backup_requested = Signal()

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main_window = main_window
        self._phone: Optional[PhoneDevice] = None
        self._scan_result = None
        self._scan_thread: Optional[ScanThread] = None

        self._build_ui()
        self._refresh_dest_info()

    def _build_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # ── Page header ────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = _label("Dashboard", "section_title")
        hdr.addWidget(title)
        hdr.addStretch()
        refresh_btn = QPushButton("↻  Refresh Devices")
        refresh_btn.setObjectName("secondary_btn")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._on_refresh)
        hdr.addWidget(refresh_btn)
        layout.addLayout(hdr)

        # ── Device card ────────────────────────────────────────────────────
        dev_card = _make_card()
        dev_layout = QVBoxLayout(dev_card)
        dev_layout.setSpacing(12)

        dev_row = QHBoxLayout()
        phone_icon = QLabel("📱")
        phone_icon.setFont(QFont("Segoe UI Emoji", 28))
        dev_row.addWidget(phone_icon)

        dev_text = QVBoxLayout()
        self._dev_name_lbl = QLabel("No device connected")
        self._dev_name_lbl.setObjectName("section_title")
        self._dev_name_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self._dev_status_lbl = QLabel("Connect your Android phone via USB and select File Transfer")
        self._dev_status_lbl.setObjectName("meta_label")
        self._dev_status_lbl.setWordWrap(True)
        dev_text.addWidget(self._dev_name_lbl)
        dev_text.addWidget(self._dev_status_lbl)
        dev_row.addLayout(dev_text, 1)
        dev_layout.addLayout(dev_row)

        # Instruction banner (shown when no device)
        self._instruction_frame = QFrame()
        self._instruction_frame.setStyleSheet(
            "QFrame { background: rgba(245,158,11,0.1); border-radius: 8px; "
            "border: 1px solid rgba(245,158,11,0.3); padding: 10px; }"
        )
        inst_layout = QHBoxLayout(self._instruction_frame)
        inst_layout.setContentsMargins(12, 10, 12, 10)
        inst_icon = QLabel("⚠️")
        inst_text = QLabel(
            "Unlock your phone, then go to USB Settings → File Transfer mode."
        )
        inst_text.setStyleSheet("color: #F59E0B; font-size: 12px;")
        inst_text.setWordWrap(True)
        inst_layout.addWidget(inst_icon)
        inst_layout.addWidget(inst_text, 1)
        dev_layout.addWidget(self._instruction_frame)
        layout.addWidget(dev_card)

        # ── Stats row ──────────────────────────────────────────────────────
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)

        self._photos_card = self._make_stat_card("📷", "—", "Photos")
        self._videos_card = self._make_stat_card("🎬", "—", "Videos")
        self._size_card   = self._make_stat_card("💾", "—", "Total Size")
        self._free_card   = self._make_stat_card("🗂️",  "—", "Free on PC")

        stats_row.addWidget(self._photos_card)
        stats_row.addWidget(self._videos_card)
        stats_row.addWidget(self._size_card)
        stats_row.addWidget(self._free_card)
        layout.addLayout(stats_row)

        # ── Scanning indicator ─────────────────────────────────────────────
        self._scan_indicator = QLabel("🔍  Scanning device…")
        self._scan_indicator.setObjectName("accent_label")
        self._scan_indicator.setVisible(False)
        layout.addWidget(self._scan_indicator)

        # ── Backup location card ───────────────────────────────────────────
        loc_card = _make_card()
        loc_layout = QVBoxLayout(loc_card)
        loc_layout.setSpacing(10)

        loc_header = QHBoxLayout()
        loc_title = QLabel("💽  Backup Location")
        loc_title.setObjectName("file_label")
        loc_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        loc_header.addWidget(loc_title)
        loc_header.addStretch()
        change_btn = QPushButton("Browse…")
        change_btn.setObjectName("secondary_btn")
        change_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        change_btn.clicked.connect(self._browse_dest)
        loc_header.addWidget(change_btn)
        loc_layout.addLayout(loc_header)

        self._dest_path_lbl = QLabel("—")
        self._dest_path_lbl.setObjectName("meta_label")
        self._dest_path_lbl.setWordWrap(True)
        loc_layout.addWidget(self._dest_path_lbl)

        self._dest_info_lbl = QLabel("")
        self._dest_info_lbl.setObjectName("meta_label")
        loc_layout.addWidget(self._dest_info_lbl)

        layout.addWidget(loc_card)

        # ── Action row ─────────────────────────────────────────────────────
        action_row = QHBoxLayout()
        action_row.addStretch()

        self._start_btn = QPushButton("▶  START BACKUP")
        self._start_btn.setObjectName("primary_btn")
        self._start_btn.setMinimumWidth(200)
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.clicked.connect(self._on_start_backup)
        self._start_btn.setEnabled(False)

        self._scan_btn = QPushButton("🔍  Scan Device")
        self._scan_btn.setObjectName("secondary_btn")
        self._scan_btn.setMinimumWidth(140)
        self._scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._scan_btn.clicked.connect(self._on_scan)
        self._scan_btn.setEnabled(False)

        action_row.addWidget(self._scan_btn)
        action_row.addWidget(self._start_btn)
        layout.addLayout(action_row)

        layout.addStretch()

        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _make_stat_card(self, icon: str, value: str, label: str) -> QFrame:
        card = _make_card()
        layout = QVBoxLayout(card)
        layout.setSpacing(4)
        layout.setContentsMargins(16, 16, 16, 16)

        icon_lbl = QLabel(icon)
        icon_lbl.setFont(QFont("Segoe UI Emoji", 20))
        layout.addWidget(icon_lbl)

        val_lbl = QLabel(value)
        val_lbl.setObjectName("stat_value")
        val_lbl.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        layout.addWidget(val_lbl)

        lbl = QLabel(label.upper())
        lbl.setObjectName("stat_label")
        layout.addWidget(lbl)

        # Store references for updating
        card._value_lbl = val_lbl
        return card

    def _update_stat(self, card: QFrame, value: str):
        card._value_lbl.setText(value)

    # ── Device callbacks ───────────────────────────────────────────────────

    def set_device(self, phone: Optional[PhoneDevice]):
        self._phone = phone
        if phone:
            self._dev_name_lbl.setText(phone.display_name)
            self._dev_status_lbl.setText(f"● Connected  —  {phone.manufacturer}")
            self._dev_status_lbl.setStyleSheet("color: #22C55E; font-size: 12px;")
            self._instruction_frame.setVisible(False)
            self._scan_btn.setEnabled(True)
        else:
            self._dev_name_lbl.setText("No device connected")
            self._dev_status_lbl.setText(
                "Connect your Android phone via USB and select File Transfer"
            )
            self._dev_status_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
            self._instruction_frame.setVisible(True)
            self._scan_btn.setEnabled(False)
            self._start_btn.setEnabled(False)
            self._reset_stats()

    def _reset_stats(self):
        self._scan_result = None
        self._update_stat(self._photos_card, "—")
        self._update_stat(self._videos_card, "—")
        self._update_stat(self._size_card,   "—")

    # ── Scan ───────────────────────────────────────────────────────────────

    def _on_scan(self):
        if not self._phone:
            return
        self._scan_btn.setEnabled(False)
        self._start_btn.setEnabled(False)
        self._scan_indicator.setVisible(True)
        self._reset_stats()

        self._scan_thread = ScanThread(self._phone, self)
        self._scan_thread.finished.connect(self._on_scan_done)
        self._scan_thread.start()

    def _on_scan_done(self, result):
        self._scan_indicator.setVisible(False)
        self._scan_btn.setEnabled(True)
        if result is None:
            self._dev_status_lbl.setText("Scan failed. Check connection.")
            return
        self._scan_result = result
        self._update_stat(self._photos_card, f"{result.photo_count:,}")
        self._update_stat(self._videos_card, f"{result.video_count:,}")
        self._update_stat(self._size_card,   _fmt_size(result.total_size))
        self._start_btn.setEnabled(result.total_count > 0)

    # ── Dest / storage ─────────────────────────────────────────────────────

    def _browse_dest(self):
        settings = get_settings()
        folder = QFileDialog.getExistingDirectory(
            self, "Select Backup Folder",
            settings.backup_folder or os.path.expanduser("~"),
        )
        if folder:
            settings.backup_folder = folder
            settings.save()
            self._refresh_dest_info()

    def _refresh_dest_info(self):
        settings = get_settings()
        folder = settings.backup_folder
        self._dest_path_lbl.setText(folder)
        try:
            usage = shutil.disk_usage(folder if os.path.exists(folder) else os.path.splitdrive(folder)[0] + "\\")
            free  = usage.free
            total = usage.total
            self._dest_info_lbl.setText(
                f"Free: {_fmt_size(free)}  /  Total: {_fmt_size(total)}"
            )
            self._update_stat(self._free_card, _fmt_size(free))
        except Exception:
            self._dest_info_lbl.setText("(folder not found)")
            self._update_stat(self._free_card, "—")

    # ── Actions ────────────────────────────────────────────────────────────

    def _on_refresh(self):
        from app.device.device_manager import get_device_manager
        devices = get_device_manager().refresh()
        if devices:
            self.set_device(devices[0])
        else:
            self.set_device(None)

    def _on_start_backup(self):
        self.start_backup_requested.emit()
        # Pass scan result to backup page
        bp = self._main_window._pages.get("backup")
        if bp and self._phone:
            bp.prepare(self._phone, self._scan_result)
