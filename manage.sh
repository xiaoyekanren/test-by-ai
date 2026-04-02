#!/bin/bash

# IoTDB Test Automation Platform - Service Management Script
# Usage: ./manage.sh {start|stop|restart|status|--help}

set -e

# Configuration
BACKEND_PORT=8000
FRONTEND_PORT=5173
PID_DIR="./data/pids"
LOG_DIR="./data/logs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create directories if not exist
mkdir -p "$PID_DIR" "$LOG_DIR"

# PID files
BACKEND_PID="$PID_DIR/backend.pid"
FRONTEND_PID="$PID_DIR/frontend.pid"

# Log files
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    echo "IoTDB Test Automation Platform - Service Management"
    echo ""
    echo "Usage: $0 {start|stop|restart|status}"
    echo ""
    echo "Commands:"
    echo "  start           Start all services (backend + frontend)"
    echo "  stop            Stop all services"
    echo "  restart         Restart all services"
    echo "  status          Show service status"
    echo ""
    echo "  start-backend   Start only backend server"
    echo "  stop-backend    Stop only backend server"
    echo "  start-frontend  Start only frontend server"
    echo "  stop-frontend   Stop only frontend server"
    echo ""
    echo "  logs            Follow backend logs (Ctrl+C to exit)"
    echo "  logs-frontend   Follow frontend logs (Ctrl+C to exit)"
    echo ""
    echo "Configuration:"
    echo "  Backend Port:   $BACKEND_PORT"
    echo "  Frontend Port:  $FRONTEND_PORT"
    echo "  PID Directory:  $PID_DIR"
    echo "  Log Directory:  $LOG_DIR"
    echo ""
    echo "Examples:"
    echo "  $0 start              # Start the platform"
    echo "  $0 status             # Check if services are running"
    echo "  $0 restart            # Restart all services"
    echo "  $0 logs               # View backend logs in real-time"
    echo ""
    echo "Access URLs:"
    echo "  Frontend:  http://localhost:$FRONTEND_PORT"
    echo "  Backend:   http://localhost:$BACKEND_PORT"
    echo "  API Docs:  http://localhost:$BACKEND_PORT/docs"
}

check_process() {
    local pid_file=$1
    local name=$2

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0  # Running
        else
            rm -f "$pid_file"
            return 1  # Not running (stale PID)
        fi
    fi
    return 1  # Not running
}

start_backend() {
    if check_process "$BACKEND_PID" "backend"; then
        print_warning "Backend is already running (PID: $(cat $BACKEND_PID))"
        return 0
    fi

    print_status "Starting backend server on port $BACKEND_PORT..."
    cd backend
    python3 -m uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT > "../$BACKEND_LOG" 2>&1 &
    echo $! > "../$BACKEND_PID"
    cd ..

    sleep 2

    if check_process "$BACKEND_PID" "backend"; then
        print_status "Backend started successfully (PID: $(cat $BACKEND_PID))"
        print_status "API docs: http://localhost:$BACKEND_PORT/docs"
    else
        print_error "Failed to start backend. Check logs at $BACKEND_LOG"
        return 1
    fi
}

start_frontend() {
    if check_process "$FRONTEND_PID" "frontend"; then
        print_warning "Frontend is already running (PID: $(cat $FRONTEND_PID))"
        return 0
    fi

    print_status "Starting frontend server on port $FRONTEND_PORT..."
    cd frontend
    npm run dev -- --port $FRONTEND_PORT > "../$FRONTEND_LOG" 2>&1 &
    echo $! > "../$FRONTEND_PID"
    cd ..

    sleep 3

    if check_process "$FRONTEND_PID" "frontend"; then
        print_status "Frontend started successfully (PID: $(cat $FRONTEND_PID))"
        print_status "Application: http://localhost:$FRONTEND_PORT"
    else
        print_error "Failed to start frontend. Check logs at $FRONTEND_LOG"
        return 1
    fi
}

stop_backend() {
    if ! check_process "$BACKEND_PID" "backend"; then
        print_warning "Backend is not running"
        return 0
    fi

    local pid=$(cat "$BACKEND_PID")
    print_status "Stopping backend (PID: $pid)..."
    kill "$pid" 2>/dev/null || true

    # Wait for process to stop
    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done

    if ps -p "$pid" > /dev/null 2>&1; then
        print_warning "Force killing backend..."
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$BACKEND_PID"
    print_status "Backend stopped"
}

stop_frontend() {
    if ! check_process "$FRONTEND_PID" "frontend"; then
        print_warning "Frontend is not running"
        return 0
    fi

    local pid=$(cat "$FRONTEND_PID")
    print_status "Stopping frontend (PID: $pid)..."
    kill "$pid" 2>/dev/null || true

    # Also kill any node processes running vite on the port
    pkill -f "vite.*$FRONTEND_PORT" 2>/dev/null || true

    # Wait for process to stop
    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done

    if ps -p "$pid" > /dev/null 2>&1; then
        print_warning "Force killing frontend..."
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$FRONTEND_PID"
    print_status "Frontend stopped"
}

show_status() {
    echo ""
    echo "=========================================="
    echo "   IoTDB Test Automation Platform Status"
    echo "=========================================="
    echo ""

    # Backend status
    if check_process "$BACKEND_PID" "backend"; then
        echo -e "Backend:  ${GREEN}Running${NC} (PID: $(cat $BACKEND_PID), Port: $BACKEND_PORT)"
    else
        echo -e "Backend:  ${RED}Stopped${NC}"
    fi

    # Frontend status
    if check_process "$FRONTEND_PID" "frontend"; then
        echo -e "Frontend: ${GREEN}Running${NC} (PID: $(cat $FRONTEND_PID), Port: $FRONTEND_PORT)"
    else
        echo -e "Frontend: ${RED}Stopped${NC}"
    fi

    echo ""
    echo "Logs:"
    echo "  Backend:  $BACKEND_LOG"
    echo "  Frontend: $FRONTEND_LOG"
    echo ""
}

start_all() {
    print_status "Starting IoTDB Test Automation Platform..."
    start_backend
    start_frontend
    print_status "All services started!"
    show_status
}

stop_all() {
    print_status "Stopping IoTDB Test Automation Platform..."
    stop_frontend
    stop_backend
    print_status "All services stopped"
}

# Main command dispatch
case "${1:-}" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        stop_all
        echo ""
        sleep 2
        start_all
        ;;
    status)
        show_status
        ;;
    start-backend)
        start_backend
        ;;
    stop-backend)
        stop_backend
        ;;
    start-frontend)
        start_frontend
        ;;
    stop-frontend)
        stop_frontend
        ;;
    logs)
        echo "Backend logs (Ctrl+C to exit):"
        tail -f "$BACKEND_LOG"
        ;;
    logs-frontend)
        echo "Frontend logs (Ctrl+C to exit):"
        tail -f "$FRONTEND_LOG"
        ;;
    --help|-h|help)
        show_help
        exit 0
        ;;
    *)
        show_help
        exit 1
        ;;
esac

exit 0