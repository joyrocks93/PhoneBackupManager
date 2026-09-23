# Phone Backup Manager

A modern, standalone Windows desktop application that automatically backs up photos and videos from Android phones connected via USB.

> **No Python or any development environment required on the end user's PC.** The final `.exe` is fully self-contained.

---

## Features

| Feature | Details |
|---|---|
| 📱 Device Detection | Automatic MTP/WPD device detection — no phone-side setup |
| 🔍 Media Scanner | Recursive scan for JPG, PNG, HEIC, MP4, MOV, MKV, and more |
| 💾 Smart Backup | Duplicate detection via DB + size + date + SHA-256 |
| ⏸️ Pause / Resume | Pause mid-backup and resume exactly where you left off |
| 📋 History | Full SQLite database of every backup session and file |
| ⚙️ Settings | Org mode, filters, auto-backup, theme, excluded folders |
| 🏎️ Performance | Streaming 1 MB chunks — handles 100 GB+ without memory issues |
| 🔒 Privacy | Fully offline — no cloud, no telemetry, no phone modifications |

---

## Requirements

### To run the `.exe`
- Windows 10 / 11 (64-bit)
- Android phone in **File Transfer (MTP)** mode

### To build from source
- Python 3.11+
- See `requirements.txt`

---

## Quick Start

### Option A — Run the pre-built EXE
1. Download `PhoneBackupManager.exe` from the `dist/` folder.
2. Double-click to run. No installation needed.
3. Connect your Android phone via USB, select **File Transfer** on the phone.
4. Click **Scan Device**, then **Start Backup**.

### Option B — Run from source
```bat
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run
python main.py
```

### Option C — Build your own EXE
```bat
build_exe.bat
```
The executable will appear at `dist\PhoneBackupManager\PhoneBackupManager.exe`.

---

## Phone Setup

1. Plug the USB cable into your Android phone and PC.
2. Pull down the notification shade on your phone.
3. Tap the USB notification.
4. Select **File Transfer** (also called MTP or Android File Transfer).
5. Unlock your phone if prompted.

The app will detect the phone automatically within 2 seconds.

---

## How Duplicate Detection Works

The app uses a 4-step strategy to avoid re-copying files:

1. **Database check** — Was this file (same path + size) already backed up?
2. **Disk check** — Does a file with the same name exist at the destination?
3. **Size comparison** — Same size? Likely a duplicate.
4. **Date comparison** — Modification dates within 2 seconds → skip.
5. **SHA-256 hash** — (Optional, enable in Settings) — 100% guaranteed.

If a file has the same name but different content, it is **renamed** (`IMG_001_1.jpg`) rather than overwritten.

---

## Backup Organisation Modes

### Mode A — Preserve Structure (default)
```
D:\Phone Backup\
  DCIM\
    Camera\
      IMG_20260923_184521.jpg
  Android\media\com.whatsapp\...
```

### Mode B — Organise by Date
```
D:\Phone Backup\
  2026\
    09\
      Photos\
        IMG_20260923_184521.jpg
      Videos\
        VID_20260923_120000.mp4
```

---

## Project Structure

```
PhoneBackupManager/
├── main.py                     # Entry point
├── requirements.txt
├── build_exe.bat               # Build script
│
├── app/
│   ├── ui/                     # PySide6 GUI pages
│   │   ├── main_window.py      # Main window + QSS stylesheet
│   │   ├── dashboard.py        # Device status + scan + START BACKUP
│   │   ├── backup_view.py      # Live progress page
│   │   ├── history_view.py     # Backup history table
│   │   └── settings_view.py    # Settings page
│   │
│   ├── device/                 # MTP/WPD device layer
│   │   ├── mtp_manager.py      # comtypes WPD COM wrapper
│   │   ├── device_manager.py   # High-level device API
│   │   └── device_monitor.py   # QThread background poller
│   │
│   ├── backup/                 # Backup engine
│   │   ├── scanner.py          # Recursive media scanner
│   │   ├── backup_manager.py   # Backup orchestrator (QThread)
│   │   ├── duplicate_detector.py
│   │   ├── transfer_manager.py # Streaming file copy
│   │   └── verifier.py         # SHA-256 verification
│   │
│   ├── database/
│   │   └── database.py         # SQLite (sessions + files)
│   │
│   └── config/
│       └── settings.py         # JSON settings
│
└── assets/
```

---

## Data & Privacy

- **All data stays on your PC.** Nothing is uploaded anywhere.
- The app **never deletes or modifies** files on your phone.
- The SQLite database is stored at `%USERPROFILE%\.phone_backup_manager\backup_history.db`.
- Settings are stored at `%USERPROFILE%\.phone_backup_manager\settings.json`.
- Logs are written to `%USERPROFILE%\.phone_backup_manager\logs\`.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Phone not detected | Check USB mode → **File Transfer** |
| Phone detected but no files | Unlock phone, accept any permission dialogs |
| Transfer very slow | Normal for MTP over USB 2.0 (~30–40 MB/s) |
| Files missing after backup | Check excluded folders in Settings |
| Build fails | Run `pip install --upgrade pyinstaller` |

---

## Technology

- **GUI:** PySide6 (Qt 6 for Python)
- **MTP/WPD:** Windows Portable Device (WPD) COM API via `comtypes`
- **Database:** SQLite (built into Python)
- **Packaging:** PyInstaller
- **OS:** Windows 10/11 only (WPD is Windows-native)
