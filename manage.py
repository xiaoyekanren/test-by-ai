#!/usr/bin/env python3
"""
IoTDB Test Automation Platform - Service Management Script
Usage: python manage.py {start|stop|restart|status}
"""

import os
import sys
import subprocess
import time
import signal
import platform
from pathlib import Path

# Configuration
BACKEND_PORT = 8000
FRONTEND_PORT = 5173
PID_DIR = Path("data/pids")
LOG_DIR = Path("data/logs")

BACKEND_PID_FILE = PID_DIR / "backend.pid"
FRONTEND_PID_FILE = PID_DIR / "frontend.pid"
BACKEND_LOG_FILE = LOG_DIR / "backend.log"
FRONTEND_LOG_FILE = LOG_DIR / "frontend.log"


def ensure_dirs():
    """Create necessary directories."""
    PID_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def print_info(msg):
    print(f"[INFO] {msg}")


def print_warn(msg):
    print(f"[WARN] {msg}")


def print_error(msg):
    print(f"[ERROR] {msg}")


def get_pid_by_port(port):
    """Get process PID listening on the given port."""
    system = platform.system()

    if system == "Windows":
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if "LISTENING" in line and f":{port}" in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        return int(parts[-1])
        except Exception:
            pass
    else:  # Linux/Mac
        try:
            result = subprocess.run(
                ["lsof", "-i", f":{port}", "-t"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                return int(result.stdout.strip().split()[0])
        except Exception:
            pass

    return None


def is_running(port):
    """Check if service is running on the given port."""
    return get_pid_by_port(port) is not None


def stop_process(port, name):
    """Stop process by port."""
    pid = get_pid_by_port(port)
    if pid is None:
        print_warn(f"{name} is not running")
        return False

    print_info(f"Stopping {name} (PID: {pid})...")

    system = platform.system()
    try:
        if system == "Windows":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                           capture_output=True, timeout=10)
        else:
            os.kill(pid, signal.SIGKILL)
        print_info(f"{name} stopped")
        return True
    except Exception as e:
        print_error(f"Failed to stop {name}: {e}")
        return False


def start_backend():
    """Start backend server."""
    if is_running(BACKEND_PORT):
        pid = get_pid_by_port(BACKEND_PORT)
        print_warn(f"Backend is already running (PID: {pid})")
        return True

    print_info(f"Starting backend server on port {BACKEND_PORT}...")

    backend_dir = Path("backend")
    if not backend_dir.exists():
        print_error("Backend directory not found")
        return False

    cmd = [
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", "0.0.0.0",
        "--port", str(BACKEND_PORT)
    ]

    log_file = open(BACKEND_LOG_FILE, "w")

    if platform.system() == "Windows":
        # Use CREATE_NEW_PROCESS_GROUP to detach from console
        subprocess.Popen(
            cmd,
            cwd=backend_dir,
            stdout=log_file,
            stderr=log_file,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        subprocess.Popen(
            cmd,
            cwd=backend_dir,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True
        )

    # Wait and check
    time.sleep(3)
    pid = get_pid_by_port(BACKEND_PORT)
    if pid:
        print_info(f"Backend started successfully (PID: {pid})")
        print_info(f"API docs: http://localhost:{BACKEND_PORT}/docs")
        return True
    else:
        print_error(f"Failed to start backend. Check logs at {BACKEND_LOG_FILE}")
        return False


def start_frontend():
    """Start frontend server."""
    if is_running(FRONTEND_PORT):
        pid = get_pid_by_port(FRONTEND_PORT)
        print_warn(f"Frontend is already running (PID: {pid})")
        return True

    print_info(f"Starting frontend server on port {FRONTEND_PORT}...")

    frontend_dir = Path("frontend")
    if not frontend_dir.exists():
        print_error("Frontend directory not found")
        return False

    cmd = "npm run dev -- --port " + str(FRONTEND_PORT)

    log_file = open(FRONTEND_LOG_FILE, "w")

    if platform.system() == "Windows":
        subprocess.Popen(
            cmd,
            cwd=frontend_dir,
            stdout=log_file,
            stderr=log_file,
            shell=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        subprocess.Popen(
            cmd,
            cwd=frontend_dir,
            stdout=log_file,
            stderr=log_file,
            shell=True,
            start_new_session=True
        )

    # Wait and check
    time.sleep(5)
    pid = get_pid_by_port(FRONTEND_PORT)
    if pid:
        print_info(f"Frontend started successfully (PID: {pid})")
        print_info(f"Application: http://localhost:{FRONTEND_PORT}")
        return True
    else:
        print_error(f"Failed to start frontend. Check logs at {FRONTEND_LOG_FILE}")
        return False


def show_status():
    """Show service status."""
    print()
    print("=" * 42)
    print("   IoTDB Test Automation Platform Status")
    print("=" * 42)
    print()

    backend_pid = get_pid_by_port(BACKEND_PORT)
    if backend_pid:
        print(f"Backend:  [RUNNING] (PID: {backend_pid}, Port: {BACKEND_PORT})")
    else:
        print("Backend:  [STOPPED]")

    frontend_pid = get_pid_by_port(FRONTEND_PORT)
    if frontend_pid:
        print(f"Frontend: [RUNNING] (PID: {frontend_pid}, Port: {FRONTEND_PORT})")
    else:
        print("Frontend: [STOPPED]")

    print()
    print("Logs:")
    print(f"  Backend:  {BACKEND_LOG_FILE}")
    print(f"  Frontend: {FRONTEND_LOG_FILE}")
    print()


def show_logs(service):
    """Show service logs."""
    if service == "backend":
        log_file = BACKEND_LOG_FILE
    elif service == "frontend":
        log_file = FRONTEND_LOG_FILE
    else:
        print_error(f"Unknown service: {service}")
        return

    if log_file.exists():
        print(f"{service} logs:")
        print(log_file.read_text())
    else:
        print_error("No log file found")


def show_help():
    """Show help message."""
    print("IoTDB Test Automation Platform - Service Management")
    print()
    print("Usage: python manage.py {start|stop|restart|status}")
    print()
    print("Commands:")
    print("  start           Start all services (backend + frontend)")
    print("  stop            Stop all services")
    print("  restart         Restart all services")
    print("  status          Show service status")
    print()
    print("  start-backend   Start only backend server")
    print("  stop-backend    Stop only backend server")
    print("  start-frontend  Start only frontend server")
    print("  stop-frontend   Stop only frontend server")
    print()
    print("  logs            Show backend logs")
    print("  logs-frontend   Show frontend logs")
    print()
    print(f"Access URLs:")
    print(f"  Frontend:  http://localhost:{FRONTEND_PORT}")
    print(f"  Backend:   http://localhost:{BACKEND_PORT}")
    print(f"  API Docs:  http://localhost:{BACKEND_PORT}/docs")


def main():
    ensure_dirs()

    if len(sys.argv) < 2:
        show_help()
        return

    cmd = sys.argv[1].lower()

    if cmd == "start":
        print_info("Starting IoTDB Test Automation Platform...")
        start_backend()
        start_frontend()
        print_info("All services started!")
        show_status()

    elif cmd == "stop":
        print_info("Stopping IoTDB Test Automation Platform...")
        stop_process(FRONTEND_PORT, "Frontend")
        stop_process(BACKEND_PORT, "Backend")
        print_info("All services stopped")

    elif cmd == "restart":
        print_info("Stopping IoTDB Test Automation Platform...")
        stop_process(FRONTEND_PORT, "Frontend")
        stop_process(BACKEND_PORT, "Backend")
        print_info("All services stopped")
        time.sleep(2)
        print_info("Starting IoTDB Test Automation Platform...")
        start_backend()
        start_frontend()
        print_info("All services started!")
        show_status()

    elif cmd == "status":
        show_status()

    elif cmd == "start-backend":
        start_backend()

    elif cmd == "stop-backend":
        stop_process(BACKEND_PORT, "Backend")

    elif cmd == "start-frontend":
        start_frontend()

    elif cmd == "stop-frontend":
        stop_process(FRONTEND_PORT, "Frontend")

    elif cmd == "logs":
        show_logs("backend")

    elif cmd == "logs-frontend":
        show_logs("frontend")

    elif cmd in ("--help", "-h", "help"):
        show_help()

    else:
        print_error(f"Unknown command: {cmd}")
        show_help()


if __name__ == "__main__":
    main()