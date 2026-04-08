#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
PYTHON_MIN_VERSION="3.10"
NODE_MIN_MAJOR=18

cd "$SCRIPT_DIR"

COMMAND="${1:-}"

get_python_cmd() {
    if [ -n "${PYTHON_BIN:-}" ]; then
        if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
            echo "Configured PYTHON_BIN is not available: $PYTHON_BIN" >&2
            return 1
        fi
        if "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
            command -v "$PYTHON_BIN"
            return 0
        fi
        echo "Python $PYTHON_MIN_VERSION+ is required, but PYTHON_BIN=$PYTHON_BIN is too old." >&2
        return 1
    fi

    for candidate in python3 python; do
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

check_node_runtime() {
    if ! command -v node >/dev/null 2>&1; then
        echo "Node.js $NODE_MIN_MAJOR+ is required. Please install Node.js first." >&2
        return 1
    fi

    if ! command -v npm >/dev/null 2>&1; then
        echo "npm is required. Please install npm with Node.js first." >&2
        return 1
    fi

    local node_major
    node_major="$(node -p 'Number(process.versions.node.split(".")[0])' 2>/dev/null || true)"
    if [ -z "$node_major" ] || [ "$node_major" -lt "$NODE_MIN_MAJOR" ]; then
        echo "Node.js $NODE_MIN_MAJOR+ is required. Current version: $(node -v 2>/dev/null || echo unknown)" >&2
        return 1
    fi
}

ensure_venv() {
    if [ -x "$VENV_DIR/bin/python" ]; then
        if ! "$VENV_DIR/bin/python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
            echo "Python $PYTHON_MIN_VERSION+ is required, but the existing venv is too old: $("$VENV_DIR/bin/python" --version 2>&1)" >&2
            return 1
        fi
        return 0
    fi

    echo "Virtual environment not found. Creating venv..."
    local python_runner
    python_runner="$(get_python_cmd)"
    "$python_runner" -m venv "$VENV_DIR"
}

case "$COMMAND" in
    install|start|restart|check)
        check_node_runtime
        ;;
esac

case "$COMMAND" in
    install|start|restart)
        ensure_venv
        PYTHON_RUNNER="$VENV_DIR/bin/python"
        ;;
    *)
        if [ -x "$VENV_DIR/bin/python" ]; then
            ensure_venv
            PYTHON_RUNNER="$VENV_DIR/bin/python"
        else
            PYTHON_RUNNER="$(get_python_cmd)"
        fi
        ;;
esac

exec "$PYTHON_RUNNER" manage.py "$@"
