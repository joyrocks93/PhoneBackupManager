"""
main_window.py
Main application window with sidebar navigation.
Uses a custom dark QSS stylesheet and frameless-style design.
"""

import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QSizePolicy, QFrame
)
from PySide6.QtCore import Qt, QSize, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon, QFont, QColor, QPalette, QPixmap, QPainter, QBrush

from app.device.device_monitor import DeviceMonitor
from app.device.device_manager import PhoneDevice

logger = logging.getLogger(__name__)

# ── Colour tokens ──────────────────────────────────────────────────────────────
DARK_BG     = "#0F172A"
SIDEBAR_BG  = "#1E293B"
CARD_BG     = "#1E293B"
ACCENT      = "#3B82F6"
ACCENT_DARK = "#2563EB"
TEXT_PRI    = "#F1F5F9"
TEXT_SEC    = "#94A3B8"
SUCCESS     = "#22C55E"
WARNING     = "#F59E0B"
DANGER      = "#EF4444"
BORDER      = "#334155"

APP_STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {DARK_BG};
    color: {TEXT_PRI};
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}}

/* Sidebar */
#sidebar {{
    background-color: {SIDEBAR_BG};
    border-right: 1px solid {BORDER};
    min-width: 200px;
    max-width: 200px;
}}

#app_title {{
    font-size: 14px;
    font-weight: 700;
    color: {TEXT_PRI};
    padding: 8px 0 4px 0;
}}

#app_subtitle {{
    font-size: 10px;
    color: {TEXT_SEC};
    letter-spacing: 1px;
}}

/* Nav buttons */
QPushButton#nav_btn {{
    background-color: transparent;
    color: {TEXT_SEC};
    text-align: left;
    padding: 11px 20px;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#nav_btn:hover {{
    background-color: rgba(59, 130, 246, 0.12);
    color: {TEXT_PRI};
}}
QPushButton#nav_btn[active=true] {{
    background-color: rgba(59, 130, 246, 0.2);
    color: {ACCENT};
    font-weight: 600;
}}

/* Device badge */
#device_badge {{
    background-color: rgba(34, 197, 94, 0.15);
    border: 1px solid rgba(34, 197, 94, 0.3);
    border-radius: 8px;
    padding: 8px 12px;
    margin: 4px 8px;
}}
#device_badge_label {{
    color: {SUCCESS};
    font-size: 11px;
    font-weight: 600;
}}
#device_name_label {{
    color: {TEXT_PRI};
    font-size: 12px;
    font-weight: 600;
}}

#no_device_label {{
    color: {TEXT_SEC};
    font-size: 11px;
    padding: 8px 12px;
}}

/* Cards */
QFrame#card {{
    background-color: {CARD_BG};
    border-radius: 12px;
    border: 1px solid {BORDER};
    padding: 16px;
}}

/* Primary button */
QPushButton#primary_btn {{
    background-color: {ACCENT};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 12px 24px;
    font-size: 13px;
    font-weight: 600;
    min-height: 42px;
}}
QPushButton#primary_btn:hover {{
    background-color: {ACCENT_DARK};
}}
QPushButton#primary_btn:pressed {{
    background-color: #1D4ED8;
}}
QPushButton#primary_btn:disabled {{
    background-color: #374151;
    color: {TEXT_SEC};
}}

/* Danger button */
QPushButton#danger_btn {{
    background-color: transparent;
    color: {DANGER};
    border: 1px solid {DANGER};
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton#danger_btn:hover {{
    background-color: rgba(239, 68, 68, 0.1);
}}

/* Secondary button */
QPushButton#secondary_btn {{
    background-color: transparent;
    color: {TEXT_PRI};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#secondary_btn:hover {{
    background-color: rgba(255,255,255,0.05);
    border-color: {TEXT_SEC};
}}
QPushButton#secondary_btn:disabled {{
    color: {TEXT_SEC};
    border-color: {BORDER};
}}

/* Progress bar */
QProgressBar {{
    background-color: #1e3a5f;
    border-radius: 6px;
    height: 10px;
    border: none;
}}
QProgressBar::chunk {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT}, stop:1 #60A5FA
    );
    border-radius: 6px;
}}

/* Labels */
QLabel#section_title {{
    font-size: 20px;
    font-weight: 700;
    color: {TEXT_PRI};
}}
QLabel#stat_value {{
    font-size: 22px;
    font-weight: 700;
    color: {TEXT_PRI};
}}
QLabel#stat_label {{
    font-size: 11px;
    color: {TEXT_SEC};
    text-transform: uppercase;
    letter-spacing: 1px;
}}
QLabel#file_label {{
    color: {TEXT_PRI};
    font-size: 13px;
}}
QLabel#meta_label {{
    color: {TEXT_SEC};
    font-size: 12px;
}}
QLabel#accent_label {{
    color: {ACCENT};
    font-size: 12px;
    font-weight: 600;
}}
QLabel#success_label {{
    color: {SUCCESS};
    font-weight: 600;
}}
QLabel#warning_label {{
    color: {WARNING};
}}
QLabel#danger_label {{
    color: {DANGER};
}}

/* Scroll bars */
QScrollBar:vertical {{
    background: {DARK_BG};
    width: 8px;
    margin: 0;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_SEC};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

/* Table */
QTableWidget {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    color: {TEXT_PRI};
    selection-background-color: rgba(59,130,246,0.2);
}}
QTableWidget::item {{
    padding: 8px;
    border: none;
}}
QHeaderView::section {{
    background-color: {SIDEBAR_BG};
    color: {TEXT_SEC};
    padding: 8px;
    border: none;
    border-bottom: 1px solid {BORDER};
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
}}

/* Input / ComboBox / CheckBox */
QLineEdit, QSpinBox, QComboBox {{
    background-color: {SIDEBAR_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    color: {TEXT_PRI};
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {SIDEBAR_BG};
    border: 1px solid {BORDER};
    color: {TEXT_PRI};
    selection-background-color: {ACCENT};
}}
QCheckBox {{
    color: {TEXT_PRI};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {BORDER};
    border-radius: 4px;
    background: {DARK_BG};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
    image: url(:/icons/check.png);
}}

/* Separator */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    color: {BORDER};
}}

/* Tab Widget */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background: {CARD_BG};
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_SEC};
    padding: 8px 16px;
    border: none;
}}
QTabBar::tab:selected {{
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}
"""

LIGHT_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #F8FAFC;
    color: #0F172A;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}
"""


class MainWindow(QMainWindow):

    def __init__(self, theme: str = "dark"):
        super().__init__()
        self._theme = theme
        self._current_phone: PhoneDevice | None = None
        self._pages: dict[str, QWidget] = {}
        self._nav_buttons: dict[str, QPushButton] = {}

        self.setWindowTitle("Phone Backup Manager")
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)

        self._apply_stylesheet()
        self._build_ui()
        self._start_monitor()

    def _apply_stylesheet(self):
        if self._theme == "dark":
            self.setStyleSheet(APP_STYLESHEET)
        else:
            self.setStyleSheet(LIGHT_STYLESHEET)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 20, 12, 20)
        sidebar_layout.setSpacing(4)

        # App icon + title
        title_label = QLabel("📱 Phone Backup")
        title_label.setObjectName("app_title")
        sub_label   = QLabel("MANAGER")
        sub_label.setObjectName("app_subtitle")
        sidebar_layout.addWidget(title_label)
        sidebar_layout.addWidget(sub_label)
        sidebar_layout.addSpacing(16)

        # Device status badge
        self._device_badge = QWidget()
        self._device_badge.setObjectName("device_badge")
        badge_layout = QVBoxLayout(self._device_badge)
        badge_layout.setContentsMargins(8, 8, 8, 8)
        badge_layout.setSpacing(2)
        self._badge_status = QLabel("● NO DEVICE")
        self._badge_status.setObjectName("device_badge_label")
        self._badge_name   = QLabel("—")
        self._badge_name.setObjectName("device_name_label")
        badge_layout.addWidget(self._badge_status)
        badge_layout.addWidget(self._badge_name)
        sidebar_layout.addWidget(self._device_badge)
        self._update_device_badge(None)

        sidebar_layout.addSpacing(12)

        # Nav buttons
        nav_items = [
            ("dashboard",  "🏠  Dashboard"),
            ("backup",     "💾  Backup"),
            ("history",    "📋  History"),
            ("settings",   "⚙️  Settings"),
        ]
        for page_id, label in nav_items:
            btn = QPushButton(label)
            btn.setObjectName("nav_btn")
            btn.setCheckable(False)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, pid=page_id: self._navigate(pid))
            self._nav_buttons[page_id] = btn
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()

        # Version label
        ver = QLabel("v1.0.0")
        ver.setObjectName("meta_label")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(ver)

        root_layout.addWidget(sidebar)

        # ── Page stack ────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        root_layout.addWidget(self._stack, 1)

        # Lazy-import pages to speed up startup
        from app.ui.dashboard import DashboardPage
        from app.ui.backup_view import BackupPage
        from app.ui.history_view import HistoryPage
        from app.ui.settings_view import SettingsPage

        self._pages["dashboard"] = DashboardPage(self)
        self._pages["backup"]    = BackupPage(self)
        self._pages["history"]   = HistoryPage(self)
        self._pages["settings"]  = SettingsPage(self)

        for page in self._pages.values():
            self._stack.addWidget(page)

        # Connect cross-page signals
        self._pages["dashboard"].start_backup_requested.connect(
            lambda: self._navigate("backup")
        )
        self._pages["settings"].theme_changed.connect(self._on_theme_changed)

        self._navigate("dashboard")

    def _navigate(self, page_id: str):
        if page_id not in self._pages:
            return
        self._stack.setCurrentWidget(self._pages[page_id])
        for pid, btn in self._nav_buttons.items():
            btn.setProperty("active", pid == page_id)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _start_monitor(self):
        self._monitor = DeviceMonitor(self)
        self._monitor.device_connected.connect(self._on_device_connected)
        self._monitor.device_disconnected.connect(self._on_device_disconnected)
        self._monitor.start()

    def _on_device_connected(self, phone: PhoneDevice):
        self._current_phone = phone
        self._update_device_badge(phone)
        self._pages["dashboard"].set_device(phone)
        logger.info(f"UI: device connected: {phone.name}")

    def _on_device_disconnected(self, phone: PhoneDevice):
        if self._current_phone and self._current_phone.pnp_id == phone.pnp_id:
            self._current_phone = None
            self._update_device_badge(None)
            self._pages["dashboard"].set_device(None)
        logger.info(f"UI: device disconnected: {phone.name}")

    def _update_device_badge(self, phone: PhoneDevice | None):
        if phone:
            self._badge_status.setText("● CONNECTED")
            self._badge_status.setStyleSheet(f"color: #22C55E; font-size: 10px; font-weight: 700;")
            self._badge_name.setText(phone.display_name)
        else:
            self._badge_status.setText("● NO DEVICE")
            self._badge_status.setStyleSheet(f"color: #94A3B8; font-size: 10px; font-weight: 700;")
            self._badge_name.setText("—")

    def _on_theme_changed(self, theme: str):
        self._theme = theme
        self._apply_stylesheet()

    def get_current_phone(self) -> PhoneDevice | None:
        return self._current_phone

    def closeEvent(self, event):
        self._monitor.stop()
        super().closeEvent(event)
