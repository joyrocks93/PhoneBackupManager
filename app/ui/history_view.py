"""
history_view.py
Backup history page — table of past sessions.
"""

import logging
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QScrollArea, QAbstractItemView
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor

from app.database.database import get_db

logger = logging.getLogger(__name__)


def _fmt_size(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def _fmt_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d %b %Y  %H:%M")
    except Exception:
        return iso or "—"


STATUS_COLORS = {
    "completed":  "#22C55E",
    "running":    "#3B82F6",
    "cancelled":  "#F59E0B",
    "failed":     "#EF4444",
}

STATUS_ICONS = {
    "completed":  "✅",
    "running":    "⏳",
    "cancelled":  "⚠️",
    "failed":     "❌",
}


class HistoryPage(QWidget):

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main_window = main_window
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Backup History")
        title.setObjectName("section_title")
        hdr.addWidget(title)
        hdr.addStretch()

        refresh_btn = QPushButton("↻  Refresh")
        refresh_btn.setObjectName("secondary_btn")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._load)
        hdr.addWidget(refresh_btn)
        layout.addLayout(hdr)

        # Summary stats
        sum_row = QHBoxLayout()
        sum_row.setSpacing(16)
        self._total_sessions_lbl = QLabel("—")
        self._total_sessions_lbl.setObjectName("stat_value")
        self._total_files_lbl = QLabel("—")
        self._total_files_lbl.setObjectName("stat_value")
        self._total_size_lbl = QLabel("—")
        self._total_size_lbl.setObjectName("stat_value")

        for val, label in [
            (self._total_sessions_lbl, "Sessions"),
            (self._total_files_lbl,    "Files Backed Up"),
            (self._total_size_lbl,     "Total Transferred"),
        ]:
            card = QFrame()
            card.setObjectName("card")
            cl = QVBoxLayout(card)
            cl.setSpacing(4)
            cl.addWidget(val)
            lbl = QLabel(label.upper())
            lbl.setObjectName("stat_label")
            cl.addWidget(lbl)
            sum_row.addWidget(card)

        sum_row.addStretch()
        layout.addLayout(sum_row)

        # Table
        self._table = QTableWidget()
        self._table.setObjectName("history_table")
        self._table.setColumnCount(8)
        self._table.setHorizontalHeaderLabels([
            "Date", "Phone", "Copied", "Skipped", "Failed",
            "Size", "Location", "Status"
        ])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setColumnWidth(0, 160)
        self._table.setColumnWidth(1, 180)
        self._table.setColumnWidth(2, 80)
        self._table.setColumnWidth(3, 80)
        self._table.setColumnWidth(4, 70)
        self._table.setColumnWidth(5, 90)
        self._table.setColumnWidth(7, 100)
        layout.addWidget(self._table, 1)

        # No history label
        self._empty_lbl = QLabel("No backup history yet.\nRun your first backup to see it here.")
        self._empty_lbl.setObjectName("meta_label")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setFont(QFont("Segoe UI", 13))
        self._empty_lbl.setVisible(False)
        layout.addWidget(self._empty_lbl)

    def _load(self):
        db = get_db()
        sessions = db.get_sessions(limit=200)

        if not sessions:
            self._table.setVisible(False)
            self._empty_lbl.setVisible(True)
            self._total_sessions_lbl.setText("0")
            self._total_files_lbl.setText("0")
            self._total_size_lbl.setText("0 B")
            return

        self._table.setVisible(True)
        self._empty_lbl.setVisible(False)
        self._table.setRowCount(len(sessions))

        total_copied = 0
        total_bytes  = 0

        for row, s in enumerate(sessions):
            date_str    = _fmt_date(s["started_at"])
            phone_name  = s["device_name"] or "Unknown"
            copied      = s["files_copied"]
            skipped     = s["files_skipped"]
            failed      = s["files_failed"]
            size_bytes  = s["bytes_copied"]
            location    = s["backup_folder"]
            status      = s["status"]

            total_copied += copied
            total_bytes  += size_bytes

            cells = [
                (date_str,          None),
                (phone_name,        None),
                (f"{copied:,}",     "#22C55E" if copied > 0 else None),
                (f"{skipped:,}",    "#94A3B8"),
                (str(failed),       "#EF4444" if failed > 0 else "#94A3B8"),
                (_fmt_size(size_bytes), None),
                (location,          None),
                (f"{STATUS_ICONS.get(status, '')} {status.capitalize()}",
                 STATUS_COLORS.get(status)),
            ]

            for col, (text, color) in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if color:
                    item.setForeground(QColor(color))
                self._table.setItem(row, col, item)

            self._table.setRowHeight(row, 40)

        self._total_sessions_lbl.setText(str(len(sessions)))
        self._total_files_lbl.setText(f"{total_copied:,}")
        self._total_size_lbl.setText(_fmt_size(total_bytes))

    def showEvent(self, event):
        """Refresh history every time page is shown."""
        super().showEvent(event)
        QTimer.singleShot(100, self._load)
