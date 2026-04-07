#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
REQUIREMENTS_FILE="$SCRIPT_DIR/backend/requirements.txt"
PIP_LOG_FILE="$SCRIPT_DIR/data/logs/pip-sync.log"

cd "$SCRIPT_DIR"

COMMAND="${1:-}"

needs_runtime_sync=false
case "$COMMAND" in
    start|restart|start-backend|"")
        needs_runtime_sync=true
        ;;
esac

if [ "$needs_runtime_sync" = true ]; then
    if [ ! -d "$VENV_DIR" ]; then
        echo "Virtual environment not found. Creating venv..."
        python3 -m venv "$VENV_DIR"
    fi

    if [ ! -f "$REQUIREMENTS_FILE" ]; then
        echo "Missing requirements file: $REQUIREMENTS_FILE" >&2
        exit 1
    fi

    mkdir -p "$SCRIPT_DIR/data/logs"
    echo
    echo "=========================================="
    echo "   Runtime Sync"
    echo "=========================================="
    echo "Requirements: $REQUIREMENTS_FILE"
    echo "Log File:     $PIP_LOG_FILE"
    echo

    echo "[INFO] Checking pip..."
    if ! "$VENV_DIR/bin/python" -m pip install --disable-pip-version-check --upgrade pip >"$PIP_LOG_FILE" 2>&1; then
        echo "Failed to upgrade pip. Full output:" >&2
        cat "$PIP_LOG_FILE" >&2
        exit 1
    fi

    echo "[INFO] Syncing backend dependencies..."
    if ! "$VENV_DIR/bin/python" -m pip install --disable-pip-version-check -r "$REQUIREMENTS_FILE" >>"$PIP_LOG_FILE" 2>&1; then
        echo "Failed to sync backend dependencies. Full output:" >&2
        cat "$PIP_LOG_FILE" >&2
        exit 1
    fi

    echo "[INFO] Dependency sync complete"
fi

exec "$VENV_DIR/bin/python" manage.py "$@"
