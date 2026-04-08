@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%venv"
set "PYTHON_MIN_VERSION=3.10"
set "NODE_MIN_MAJOR=18"
set "COMMAND=%~1"

cd /d "%SCRIPT_DIR%"

if /i "%COMMAND%"=="install" goto check_node
if /i "%COMMAND%"=="start" goto check_node
if /i "%COMMAND%"=="restart" goto check_node
if /i "%COMMAND%"=="check" goto check_node
goto choose_runner

:check_node
node -e "process.exit(Number(process.versions.node.split('.')[0]) >= 18 ? 0 : 1)" >nul 2>nul
if errorlevel 1 (
    echo Node.js %NODE_MIN_MAJOR%+ is required. Please install Node.js first.
    exit /b 1
)
npm -v >nul 2>nul
if errorlevel 1 (
    echo npm is required. Please install npm with Node.js first.
    exit /b 1
)
if /i "%COMMAND%"=="check" goto choose_runner

:ensure_venv
if exist "%VENV_DIR%\Scripts\python.exe" (
    "%VENV_DIR%\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if errorlevel 1 (
        echo Python %PYTHON_MIN_VERSION%+ is required, but the existing venv is too old.
        exit /b 1
    )
) else (
    if defined PYTHON_BIN (
        "%PYTHON_BIN%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
        if errorlevel 1 (
            echo Python %PYTHON_MIN_VERSION%+ is required, but PYTHON_BIN=%PYTHON_BIN% is not available or is too old.
            exit /b 1
        )
        set "PYTHON_CMD="%PYTHON_BIN%""
    ) else (
        set "PYTHON_CMD=python3"
        python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
        if errorlevel 1 (
            set "PYTHON_CMD=python"
            python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
            if errorlevel 1 (
                echo Python %PYTHON_MIN_VERSION%+ is required. Please install Python first.
                exit /b 1
            )
        )
    )
    echo Virtual environment not found. Creating venv...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 exit /b 1
)

"%VENV_DIR%\Scripts\python.exe" manage.py %*
exit /b %ERRORLEVEL%

:choose_runner
if exist "%VENV_DIR%\Scripts\python.exe" (
    "%VENV_DIR%\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if errorlevel 1 (
        echo Python %PYTHON_MIN_VERSION%+ is required, but the existing venv is too old.
        exit /b 1
    )
    "%VENV_DIR%\Scripts\python.exe" manage.py %*
    exit /b %ERRORLEVEL%
)

if defined PYTHON_BIN (
    "%PYTHON_BIN%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if errorlevel 1 (
        echo Python %PYTHON_MIN_VERSION%+ is required, but PYTHON_BIN=%PYTHON_BIN% is not available or is too old.
        exit /b 1
    )
    "%PYTHON_BIN%" manage.py %*
    exit /b %ERRORLEVEL%
)

python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 (
    python3 manage.py %*
    exit /b %ERRORLEVEL%
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 (
    python manage.py %*
    exit /b %ERRORLEVEL%
)

echo Python %PYTHON_MIN_VERSION%+ is required. Please install Python first.
exit /b 1
