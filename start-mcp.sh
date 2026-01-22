#!/bin/bash

# Start All MCP Servers
# This script starts all MCP servers in the background

set -e

echo "========================================"
echo "MCP Servers - Startup Script"
echo "========================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Log directory
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

# PID file to track running servers
PID_FILE="$LOG_DIR/mcp_servers.pid"

# MCP Server configurations
declare -A MCP_SERVERS
MCP_SERVERS["google-calendar"]="mcp_servers/google_calendar/server.py:8010"
MCP_SERVERS["youtube-music"]="mcp_servers/youtube_music/server.py:8011"
MCP_SERVERS["weather"]="mcp_servers/weather/server.py:8012"
MCP_SERVERS["browser"]="mcp_servers/browser/server.py:8013"
MCP_SERVERS["computer"]="mcp_servers/computer/server.py:8014"
MCP_SERVERS["filesystem"]="mcp_servers/filesystem/server.py:8015"
# browser-use is now a built-in tool, not an MCP server

# Function to check if a port is in use
check_port() {
    local port=$1
    if command -v lsof &> /dev/null; then
        lsof -i :$port &> /dev/null && return 0 || return 1
    elif command -v netstat &> /dev/null; then
        netstat -tuln 2>/dev/null | grep -q ":$port " && return 0 || return 1
    elif command -v ss &> /dev/null; then
        ss -tuln 2>/dev/null | grep -q ":$port " && return 0 || return 1
    fi
    return 1
}

# Function to stop all MCP servers
stop_servers() {
    echo ""
    echo -e "${YELLOW}Stopping MCP servers...${NC}"

    if [ -f "$PID_FILE" ]; then
        while read -r line; do
            name=$(echo "$line" | cut -d: -f1)
            pid=$(echo "$line" | cut -d: -f2)
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null
                echo -e "  ${GREEN}Stopped${NC} $name (PID: $pid)"
            fi
        done < "$PID_FILE"
        rm -f "$PID_FILE"
    fi

    echo -e "${GREEN}All MCP servers stopped${NC}"
    exit 0
}

# Function to show status of servers
show_status() {
    echo ""
    echo "MCP Server Status:"
    echo "----------------------------------------"
    for name in "${!MCP_SERVERS[@]}"; do
        config="${MCP_SERVERS[$name]}"
        port="${config##*:}"

        if check_port "$port"; then
            echo -e "  ${GREEN}[RUNNING]${NC} $name - http://localhost:$port"
        else
            echo -e "  ${RED}[STOPPED]${NC} $name - port $port"
        fi
    done
    echo "----------------------------------------"
}

# Parse command line arguments
case "${1:-}" in
    stop)
        stop_servers
        ;;
    status)
        show_status
        exit 0
        ;;
    restart)
        stop_servers
        sleep 2
        ;;
    -h|--help)
        echo "Usage: $0 [start|stop|restart|status]"
        echo ""
        echo "Commands:"
        echo "  start    Start all MCP servers (default)"
        echo "  stop     Stop all running MCP servers"
        echo "  restart  Restart all MCP servers"
        echo "  status   Show status of MCP servers"
        echo ""
        exit 0
        ;;
esac

# Check if .env file exists and load it
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
    echo -e "${GREEN}Environment loaded from .env${NC}"
fi

# Check Python
if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python is not installed${NC}"
    exit 1
fi
PYTHON_CMD=$(command -v python3 || command -v python)

# Clear previous PID file
rm -f "$PID_FILE"

echo ""
echo "Starting MCP servers..."
echo ""

# Start each MCP server
for name in "${!MCP_SERVERS[@]}"; do
    config="${MCP_SERVERS[$name]}"
    script="${config%%:*}"
    port="${config##*:}"

    # Check if port is already in use
    if check_port "$port"; then
        echo -e "  ${YELLOW}[SKIP]${NC} $name - port $port already in use"
        continue
    fi

    # Check if server script exists
    if [ ! -f "$SCRIPT_DIR/$script" ]; then
        echo -e "  ${RED}[ERROR]${NC} $name - script not found: $script"
        continue
    fi

    # Start server in background
    log_file="$LOG_DIR/${name}.log"
    $PYTHON_CMD "$SCRIPT_DIR/$script" > "$log_file" 2>&1 &
    pid=$!

    # Save PID
    echo "$name:$pid" >> "$PID_FILE"

    # Wait a moment and check if it started
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
        echo -e "  ${GREEN}[OK]${NC} $name started on port $port (PID: $pid)"
    else
        echo -e "  ${RED}[FAIL]${NC} $name failed to start - check $log_file"
    fi
done

echo ""
echo "========================================"
echo "MCP Servers Running"
echo "========================================"
echo ""
echo "Server URLs:"
for name in "${!MCP_SERVERS[@]}"; do
    config="${MCP_SERVERS[$name]}"
    port="${config##*:}"
    echo "  - $name: http://localhost:$port"
done
echo ""
echo "Log files: $LOG_DIR/"
echo ""
echo "Commands:"
echo "  Stop servers:    $0 stop"
echo "  Restart servers: $0 restart"
echo "  Check status:    $0 status"
echo ""
echo "Press Ctrl+C or run '$0 stop' to stop servers"
echo "========================================"

# Set trap to cleanup on Ctrl+C
trap stop_servers SIGINT SIGTERM

# Keep script running if --wait flag is provided
if [ "${1:-}" = "--wait" ] || [ "${2:-}" = "--wait" ]; then
    echo ""
    echo "Waiting... (Press Ctrl+C to stop)"

    # Monitor servers
    while true; do
        sleep 5
        for name in "${!MCP_SERVERS[@]}"; do
            config="${MCP_SERVERS[$name]}"
            port="${config##*:}"
            if ! check_port "$port"; then
                echo -e "${YELLOW}[WARN]${NC} $name (port $port) seems to have stopped"
            fi
        done
    done
fi
