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


def print_section(title):
    print()
    print("=" * 42)
    print(f"   {title}")
    print("=" * 42)


def print_kv(label, value):
    print(f"{label:<10} {value}")


def print_access_summary():
    print_section("Access")
    print_kv("Frontend:", f"http://localhost:{FRONTEND_PORT}")
    print_kv("Backend:", f"http://localhost:{BACKEND_PORT}")
    print_kv("API Docs:", f"http://localhost:{BACKEND_PORT}/docs")


def print_logs_summary():
    print_section("Logs")
    print_kv("Backend:", str(BACKEND_LOG_FILE))
    print_kv("Frontend:", str(FRONTEND_LOG_FILE))


def print_stop_summary(frontend_stopped, backend_stopped):
    print_section("Stopped")
    print_kv("Frontend:", "STOPPED" if frontend_stopped else "NOT RUNNING")
    print_kv("Backend:", "STOPPED" if backend_stopped else "NOT RUNNING")


def print_start_summary(backend_started, frontend_started):
    print_section("Started")
    print_kv("Backend:", "RUNNING" if backend_started else "FAILED")
    print_kv("Frontend:", "RUNNING" if frontend_started else "FAILED")


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


def tail_log(log_file, lines=20):
    """Return the last N lines of a log file."""
    if not log_file.exists():
        return ""

    content = log_file.read_text(errors="replace").splitlines()
    return "\n".join(content[-lines:])


def wait_for_service(port, process, log_file, name, timeout_seconds):
    """Wait until a service starts listening or its process exits."""
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        pid = get_pid_by_port(port)
        if pid:
            return pid

        if process.poll() is not None:
            break

        time.sleep(0.5)

    pid = get_pid_by_port(port)
    if pid:
        return pid

    print_error(f"Failed to start {name}. Check logs at {log_file}")
    log_tail = tail_log(log_file)
    if log_tail:
        print_error(f"Last {min(20, len(log_tail.splitlines()))} log lines:")
        print(log_tail)
    return None


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

    with open(BACKEND_LOG_FILE, "w") as log_file:
        if platform.system() == "Windows":
            process = subprocess.Popen(
                cmd,
                cwd=backend_dir,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=log_file,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            )
        else:
            process = subprocess.Popen(
                cmd,
                cwd=backend_dir,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=log_file,
                start_new_session=True
            )

    pid = wait_for_service(
        BACKEND_PORT,
        process,
        BACKEND_LOG_FILE,
        "backend",
        timeout_seconds=10,
    )
    if pid:
        print_info(f"Backend started successfully (PID: {pid})")
        return True
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

    with open(FRONTEND_LOG_FILE, "w") as log_file:
        if platform.system() == "Windows":
            process = subprocess.Popen(
                cmd,
                cwd=frontend_dir,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=log_file,
                shell=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            )
        else:
            process = subprocess.Popen(
                cmd,
                cwd=frontend_dir,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=log_file,
                shell=True,
                start_new_session=True
            )

    pid = wait_for_service(
        FRONTEND_PORT,
        process,
        FRONTEND_LOG_FILE,
        "frontend",
        timeout_seconds=15,
    )
    if pid:
        print_info(f"Frontend started successfully (PID: {pid})")
        return True
    return False


def show_status():
    """Show service status."""
    print_section("IoTDB Test Automation Platform Status")
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

    print_logs_summary()
    print_access_summary()
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
        print()
        print_info("Starting IoTDB Test Automation Platform...")
        backend_started = start_backend()
        frontend_started = start_frontend() if backend_started else False
        if backend_started and frontend_started:
            print_info("All services started!")
        else:
            print_error("Startup did not complete successfully")
        print_start_summary(backend_started, frontend_started)
        if backend_started and frontend_started:
            print_access_summary()
        print_logs_summary()
        sys.exit(0 if backend_started and frontend_started else 1)

    elif cmd == "stop":
        print()
        print_info("Stopping IoTDB Test Automation Platform...")
        frontend_stopped = stop_process(FRONTEND_PORT, "Frontend")
        backend_stopped = stop_process(BACKEND_PORT, "Backend")
        print_info("All services stopped")
        print_stop_summary(frontend_stopped, backend_stopped)
        print_logs_summary()
        print()

    elif cmd == "restart":
        print()
        print_info("Stopping IoTDB Test Automation Platform...")
        frontend_stopped = stop_process(FRONTEND_PORT, "Frontend")
        backend_stopped = stop_process(BACKEND_PORT, "Backend")
        print_info("All services stopped")
        print_stop_summary(frontend_stopped, backend_stopped)
        print()
        time.sleep(2)
        print_info("Starting IoTDB Test Automation Platform...")
        backend_started = start_backend()
        frontend_started = start_frontend() if backend_started else False
        if backend_started and frontend_started:
            print_info("All services started!")
        else:
            print_error("Restart did not complete successfully")
        print_start_summary(backend_started, frontend_started)
        if backend_started and frontend_started:
            print_access_summary()
        print_logs_summary()
        sys.exit(0 if backend_started and frontend_started else 1)

    elif cmd == "status":
        show_status()

    elif cmd == "start-backend":
        print()
        start_backend()
        print()

    elif cmd == "stop-backend":
        print()
        stop_process(BACKEND_PORT, "Backend")
        print()

    elif cmd == "start-frontend":
        print()
        start_frontend()
        print()

    elif cmd == "stop-frontend":
        print()
        stop_process(FRONTEND_PORT, "Frontend")
        print()

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
