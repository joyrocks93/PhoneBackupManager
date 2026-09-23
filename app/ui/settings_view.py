"""
settings_view.py
Settings page — all application configuration options.
"""

import logging
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QCheckBox, QComboBox, QSpinBox, QLineEdit,
    QFileDialog, QScrollArea, QGroupBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFrameShadow(QFrame.Shadow.Sunken)
    return f


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
    lbl.setStyleSheet("color: #F1F5F9; margin-top: 8px;")
    return lbl


class SettingsPage(QWidget):

    theme_changed = Signal(str)

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main_window = main_window
        self._dirty = False
        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        # ── Header ─────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("Settings")
        title.setObjectName("section_title")
        hdr.addWidget(title)
        hdr.addStretch()

        self._save_btn = QPushButton("💾  Save Settings")
        self._save_btn.setObjectName("primary_btn")
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.clicked.connect(self._save)
        hdr.addWidget(self._save_btn)
        layout.addLayout(hdr)

        # ── Backup folder ──────────────────────────────────────────────────
        layout.addWidget(_section_label("📂  Backup Destination"))
        dest_card = QFrame()
        dest_card.setObjectName("card")
        dest_layout = QHBoxLayout(dest_card)
        self._backup_folder_edit = QLineEdit()
        self._backup_folder_edit.setPlaceholderText("Select backup folder…")
        browse_btn = QPushButton("Browse…")
        browse_btn.setObjectName("secondary_btn")
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.clicked.connect(self._browse_folder)
        dest_layout.addWidget(self._backup_folder_edit, 1)
        dest_layout.addWidget(browse_btn)
        layout.addWidget(dest_card)

        # ── Organisation ───────────────────────────────────────────────────
        layout.addWidget(_section_label("📁  Backup Organisation"))
        org_card = QFrame()
        org_card.setObjectName("card")
        org_layout = QVBoxLayout(org_card)
        org_layout.setSpacing(12)

        org_row = QHBoxLayout()
        org_lbl = QLabel("Mode:")
        org_lbl.setObjectName("file_label")
        self._org_combo = QComboBox()
        self._org_combo.addItem("Preserve phone folder structure", "preserve")
        self._org_combo.addItem("Organise by date (YYYY/MM/Photos|Videos)", "by_date")
        self._org_combo.setMinimumWidth(300)
        org_row.addWidget(org_lbl)
        org_row.addWidget(self._org_combo)
        org_row.addStretch()
        org_layout.addLayout(org_row)

        self._org_desc = QLabel("")
        self._org_desc.setObjectName("meta_label")
        self._org_desc.setWordWrap(True)
        org_layout.addWidget(self._org_desc)
        self._org_combo.currentIndexChanged.connect(self._update_org_desc)
        layout.addWidget(org_card)

        # ── File types ─────────────────────────────────────────────────────
        layout.addWidget(_section_label("🖼️  File Types"))
        types_card = QFrame()
        types_card.setObjectName("card")
        types_layout = QVBoxLayout(types_card)
        types_layout.setSpacing(10)

        self._cb_photos       = QCheckBox("📷  Photos (JPG, PNG, HEIC, WEBP, GIF…)")
        self._cb_videos       = QCheckBox("🎬  Videos (MP4, MOV, MKV, AVI…)")
        self._cb_whatsapp     = QCheckBox("💬  WhatsApp media (when accessible)")
        self._cb_downloads    = QCheckBox("⬇️  Downloads folder")
        self._cb_screenshots  = QCheckBox("📸  Screenshots")

        for cb in (self._cb_photos, self._cb_videos, self._cb_whatsapp,
                   self._cb_downloads, self._cb_screenshots):
            types_layout.addWidget(cb)

        layout.addWidget(types_card)

        # ── File size filters ──────────────────────────────────────────────
        layout.addWidget(_section_label("📏  File Size Filters"))
        size_card = QFrame()
        size_card.setObjectName("card")
        size_layout = QHBoxLayout(size_card)
        size_layout.setSpacing(20)

        min_lbl = QLabel("Min size (KB):")
        min_lbl.setObjectName("file_label")
        self._min_size_spin = QSpinBox()
        self._min_size_spin.setRange(0, 999999)
        self._min_size_spin.setSpecialValueText("No limit")
        self._min_size_spin.setSuffix(" KB")

        max_lbl = QLabel("Max size (MB):")
        max_lbl.setObjectName("file_label")
        self._max_size_spin = QSpinBox()
        self._max_size_spin.setRange(0, 99999)
        self._max_size_spin.setSpecialValueText("No limit")
        self._max_size_spin.setSuffix(" MB")

        size_layout.addWidget(min_lbl)
        size_layout.addWidget(self._min_size_spin)
        size_layout.addSpacing(20)
        size_layout.addWidget(max_lbl)
        size_layout.addWidget(self._max_size_spin)
        size_layout.addStretch()
        layout.addWidget(size_card)

        # ── Duplicate detection ────────────────────────────────────────────
        layout.addWidget(_section_label("🔍  Duplicate Detection"))
        dedup_card = QFrame()
        dedup_card.setObjectName("card")
        dedup_layout = QVBoxLayout(dedup_card)
        dedup_layout.setSpacing(10)

        self._cb_dedup = QCheckBox("Enable duplicate detection (strongly recommended)")
        self._cb_hash  = QCheckBox(
            "SHA-256 hash verification after copy (slower but ensures data integrity)"
        )
        dedup_hint = QLabel(
            "Duplicate detection checks: DB history → file size → modification date → SHA-256 hash"
        )
        dedup_hint.setObjectName("meta_label")
        dedup_hint.setWordWrap(True)

        dedup_layout.addWidget(self._cb_dedup)
        dedup_layout.addWidget(self._cb_hash)
        dedup_layout.addWidget(dedup_hint)
        layout.addWidget(dedup_card)

        # ── Automation ─────────────────────────────────────────────────────
        layout.addWidget(_section_label("⚡  Automation"))
        auto_card = QFrame()
        auto_card.setObjectName("card")
        auto_layout = QVBoxLayout(auto_card)
        auto_layout.setSpacing(10)

        self._cb_auto      = QCheckBox("Automatically start backup when phone is connected")
        self._cb_auto_confirm = QCheckBox("Show confirmation dialog before auto-backup starts")
        auto_hint = QLabel(
            "Auto-backup will scan and prompt (or start directly if confirmation is disabled)."
        )
        auto_hint.setObjectName("meta_label")
        auto_hint.setWordWrap(True)

        auto_layout.addWidget(self._cb_auto)
        auto_layout.addWidget(self._cb_auto_confirm)
        auto_layout.addWidget(auto_hint)
        layout.addWidget(auto_card)

        # ── Appearance ─────────────────────────────────────────────────────
        layout.addWidget(_section_label("🎨  Appearance"))
        theme_card = QFrame()
        theme_card.setObjectName("card")
        theme_layout = QHBoxLayout(theme_card)

        theme_lbl = QLabel("Theme:")
        theme_lbl.setObjectName("file_label")
        self._theme_combo = QComboBox()
        self._theme_combo.addItem("🌙  Dark", "dark")
        self._theme_combo.addItem("☀️  Light", "light")

        theme_layout.addWidget(theme_lbl)
        theme_layout.addWidget(self._theme_combo)
        theme_layout.addStretch()
        layout.addWidget(theme_card)

        # ── Excluded folders ───────────────────────────────────────────────
        layout.addWidget(_section_label("🚫  Excluded Folders"))
        excl_card = QFrame()
        excl_card.setObjectName("card")
        excl_layout = QVBoxLayout(excl_card)
        excl_layout.setSpacing(8)

        excl_hint = QLabel(
            "These folders will be skipped during scanning. One per line. "
            "Paths are relative to the device root (e.g. Android/data)."
        )
        excl_hint.setObjectName("meta_label")
        excl_hint.setWordWrap(True)
        excl_layout.addWidget(excl_hint)

        from PySide6.QtWidgets import QPlainTextEdit
        self._excl_edit = QPlainTextEdit()
        self._excl_edit.setMaximumHeight(100)
        self._excl_edit.setStyleSheet(
            "QPlainTextEdit { background: #0F172A; border: 1px solid #334155; "
            "border-radius: 6px; color: #F1F5F9; padding: 8px; font-family: Consolas; }"
        )
        excl_layout.addWidget(self._excl_edit)
        layout.addWidget(excl_card)

        layout.addStretch()

        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _load_settings(self):
        s = get_settings()
        self._backup_folder_edit.setText(s.backup_folder)

        idx = self._org_combo.findData(s.org_mode)
        self._org_combo.setCurrentIndex(max(0, idx))
        self._update_org_desc()

        self._cb_photos.setChecked(s.include_photos)
        self._cb_videos.setChecked(s.include_videos)
        self._cb_whatsapp.setChecked(s.include_whatsapp)
        self._cb_downloads.setChecked(s.include_downloads)
        self._cb_screenshots.setChecked(s.get("include_screenshots", True))
        self._min_size_spin.setValue(s.get("min_file_size_kb", 0))
        self._max_size_spin.setValue(s.get("max_file_size_mb", 0))
        self._cb_dedup.setChecked(s.duplicate_detection)
        self._cb_hash.setChecked(s.hash_verification)
        self._cb_auto.setChecked(s.auto_backup)
        self._cb_auto_confirm.setChecked(s.get("auto_backup_confirm", True))

        idx2 = self._theme_combo.findData(s.theme)
        self._theme_combo.setCurrentIndex(max(0, idx2))

        excl = s.excluded_folders
        self._excl_edit.setPlainText("\n".join(excl))

    def _update_org_desc(self):
        mode = self._org_combo.currentData()
        if mode == "preserve":
            self._org_desc.setText(
                "Example: D:\\Phone Backup\\DCIM\\Camera\\IMG_001.jpg"
            )
        else:
            self._org_desc.setText(
                "Example: D:\\Phone Backup\\2026\\09\\Photos\\IMG_001.jpg"
            )

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Backup Folder",
            self._backup_folder_edit.text() or os.path.expanduser("~"),
        )
        if folder:
            self._backup_folder_edit.setText(folder)

    def _save(self):
        s = get_settings()
        s.backup_folder      = self._backup_folder_edit.text().strip()
        s.set("org_mode",              self._org_combo.currentData())
        s.set("include_photos",        self._cb_photos.isChecked())
        s.set("include_videos",        self._cb_videos.isChecked())
        s.set("include_whatsapp",      self._cb_whatsapp.isChecked())
        s.set("include_downloads",     self._cb_downloads.isChecked())
        s.set("include_screenshots",   self._cb_screenshots.isChecked())
        s.set("min_file_size_kb",      self._min_size_spin.value())
        s.set("max_file_size_mb",      self._max_size_spin.value())
        s.set("duplicate_detection",   self._cb_dedup.isChecked())
        s.set("hash_verification",     self._cb_hash.isChecked())
        s.set("auto_backup",           self._cb_auto.isChecked())
        s.set("auto_backup_confirm",   self._cb_auto_confirm.isChecked())
        s.set("first_run",             False)

        new_theme = self._theme_combo.currentData()
        old_theme = s.theme
        s.set("theme", new_theme)

        # Excluded folders
        text = self._excl_edit.toPlainText()
        excl = [l.strip() for l in text.splitlines() if l.strip()]
        s.set("excluded_folders", excl)

        s.save()
        self._save_btn.setText("✅  Saved!")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self._save_btn.setText("💾  Save Settings"))

        if new_theme != old_theme:
            self.theme_changed.emit(new_theme)

        logger.info("Settings saved.")
