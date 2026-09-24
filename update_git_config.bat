@echo off
echo =========================================
echo       Update Global Git Configuration
echo =========================================
echo.

echo Please select a profile:
echo [1] joyrocks93
echo [2] botbros2025
echo.
set /p choice="Enter your choice (1 or 2): "

if "%choice%"=="1" (
    set git_username=joyrocks93
    set git_email=iamstjt93@gmail.com
) else if "%choice%"=="2" (
    set git_username=botbros2025
    set git_email=botbros2025@example.com
) else (
    echo Invalid choice. Exiting...
    pause
    exit /b
)

echo.
echo Updating configuration...
git config --global user.name "%git_username%"
git config --global user.email "%git_email%"

echo.
echo =========================================
echo Global Git configuration updated!
echo New Username : %git_username%
echo New Email    : %git_email%
echo =========================================
pause
