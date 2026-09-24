@echo off
REM ============================================================
REM  Phone Backup Manager — Build Script
REM  Creates a standalone PhoneBackupManager.exe in dist\
REM ============================================================
setlocal

echo.
echo ============================================================
echo  Phone Backup Manager - EXE Build
echo ============================================================
echo.

REM --- Check Python ---
py --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11+ from python.org
    pause
    exit /b 1
)
py --version

REM --- Install / upgrade dependencies ---
echo.
echo [1/3] Installing dependencies...
py -m pip install --upgrade pip >nul
py -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo       Done.

REM --- Pre-generate comtypes WPD modules (required for PyInstaller) ---
echo.
echo [2/3] Pre-generating WPD comtypes cache...
py -c "import comtypes.client; comtypes.client.GetModule('portabledeviceapi.dll')" 2>nul
py -c "import comtypes.client; comtypes.client.GetModule('portabledevicetypes.dll')" 2>nul
echo       Done (errors above are non-fatal).

REM --- Build with PyInstaller ---
echo.
echo [3/3] Building executable...
echo.

py -m PyInstaller ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "PhoneBackupManager" ^
    --icon "assets\icon.ico" ^
    --add-data "assets;assets" ^
    --hidden-import "comtypes.stream" ^
    --hidden-import "comtypes.persist" ^
    --hidden-import "comtypes.typeinfo" ^
    --hidden-import "PySide6.QtSvg" ^
    --hidden-import "PySide6.QtXml" ^
    --collect-submodules "comtypes" ^
    --collect-submodules "PySide6" ^
    --exclude-module "tkinter" ^
    --exclude-module "matplotlib" ^
    --exclude-module "numpy" ^
    --exclude-module "scipy" ^
    main.py

if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed. Check output above.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  BUILD SUCCESSFUL!
echo.
echo  Output: dist\PhoneBackupManager\PhoneBackupManager.exe
echo ============================================================
echo.
pause
