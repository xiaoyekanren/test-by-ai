@echo off
setlocal

set SCRIPT_DIR=%~dp0
set VENV_DIR=%SCRIPT_DIR%venv

REM Check if venv exists, create if not
if not exist "%VENV_DIR%" (
    echo Virtual environment not found. Creating venv...
    python -m venv "%VENV_DIR%"
    echo Installing dependencies...
    if exist "%SCRIPT_DIR%requirements.txt" (
        "%VENV_DIR%\Scripts\pip.exe" install -r "%SCRIPT_DIR%requirements.txt"
    ) else (
        echo No requirements.txt found, skipping dependency installation.
    )
)

REM Activate venv and run
call "%VENV_DIR%\Scripts\activate.bat"
python manage.py %*