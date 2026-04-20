#!/usr/bin/env python3
"""
IoTDB Test Automation Platform - Service Management Script
Usage: python manage.py {start|stop|restart|status|install|check|release}
"""

from __future__ import annotations

import os
import sys
import subprocess
import time
import signal
import platform
import shutil
import hashlib
from datetime import datetime
from pathlib import Path

# Configuration
PROJECT_NAME = "test-by-ai"
ROOT_DIR = Path(__file__).resolve().parent
BACKEND_PORT = 8000
FRONTEND_PORT = 5173
DATA_DIR = ROOT_DIR / "data"
PID_DIR = DATA_DIR / "pids"
LOG_DIR = DATA_DIR / "logs"
DEP_STATE_DIR = DATA_DIR / "deps"
VENV_DIR = ROOT_DIR / "venv"
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
RELEASE_DIR = ROOT_DIR / "release"
REQUIREMENTS_FILE = BACKEND_DIR / "requirements.txt"
RELEASE_LOG_FILE = LOG_DIR / "release.log"
RELEASE_BUNDLED_FRONTEND_DIR = Path("backend/app/frontend_dist")
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


RELEASE_RUNTIME_MANAGE = r'''#!/usr/bin/env python3
"""
IoTDB Test Automation Platform - Release Runtime Script
Usage: python manage.py {install|start|stop|restart|status|check}
"""

import os
import hashlib
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
BACKEND_PORT = 8000
PID_DIR = Path("data/pids")
LOG_DIR = Path("data/logs")
DEP_STATE_DIR = Path("data/deps")
VENV_DIR = Path("venv")
REQUIREMENTS_FILE = Path("backend/requirements.txt")
BACKEND_LOG_FILE = LOG_DIR / "backend.log"
BACKEND_REQUIREMENTS_STAMP = DEP_STATE_DIR / "backend-requirements.sha256"
PYTHON_MIN_VERSION = (3, 10)


def ensure_dirs():
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


def command_output(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    return result.stdout.strip() or result.stderr.strip()


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_python_version():
    if sys.version_info < PYTHON_MIN_VERSION:
        print_error(f"Python 3.10+ is required. Current version: {platform.python_version()}")
        sys.exit(1)


def get_venv_python():
    venv_python = venv_python_path()
    if venv_python.exists():
        return venv_python
    print_error("Virtual environment not found. Run ./manage.sh install first.")
    sys.exit(1)


def ensure_venv():
    venv_python = venv_python_path()
    if venv_python.exists():
        return

    print_info("Virtual environment not found. Creating venv...")
    result = subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)])
    if result.returncode != 0:
        sys.exit(result.returncode)


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
    ensure_venv()
    venv_python = get_venv_python()
    if not backend_deps_need_sync(force):
        print_info("Backend dependencies already installed")
        return

    print_section("Backend Dependency Install")
    print_kv("Python:", command_output([str(venv_python), "--version"]))
    print_kv("Requirements:", str(REQUIREMENTS_FILE))
    print()

    result = subprocess.run([
        str(venv_python),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "-r",
        str(REQUIREMENTS_FILE),
    ])
    if result.returncode != 0:
        sys.exit(result.returncode)

    mark_backend_deps_synced()
    print_info("Backend dependency install complete")


def install_deps():
    sync_backend_deps(force=True)
    print_section("Install Complete")
    print("Run ./manage.sh start to start the release server.")


def get_pids_by_port(port):
    system = platform.system()
    pids = []
    if system == "Windows":
        try:
            result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=5)
            for line in result.stdout.splitlines():
                if "LISTENING" in line and f":{port}" in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pids.append(int(parts[-1]))
        except Exception:
            pass
    else:
        try:
            result = subprocess.run(["lsof", "-i", f":{port}", "-t"], capture_output=True, text=True, timeout=5)
            if result.stdout.strip():
                pids.extend(int(pid) for pid in result.stdout.strip().split())
        except Exception:
            pass
    return sorted(set(pids))


def get_pid_by_port(port):
    pids = get_pids_by_port(port)
    return pids[0] if pids else None


def is_running(port):
    return get_pid_by_port(port) is not None


def tail_log(log_file, lines=20):
    if not log_file.exists():
        return ""
    return "\n".join(log_file.read_text(errors="replace").splitlines()[-lines:])


def wait_for_service(port, process, log_file, name, timeout_seconds):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        pid = get_pid_by_port(port)
        if pid:
            return pid
        if process.poll() is not None:
            break
        time.sleep(0.5)

    print_error(f"Failed to start {name}. Check logs at {log_file}")
    log_tail = tail_log(log_file)
    if log_tail:
        print_error("Last log lines:")
        print(log_tail)
    return None


def start_backend():
    if is_running(BACKEND_PORT):
        pid = get_pid_by_port(BACKEND_PORT)
        print_warn(f"Release server is already running (PID: {pid})")
        return True

    print_info(f"Starting release server on port {BACKEND_PORT}...")
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(BACKEND_PORT),
    ]

    with open(BACKEND_LOG_FILE, "w") as log_file:
        if platform.system() == "Windows":
            process = subprocess.Popen(
                cmd,
                cwd=Path("backend"),
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=log_file,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            )
        else:
            process = subprocess.Popen(
                cmd,
                cwd=Path("backend"),
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=log_file,
                start_new_session=True,
            )

    pid = wait_for_service(BACKEND_PORT, process, BACKEND_LOG_FILE, "release server", 10)
    if pid:
        print_info(f"Release server started successfully (PID: {pid})")
        return True
    return False


def stop_backend():
    pids = get_pids_by_port(BACKEND_PORT)
    if not pids:
        print_warn("Release server is not running")
        return True

    print_info(f"Stopping release server (PID: {', '.join(str(pid) for pid in pids)})...")
    if platform.system() == "Windows":
        for pid in pids:
            subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"], capture_output=True, timeout=10)
    else:
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

    deadline = time.time() + 5
    while time.time() < deadline:
        if not is_running(BACKEND_PORT):
            print_info("Release server stopped")
            return True
        time.sleep(0.2)

    print_error(f"Failed to stop release server: port {BACKEND_PORT} is still in use")
    return False


def show_status():
    print_section("Release Status")
    pid = get_pid_by_port(BACKEND_PORT)
    if pid:
        print(f"Server: [RUNNING] (PID: {pid}, Port: {BACKEND_PORT})")
    else:
        print("Server: [STOPPED]")
    print_kv("App:", f"http://localhost:{BACKEND_PORT}")
    print_kv("API Docs:", f"http://localhost:{BACKEND_PORT}/docs")
    print_kv("Log:", str(BACKEND_LOG_FILE))


def show_check():
    print_section("Release Check")
    print_kv("Python:", command_output([sys.executable, "--version"]))
    print_kv("Python exe:", sys.executable)
    print_kv("Venv:", "OK" if venv_python_path().exists() else "MISSING")
    print_kv("Backend:", "OK" if Path("backend/app").exists() else "MISSING")
    print_kv("Frontend:", "BUNDLED" if Path("backend/app/frontend_dist/index.html").exists() else "MISSING")
    print_kv("Reqs:", "OK" if REQUIREMENTS_FILE.exists() else "MISSING")
    print_kv("Port:", f"IN USE (PID: {get_pid_by_port(BACKEND_PORT)})" if is_running(BACKEND_PORT) else "FREE")


def show_help():
    print("IoTDB Test Automation Platform - Release Runtime")
    print()
    print("Usage: python manage.py {install|start|stop|restart|status|check}")
    print()
    print("Commands:")
    print("  install         Install backend dependencies")
    print("  start           Start the release server")
    print("  stop            Stop the release server")
    print("  restart         Restart the release server")
    print("  status          Show release server status")
    print("  check           Check release files, runtime, and port")


def main():
    os.chdir(ROOT_DIR)
    ensure_python_version()
    ensure_dirs()

    if len(sys.argv) < 2:
        show_help()
        return

    cmd = sys.argv[1].lower()
    if cmd == "install":
        install_deps()
    elif cmd == "start":
        started = start_backend()
        show_status()
        sys.exit(0 if started else 1)
    elif cmd == "stop":
        stopped = stop_backend()
        sys.exit(0 if stopped else 1)
    elif cmd == "restart":
        stop_backend()
        time.sleep(2)
        started = start_backend()
        show_status()
        sys.exit(0 if started else 1)
    elif cmd == "status":
        show_status()
    elif cmd == "check":
        show_check()
    elif cmd in ("--help", "-h", "help"):
        show_help()
    else:
        print_error(f"Unknown command: {cmd}")
        show_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
'''

RELEASE_RUNTIME_SH = r'''#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
PYTHON_MIN_VERSION="3.10"

cd "$SCRIPT_DIR"

get_python_cmd() {
    if [ -n "${PYTHON_BIN:-}" ]; then
        if "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
            command -v "$PYTHON_BIN"
            return 0
        fi
        echo "Python $PYTHON_MIN_VERSION+ is required, but PYTHON_BIN=$PYTHON_BIN is unavailable or too old." >&2
        return 1
    fi

    for candidate in python3.12 python3 python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
                command -v "$candidate"
                return 0
            fi
        fi
    done

    echo "Python $PYTHON_MIN_VERSION+ is required. Please install Python first." >&2
    return 1
}

ensure_venv() {
    if [ -x "$VENV_DIR/bin/python" ]; then
        return 0
    fi

    echo "Virtual environment not found. Creating venv..."
    local python_runner
    python_runner="$(get_python_cmd)"
    "$python_runner" -m venv "$VENV_DIR"
}

case "${1:-}" in
    install|start|restart)
        ensure_venv
        PYTHON_RUNNER="$VENV_DIR/bin/python"
        ;;
    *)
        if [ -x "$VENV_DIR/bin/python" ]; then
            PYTHON_RUNNER="$VENV_DIR/bin/python"
        else
            PYTHON_RUNNER="$(get_python_cmd)"
        fi
        ;;
esac

exec "$PYTHON_RUNNER" manage.py "$@"
'''

RELEASE_RUNTIME_BAT = r'''@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%venv"
set "PYTHON_MIN_VERSION=3.10"

cd /d "%SCRIPT_DIR%"

if /i "%~1"=="install" goto ensure_venv
if /i "%~1"=="start" goto ensure_venv
if /i "%~1"=="restart" goto ensure_venv
goto choose_runner

:ensure_venv
if not exist "%VENV_DIR%\Scripts\python.exe" (
    call :find_python
    if errorlevel 1 exit /b 1
    echo Virtual environment not found. Creating venv...
    "!PYTHON_CMD!" -m venv "%VENV_DIR%"
    if errorlevel 1 exit /b 1
)
"%VENV_DIR%\Scripts\python.exe" manage.py %*
exit /b %ERRORLEVEL%

:choose_runner
if exist "%VENV_DIR%\Scripts\python.exe" (
    "%VENV_DIR%\Scripts\python.exe" manage.py %*
    exit /b %ERRORLEVEL%
)
if defined PYTHON_BIN (
    call :find_python
    if errorlevel 1 exit /b 1
    "!PYTHON_CMD!" manage.py %*
    exit /b %ERRORLEVEL%
)

call :find_python
if errorlevel 1 exit /b 1
"%PYTHON_CMD%" manage.py %*
exit /b %ERRORLEVEL%

:find_python
set "PYTHON_CMD="
if defined PYTHON_BIN (
    set "PYTHON_CMD=%PYTHON_BIN:"=%"
    if not defined PYTHON_CMD (
        echo Python %PYTHON_MIN_VERSION%+ is required, but PYTHON_BIN is empty.
        exit /b 1
    )
    "!PYTHON_CMD!" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if errorlevel 1 (
        echo Python %PYTHON_MIN_VERSION%+ is required, but PYTHON_BIN=%PYTHON_BIN% is not available or is too old.
        exit /b 1
    )
    exit /b 0
)

for %%P in (python3.12 python3 python) do (
    %%P -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=%%P"
        exit /b 0
    )
)

echo Python %PYTHON_MIN_VERSION%+ is required. Please install Python first.
exit /b 1
'''


def safe_package_component(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        print_error(f"Release {label} cannot be empty.")
        sys.exit(1)

    invalid_chars = '<>:"/\\|?*'
    sanitized = "".join("-" if char in invalid_chars or ord(char) < 32 else char for char in value)
    sanitized = sanitized.strip(" .")
    if not sanitized:
        print_error(f"Release {label} does not contain a valid file name component: {value}")
        sys.exit(1)
    return sanitized


def get_release_version(version: str | None = None) -> str:
    if version:
        return safe_package_component(version, "version")

    snapshot_date = datetime.now().strftime("%Y-%m-%d")
    return f"snapshot-{snapshot_date}"


def create_release_zip(release_path: Path) -> Path:
    zip_path = release_path.parent / f"{release_path.name}.zip"
    if zip_path.exists():
        zip_path.unlink()

    archive_base = zip_path.parent / zip_path.stem
    shutil.make_archive(
        str(archive_base),
        "zip",
        root_dir=release_path.parent,
        base_dir=release_path.name,
    )
    return zip_path


def ensure_project_files() -> None:
    required_paths = [
        BACKEND_DIR / "app",
        BACKEND_DIR / "requirements.txt",
        FRONTEND_DIR / "package.json",
        DATA_DIR / "app.db.example",
    ]
    missing = [path.relative_to(ROOT_DIR) for path in required_paths if not path.exists()]
    if missing:
        print_error("Release build is missing required files:")
        for path in missing:
            print(f"  - {path}")
        sys.exit(1)


def build_frontend() -> None:
    sync_frontend_deps()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    RELEASE_LOG_FILE.write_text("")

    print_section("Release Build")
    print_kv("Frontend:", str(FRONTEND_DIR.relative_to(ROOT_DIR)))
    print_kv("Log File:", str(RELEASE_LOG_FILE.relative_to(ROOT_DIR)))
    print()

    print_info("Building frontend release bundle...")
    result = run_logged(["npm", "run", "build"], RELEASE_LOG_FILE, cwd=FRONTEND_DIR)
    if result.returncode != 0:
        print_error("Failed to build frontend release bundle. Full output:")
        print(RELEASE_LOG_FILE.read_text(errors="replace"))
        sys.exit(1)

    dist_index = FRONTEND_DIR / "dist" / "index.html"
    if not dist_index.exists():
        print_error("Frontend build did not produce frontend/dist/index.html")
        sys.exit(1)

    print_info("Frontend release bundle complete")


def copy_release_path(source: Path, target: Path) -> None:
    if not source.exists():
        return

    if source.is_dir():
        shutil.copytree(
            source,
            target,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", ".DS_Store", ".pytest_cache", ".vscode", "node_modules"),
        )
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def write_text(path: Path, content: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, newline="\n")
    if executable and platform.system() != "Windows":
        path.chmod(path.stat().st_mode | 0o755)


def write_release_runtime(release_path: Path) -> None:
    write_text(release_path / "manage.py", RELEASE_RUNTIME_MANAGE, executable=True)
    write_text(release_path / "manage.sh", RELEASE_RUNTIME_SH, executable=True)
    write_text(release_path / "manage.bat", RELEASE_RUNTIME_BAT)


def write_release_readme(release_path: Path) -> None:
    content = f"""# IoTDB Test Automation Platform Release

This directory is a final release package generated from the source tree.

## Run

```bash
./manage.sh install
./manage.sh start
```

On Windows:

```bat
manage.bat install
manage.bat start
```

Then open:

- App: http://localhost:{BACKEND_PORT}
- API Docs: http://localhost:{BACKEND_PORT}/docs

## Commands

| Command | Description |
| --- | --- |
| `install` | Install backend dependencies into `venv/` |
| `start` | Start the release server |
| `stop` | Stop the release server |
| `restart` | Restart the release server |
| `status` | Show server status |
| `check` | Check release files, runtime, and port |

The frontend is prebuilt and bundled in `backend/app/frontend_dist/`.
"""
    write_text(release_path / "README.md", content)


def write_release_metadata(release_path: Path, version: str, zip_path: Path) -> None:
    branch = command_output(["git", "branch", "--show-current"], cwd=ROOT_DIR)
    commit = command_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT_DIR)
    dirty = bool(command_output(["git", "status", "--short"], cwd=ROOT_DIR))
    frontend_hash = file_tree_hash(FRONTEND_DIR / "dist")
    metadata = [
        f"created_at={datetime.now().isoformat(timespec='seconds')}",
        f"project={PROJECT_NAME}",
        f"version={version}",
        f"package_dir={release_path.name}",
        f"package_zip={zip_path.name}",
        f"branch={branch or 'unknown'}",
        f"commit={commit or 'unknown'}",
        f"dirty_worktree={str(dirty).lower()}",
        "package_type=backend-bundled-release",
        "includes_frontend_source=false",
        "includes_node_modules=false",
        "includes_data_app_db=true",
        "includes_data_app_db_example=false",
        f"frontend_bundle={RELEASE_BUNDLED_FRONTEND_DIR.as_posix()}",
        f"frontend_dist_sha256={frontend_hash}",
    ]
    write_text(release_path / "RELEASE_INFO.txt", "\n".join(metadata) + "\n")


def file_tree_hash(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        relative = path.relative_to(directory).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        with open(path, "rb") as input_file:
            for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def create_release(version: str | None = None) -> tuple[Path, Path]:
    ensure_python_version()
    ensure_project_files()
    build_frontend()

    release_version = get_release_version(version)
    package_name = f"{safe_package_component(PROJECT_NAME, 'project')}-{release_version}"
    release_path = RELEASE_DIR / package_name
    if release_path.exists():
        shutil.rmtree(release_path)
    release_path.mkdir(parents=True, exist_ok=True)

    copy_release_path(BACKEND_DIR / "app", release_path / "backend" / "app")
    copy_release_path(BACKEND_DIR / "requirements.txt", release_path / "backend" / "requirements.txt")
    copy_release_path(FRONTEND_DIR / "dist", release_path / RELEASE_BUNDLED_FRONTEND_DIR)
    copy_release_path(DATA_DIR / "app.db.example", release_path / "data" / "app.db")

    for dirname in ("logs", "pids"):
        (release_path / "data" / dirname).mkdir(parents=True, exist_ok=True)

    write_release_runtime(release_path)
    write_release_readme(release_path)
    zip_path = release_path.parent / f"{release_path.name}.zip"
    write_release_metadata(release_path, release_version, zip_path)
    zip_path = create_release_zip(release_path)

    print_section("Release Ready")
    print_kv("Directory:", str(release_path.relative_to(ROOT_DIR)))
    print_kv("Zip:", str(zip_path.relative_to(ROOT_DIR)))
    print_kv("Version:", release_version)
    print_kv("Frontend:", "bundled into backend")
    print_kv("Data:", "app.db included")
    print()
    print(f"Run ./manage.sh install and ./manage.sh start inside {release_path.relative_to(ROOT_DIR)}.")
    return release_path, zip_path


def show_help():
    """Show help message."""
    print("IoTDB Test Automation Platform - Service Management")
    print()
    print("Usage: python manage.py {start|stop|restart|status|install|check|release}")
    print()
    print("Commands:")
    print("  start           Start all services (backend + frontend)")
    print("  stop            Stop all services")
    print("  restart         Restart all services")
    print("  status          Show service status")
    print("  install         Install backend and frontend dependencies")
    print("  check           Check runtimes, project files, dependencies, and ports")
    print("  release         Build a final release package, defaulting to snapshot-YYYY-MM-DD")
    print("                  Optional: python manage.py release --version 0.1.0")
    print()
    print(f"Access URLs:")
    print(f"  Frontend:  http://localhost:{FRONTEND_PORT}")
    print(f"  Backend:   http://localhost:{BACKEND_PORT}")
    print(f"  API Docs:  http://localhost:{BACKEND_PORT}/docs")


def main():
    os.chdir(ROOT_DIR)
    ensure_python_version()
    ensure_dirs()

    if len(sys.argv) < 2:
        show_help()
        return

    cmd = sys.argv[1].lower()
    if cmd == "release":
        release_args = sys.argv[2:]
        version = None
        if release_args:
            if len(release_args) == 2 and release_args[0] == "--version":
                version = release_args[1]
            else:
                print_error("Usage: python manage.py release [--version VERSION]")
                sys.exit(1)
        create_release(version)
        return

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
