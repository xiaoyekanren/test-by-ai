@echo off
setlocal enabledelayedexpansion

REM IoTDB Test Automation Platform - Service Management Script (Windows)
REM Usage: manage.bat {start|stop|restart|status|--help}

REM Configuration
set BACKEND_PORT=8000
set FRONTEND_PORT=5173
set PID_DIR=.\data\pids
set LOG_DIR=.\data\logs

REM Create directories if not exist
if not exist "%PID_DIR%" mkdir "%PID_DIR%"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM PID files
set BACKEND_PID=%PID_DIR%\backend.pid
set FRONTEND_PID=%PID_DIR%\frontend.pid

REM Log files
set BACKEND_LOG=%LOG_DIR%\backend.log
set FRONTEND_LOG=%LOG_DIR%\frontend.log

REM Parse command
set CMD=%~1

if "%CMD%"=="" goto :show_help
if "%CMD%"=="start" goto :start_all
if "%CMD%"=="stop" goto :stop_all
if "%CMD%"=="restart" goto :restart_all
if "%CMD%"=="status" goto :show_status
if "%CMD%"=="start-backend" goto :start_backend
if "%CMD%"=="stop-backend" goto :stop_backend
if "%CMD%"=="start-frontend" goto :start_frontend
if "%CMD%"=="stop-frontend" goto :stop_frontend
if "%CMD%"=="logs" goto :logs_backend
if "%CMD%"=="logs-frontend" goto :logs_frontend
if "%CMD%"=="--help" goto :show_help
if "%CMD%"=="-h" goto :show_help
if "%CMD%"=="help" goto :show_help
goto :show_help

:print_info
echo [INFO] %~1
goto :eof

:print_warn
echo [WARN] %~1
goto :eof

:print_error
echo [ERROR] %~1
goto :eof

:check_process
setlocal
set PID_FILE=%~1
if exist "%PID_FILE%" (
    set /p PID_VAL=<%PID_FILE%
    tasklist /FI "PID eq !PID_VAL!" 2>nul | find " !PID_VAL! " >nul
    if !errorlevel! equ 0 (
        endlocal
        exit /b 0
    ) else (
        del /f /q "%PID_FILE%" 2>nul
        endlocal
        exit /b 1
    )
)
endlocal
exit /b 1

:start_backend
call :check_process "%BACKEND_PID%"
if !errorlevel! equ 0 (
    set /p BPID=<%BACKEND_PID%
    call :print_warn "Backend is already running (PID: !BPID!)"
    goto :eof
)

call :print_info "Starting backend server on port %BACKEND_PORT%..."
cd backend

REM Check if Python is available
where python >nul 2>nul
if !errorlevel! neq 0 (
    call :print_error "Python not found in PATH"
    cd ..
    exit /b 1
)

REM Start backend in background
start /b cmd /c "python -m uvicorn app.main:app --host 0.0.0.0 --port %BACKEND_PORT% > ..\%BACKEND_LOG% 2>&1"

REM Wait a moment and get PID
timeout /t 2 /nobreak >nul

REM Find uvicorn process PID
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FO LIST ^| find "PID:"') do (
    set UVICORN_PID=%%a
)

if defined UVICORN_PID (
    echo !UVICORN_PID! > ..\%BACKEND_PID%
    call :print_info "Backend started successfully (PID: !UVICORN_PID!)"
    call :print_info "API docs: http://localhost:%BACKEND_PORT%/docs"
) else (
    call :print_error "Failed to start backend. Check logs at %BACKEND_LOG%"
)

cd ..
goto :eof

:start_frontend
call :check_process "%FRONTEND_PID%"
if !errorlevel! equ 0 (
    set /p FPID=<%FRONTEND_PID%
    call :print_warn "Frontend is already running (PID: !FPID!)"
    goto :eof
)

call :print_info "Starting frontend server on port %FRONTEND_PORT%..."
cd frontend

REM Check if npm is available
where npm >nul 2>nul
if !errorlevel! neq 0 (
    call :print_error "npm not found in PATH"
    cd ..
    exit /b 1
)

REM Start frontend in background
start /b cmd /c "npm run dev -- --port %FRONTEND_PORT% > ..\%FRONTEND_LOG% 2>&1"

REM Wait for frontend to start
timeout /t 3 /nobreak >nul

REM Find node process PID
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq node.exe" /FO LIST ^| find "PID:"') do (
    set NODE_PID=%%a
)

if defined NODE_PID (
    echo !NODE_PID! > ..\%FRONTEND_PID%
    call :print_info "Frontend started successfully (PID: !NODE_PID!)"
    call :print_info "Application: http://localhost:%FRONTEND_PORT%"
) else (
    call :print_error "Failed to start frontend. Check logs at %FRONTEND_LOG%"
)

cd ..
goto :eof

:stop_backend
call :check_process "%BACKEND_PID%"
if !errorlevel! neq 0 (
    call :print_warn "Backend is not running"
    goto :eof
)

set /p BPID=<%BACKEND_PID%
call :print_info "Stopping backend (PID: %BPID%)..."
taskkill /PID %BPID% /F >nul 2>nul
del /f /q "%BACKEND_PID%" 2>nul
call :print_info "Backend stopped"
goto :eof

:stop_frontend
call :check_process "%FRONTEND_PID%"
if !errorlevel! neq 0 (
    call :print_warn "Frontend is not running"
    goto :eof
)

set /p FPID=<%FRONTEND_PID%
call :print_info "Stopping frontend (PID: %FPID%)..."
taskkill /PID %FPID% /F >nul 2>nul

REM Also kill any node processes that might be vite
taskkill /FI "IMAGENAME eq node.exe" /F >nul 2>nul

del /f /q "%FRONTEND_PID%" 2>nul
call :print_info "Frontend stopped"
goto :eof

:start_all
call :print_info "Starting IoTDB Test Automation Platform..."
call :start_backend
call :start_frontend
call :print_info "All services started!"
call :show_status
goto :eof

:stop_all
call :print_info "Stopping IoTDB Test Automation Platform..."
call :stop_frontend
call :stop_backend
call :print_info "All services stopped"
goto :eof

:restart_all
call :stop_all
echo.
timeout /t 2 /nobreak >nul
call :start_all
goto :eof

:show_status
echo.
echo ==========================================
echo    IoTDB Test Automation Platform Status
echo ==========================================
echo.

REM Backend status
call :check_process "%BACKEND_PID%"
if !errorlevel! equ 0 (
    set /p BPID=<%BACKEND_PID%
    echo Backend:  [RUNNING] (PID: !BPID!, Port: %BACKEND_PORT%)
) else (
    echo Backend:  [STOPPED]
)

REM Frontend status
call :check_process "%FRONTEND_PID%"
if !errorlevel! equ 0 (
    set /p FPID=<%FRONTEND_PID%
    echo Frontend: [RUNNING] (PID: !FPID!, Port: %FRONTEND_PORT%)
) else (
    echo Frontend: [STOPPED]
)

echo.
echo Logs:
echo   Backend:  %BACKEND_LOG%
echo   Frontend: %FRONTEND_LOG%
echo.
goto :eof

:logs_backend
echo Backend logs (Ctrl+C to exit):
if exist "%BACKEND_LOG%" (
    type "%BACKEND_LOG%"
) else (
    echo No log file found
)
goto :eof

:logs_frontend
echo Frontend logs (Ctrl+C to exit):
if exist "%FRONTEND_LOG%" (
    type "%FRONTEND_LOG%"
) else (
    echo No log file found
)
goto :eof

:show_help
echo IoTDB Test Automation Platform - Service Management (Windows)
echo.
echo Usage: %~nx0 {start^|stop^|restart^|status}
echo.
echo Commands:
echo   start           Start all services (backend + frontend)
echo   stop            Stop all services
echo   restart         Restart all services
echo   status          Show service status
echo.
echo   start-backend   Start only backend server
echo   stop-backend    Stop only backend server
echo   start-frontend  Start only frontend server
echo   stop-frontend   Stop only frontend server
echo.
echo   logs            Show backend logs
echo   logs-frontend   Show frontend logs
echo.
echo Configuration:
echo   Backend Port:   %BACKEND_PORT%
echo   Frontend Port:  %FRONTEND_PORT%
echo   PID Directory:  %PID_DIR%
echo   Log Directory:  %LOG_DIR%
echo.
echo Examples:
echo   %~nx0 start              # Start the platform
echo   %~nx0 status             # Check if services are running
echo   %~nx0 restart            # Restart all services
echo.
echo Access URLs:
echo   Frontend:  http://localhost:%FRONTEND_PORT%
echo   Backend:   http://localhost:%BACKEND_PORT%
echo   API Docs:  http://localhost:%BACKEND_PORT%/docs
echo.
goto :eof

endlocal