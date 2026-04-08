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
import shutil
import hashlib
from pathlib import Path

# Configuration
BACKEND_PORT = 8000
FRONTEND_PORT = 5173
PID_DIR = Path("data/pids")
LOG_DIR = Path("data/logs")
DEP_STATE_DIR = Path("data/deps")
VENV_DIR = Path("venv")
REQUIREMENTS_FILE = Path("backend/requirements.txt")
FRONTEND_DIR = Path("frontend")
PACKAGE_JSON_FILE = FRONTEND_DIR / "package.json"
PACKAGE_LOCK_FILE = FRONTEND_DIR / "package-lock.json"
PIP_LOG_FILE = LOG_DIR / "pip-sync.log"
NPM_LOG_FILE = LOG_DIR / "npm-sync.log"
BACKEND_REQUIREMENTS_STAMP = DEP_STATE_DIR / "backend-requirements.sha256"
PYTHON_MIN_VERSION = (3, 10)
NODE_MIN_MAJOR = 18

BACKEND_PID_FILE = PID_DIR / "backend.pid"
FRONTEND_PID_FILE = PID_DIR / "frontend.pid"
BACKEND_LOG_FILE = LOG_DIR / "backend.log"
FRONTEND_LOG_FILE = LOG_DIR / "frontend.log"


def ensure_dirs():
    """Create necessary directories."""
    PID_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    DEP_STATE_DIR.mkdir(parents=True, exist_ok=True)


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


def venv_python_path():
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def is_running_from_venv():
    expected = venv_python_path()
    if not expected.exists():
        return False
    try:
        return Path(sys.executable).resolve() == expected.resolve()
    except OSError:
        return False


def prepare_subprocess_cmd(cmd):
    if platform.system() != "Windows" or not isinstance(cmd, (list, tuple)) or not cmd:
        return cmd

    executable = str(cmd[0])
    resolved = shutil.which(executable) or executable
    if Path(resolved).suffix.lower() in (".bat", ".cmd"):
        return ["cmd.exe", "/d", "/c", resolved, *[str(arg) for arg in cmd[1:]]]

    return [str(arg) for arg in cmd]


def run_logged(cmd, log_file, cwd=None):
    with open(log_file, "a") as output:
        return subprocess.run(prepare_subprocess_cmd(cmd), cwd=cwd, stdout=output, stderr=output)


def command_output(cmd, cwd=None):
    result = subprocess.run(
        prepare_subprocess_cmd(cmd),
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip() or result.stderr.strip()


def ensure_python_version():
    if sys.version_info < PYTHON_MIN_VERSION:
        required = ".".join(str(part) for part in PYTHON_MIN_VERSION)
        current = platform.python_version()
        print_error(f"Python {required}+ is required. Current version: {current}")
        sys.exit(1)


def check_node_runtime():
    node = shutil.which("node")
    npm = shutil.which("npm")

    if not node:
        print_error(f"Node.js {NODE_MIN_MAJOR}+ is required. Please install Node.js first.")
        sys.exit(1)
    if not npm:
        print_error("npm is required. Please install npm with Node.js first.")
        sys.exit(1)

    try:
        result = subprocess.run(
            [node, "-p", 'Number(process.versions.node.split(".")[0])'],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        node_major = int(result.stdout.strip())
    except Exception:
        node_major = 0

    if node_major < NODE_MIN_MAJOR:
        current = command_output([node, "-v"])
        print_error(f"Node.js {NODE_MIN_MAJOR}+ is required. Current version: {current or 'unknown'}")
        sys.exit(1)


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_venv_python():
    venv_python = venv_python_path()
    if venv_python.exists():
        result = subprocess.run(
            [
                str(venv_python),
                "-c",
                "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            current = command_output([str(venv_python), "--version"])
            print_error(f"Python 3.10+ is required, but the existing venv is too old: {current}")
            sys.exit(1)
        return venv_python

    print_error("Virtual environment not found. Run ./manage.sh install first.")
    sys.exit(1)


def backend_deps_need_sync(force=False):
    if force:
        return True
    if not REQUIREMENTS_FILE.exists():
        print_error(f"Missing requirements file: {REQUIREMENTS_FILE}")
        sys.exit(1)

    current_hash = file_sha256(REQUIREMENTS_FILE)
    if not BACKEND_REQUIREMENTS_STAMP.exists():
        return True
    return BACKEND_REQUIREMENTS_STAMP.read_text().strip() != current_hash


def mark_backend_deps_synced():
    DEP_STATE_DIR.mkdir(parents=True, exist_ok=True)
    BACKEND_REQUIREMENTS_STAMP.write_text(file_sha256(REQUIREMENTS_FILE) + "\n")


def sync_backend_deps(force=False):
    venv_python = get_venv_python()

    if not backend_deps_need_sync(force):
        print_info("Backend dependencies already installed")
        return venv_python

    ensure_dirs()
    PIP_LOG_FILE.write_text("")
    print_section("Backend Dependency Sync")
    print_kv("Python:", command_output([str(venv_python), "--version"]))
    print_kv("Requirements:", str(REQUIREMENTS_FILE))
    print_kv("Log File:", str(PIP_LOG_FILE))
    print()

    print_info("Checking pip...")
    result = run_logged(
        [str(venv_python), "-m", "pip", "install", "--disable-pip-version-check", "--upgrade", "pip"],
        PIP_LOG_FILE,
    )
    if result.returncode != 0:
        print_error("Failed to upgrade pip. Full output:")
        print(PIP_LOG_FILE.read_text(errors="replace"))
        sys.exit(1)

    print_info("Syncing backend dependencies...")
    result = run_logged(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            str(REQUIREMENTS_FILE),
        ],
        PIP_LOG_FILE,
    )
    if result.returncode != 0:
        print_error("Failed to sync backend dependencies. Full output:")
        print(PIP_LOG_FILE.read_text(errors="replace"))
        sys.exit(1)

    print_info("Backend dependency sync complete")
    mark_backend_deps_synced()
    return venv_python


def frontend_deps_need_sync(force=False):
    if force:
        return True
    node_modules = FRONTEND_DIR / "node_modules"
    package_lock_marker = node_modules / ".package-lock.json"
    if not node_modules.exists():
        return True
    if PACKAGE_LOCK_FILE.exists() and (
        not package_lock_marker.exists()
        or PACKAGE_LOCK_FILE.stat().st_mtime > package_lock_marker.stat().st_mtime
    ):
        return True
    if PACKAGE_JSON_FILE.stat().st_mtime > node_modules.stat().st_mtime:
        return True
    return False


def sync_frontend_deps(force=False):
    check_node_runtime()

    if not PACKAGE_JSON_FILE.exists():
        print_error(f"Missing package file: {PACKAGE_JSON_FILE}")
        sys.exit(1)

    if not frontend_deps_need_sync(force):
        print_info("Frontend dependencies already installed")
        return

    ensure_dirs()
    NPM_LOG_FILE.write_text("")
    print_section("Frontend Dependency Sync")
    print_kv("Node:", command_output(["node", "-v"]))
    print_kv("npm:", command_output(["npm", "-v"]))
    print_kv("Package:", str(PACKAGE_JSON_FILE))
    print_kv("Log File:", str(NPM_LOG_FILE))
    print()

    if PACKAGE_LOCK_FILE.exists():
        print_info("Installing frontend dependencies with npm ci...")
        cmd = ["npm", "ci"]
    else:
        print_info("Installing frontend dependencies with npm install...")
        cmd = ["npm", "install"]

    result = run_logged(cmd, NPM_LOG_FILE, cwd=FRONTEND_DIR)
    if result.returncode != 0:
        print_error("Failed to install frontend dependencies. Full output:")
        print(NPM_LOG_FILE.read_text(errors="replace"))
        sys.exit(1)

    print_info("Frontend dependency sync complete")


def sync_runtime_deps(cmd):
    if os.environ.get("MANAGE_DEPS_SYNCED") == "1":
        return

    needs_backend_sync = cmd in ("install", "start", "restart")
    needs_frontend_sync = cmd in ("install", "start", "restart")
    force_sync = cmd == "install"

    venv_python = None
    if needs_backend_sync:
        venv_python = sync_backend_deps(force=force_sync)
    if needs_frontend_sync:
        sync_frontend_deps(force=force_sync)

    if cmd == "install":
        print_section("Install Complete")
        launcher = ".\\manage.bat" if platform.system() == "Windows" else "./manage.sh"
        print(f"Run {launcher} start to start backend and frontend services.")
        sys.exit(0)

    if needs_backend_sync and venv_python and not is_running_from_venv():
        os.environ["MANAGE_DEPS_SYNCED"] = "1"
        os.execv(str(venv_python), [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]])


def check_path(path):
    return "OK" if path.exists() else "MISSING"


def get_node_major():
    try:
        result = subprocess.run(
            ["node", "-p", 'Number(process.versions.node.split(".")[0])'],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return int(result.stdout.strip())
    except Exception:
        return None


def show_check():
    print_section("Environment Check")

    python_version = command_output([sys.executable, "--version"])
    print_kv("Python:", python_version or "unknown")
    print_kv("Python exe:", sys.executable)

    venv_python = venv_python_path()
    if venv_python.exists():
        print_kv("Venv:", f"OK ({command_output([str(venv_python), '--version'])})")
    else:
        print_kv("Venv:", "MISSING")

    node = shutil.which("node")
    npm = shutil.which("npm")
    node_major = get_node_major() if node else None
    node_status = "OK" if node_major is not None and node_major >= NODE_MIN_MAJOR else "MISSING/TOO OLD"
    print_kv("Node:", f"{node_status} ({command_output(['node', '-v']) if node else 'not found'})")
    print_kv("npm:", f"OK ({command_output(['npm', '-v'])})" if npm else "MISSING")

    print_section("Project Files")
    print_kv("Backend:", check_path(Path("backend")))
    print_kv("Frontend:", check_path(FRONTEND_DIR))
    print_kv("Reqs:", check_path(REQUIREMENTS_FILE))
    print_kv("Package:", check_path(PACKAGE_JSON_FILE))
    print_kv("Lock:", check_path(PACKAGE_LOCK_FILE))

    print_section("Dependencies")
    if REQUIREMENTS_FILE.exists():
        print_kv("Backend:", "SYNCED" if not backend_deps_need_sync() else "NEEDS INSTALL")
    else:
        print_kv("Backend:", "MISSING REQUIREMENTS")
    if PACKAGE_JSON_FILE.exists():
        print_kv("Frontend:", "SYNCED" if not frontend_deps_need_sync() else "NEEDS INSTALL")
    else:
        print_kv("Frontend:", "MISSING PACKAGE")

    print_section("Ports")
    backend_pid = get_pid_by_port(BACKEND_PORT)
    frontend_pid = get_pid_by_port(FRONTEND_PORT)
    print_kv("Backend:", f"IN USE (PID: {backend_pid})" if backend_pid else "FREE")
    print_kv("Frontend:", f"IN USE (PID: {frontend_pid})" if frontend_pid else "FREE")


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
    print_kv("Frontend:", "STOPPED" if frontend_stopped else "FAILED")
    print_kv("Backend:", "STOPPED" if backend_stopped else "FAILED")


def print_start_summary(backend_started, frontend_started):
    print_section("Started")
    print_kv("Backend:", "RUNNING" if backend_started else "FAILED")
    print_kv("Frontend:", "RUNNING" if frontend_started else "FAILED")


def get_pids_by_port(port):
    """Get process PIDs listening on the given port."""
    system = platform.system()
    pids = []

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
                        pids.append(int(parts[-1]))
        except Exception:
            pass
    else:  # Linux/Mac
        try:
            result = subprocess.run(
                ["lsof", "-i", f":{port}", "-t"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                pids.extend(int(pid) for pid in result.stdout.strip().split())
        except Exception:
            pass

    return sorted(set(pids))


def get_pid_by_port(port):
    """Get one process PID listening on the given port."""
    pids = get_pids_by_port(port)
    return pids[0] if pids else None


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
    pids = get_pids_by_port(port)
    if not pids:
        print_warn(f"{name} is not running")
        return True

    print_info(f"Stopping {name} (PID: {', '.join(str(pid) for pid in pids)})...")

    system = platform.system()
    try:
        if system == "Windows":
            for pid in pids:
                subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                               capture_output=True, timeout=10)
        else:
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass

            deadline = time.time() + 5
            while time.time() < deadline:
                if not is_running(port):
                    print_info(f"{name} stopped")
                    return True
                time.sleep(0.2)

            for pid in get_pids_by_port(port):
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

        deadline = time.time() + 5
        while time.time() < deadline:
            if not is_running(port):
                print_info(f"{name} stopped")
                return True
            time.sleep(0.2)

        print_error(f"Failed to stop {name}: port {port} is still in use")
        return False
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

    cmd = f"npm run dev -- --host 0.0.0.0 --port {FRONTEND_PORT}"

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
    print("Usage: python manage.py {start|stop|restart|status|install|check}")
    print()
    print("Commands:")
    print("  start           Start all services (backend + frontend)")
    print("  stop            Stop all services")
    print("  restart         Restart all services")
    print("  status          Show service status")
    print("  install         Install backend and frontend dependencies")
    print("  check           Check runtimes, project files, dependencies, and ports")
    print()
    print(f"Access URLs:")
    print(f"  Frontend:  http://localhost:{FRONTEND_PORT}")
    print(f"  Backend:   http://localhost:{BACKEND_PORT}")
    print(f"  API Docs:  http://localhost:{BACKEND_PORT}/docs")


def main():
    os.chdir(Path(__file__).resolve().parent)
    ensure_python_version()
    ensure_dirs()

    if len(sys.argv) < 2:
        show_help()
        return

    cmd = sys.argv[1].lower()
    sync_runtime_deps(cmd)

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
        stop_process(FRONTEND_PORT, "Frontend")
        stop_process(BACKEND_PORT, "Backend")
        frontend_stopped = not is_running(FRONTEND_PORT)
        backend_stopped = not is_running(BACKEND_PORT)
        print_info("All services stopped")
        print_stop_summary(frontend_stopped, backend_stopped)
        print_logs_summary()
        print()

    elif cmd == "restart":
        print()
        print_info("Stopping IoTDB Test Automation Platform...")
        stop_process(FRONTEND_PORT, "Frontend")
        stop_process(BACKEND_PORT, "Backend")
        frontend_stopped = not is_running(FRONTEND_PORT)
        backend_stopped = not is_running(BACKEND_PORT)
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

    elif cmd == "check":
        show_check()

    elif cmd in ("--help", "-h", "help"):
        show_help()

    else:
        print_error(f"Unknown command: {cmd}")
        show_help()


if __name__ == "__main__":
    main()
