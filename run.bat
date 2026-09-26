@echo off
setlocal
cd /d "%~dp0"

if exist "%~dp0BusinessLiteratureRadar.exe" (
    start "" "%~dp0BusinessLiteratureRadar.exe"
    exit /b 0
)

where pyw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pyw -3 "%~dp0app.py"
    exit /b 0
)

where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pythonw "%~dp0app.py"
    exit /b 0
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    python "%~dp0app.py"
    exit /b %errorlevel%
)

echo Python 3.10+ was not found. Download the Windows package with BusinessLiteratureRadar.exe, or install Python from https://www.python.org/downloads/ .
pause
exit /b 1
