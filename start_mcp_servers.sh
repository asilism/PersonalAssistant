#!/bin/bash

# Start all MCP servers for Personal Assistant
# This script launches all MCP servers in the background

echo "========================================"
echo "Starting MCP Servers"
echo "========================================"
echo ""

# Directory containing MCP servers
MCP_DIR="mcp_servers"

# Log directory
LOG_DIR="logs/mcp"
mkdir -p "$LOG_DIR"

# PID file directory
PID_DIR="logs/pids"
mkdir -p "$PID_DIR"

# Array of MCP server directories
MCP_SERVERS=(
    "calculator_agent"
    "calendar_agent"
    "jira_agent"
    "mail_agent"
    "rpa_agent"
)

# Function to start a single MCP server
start_server() {
    local server_name=$1
    local server_path="${MCP_DIR}/${server_name}"
    local log_file="${LOG_DIR}/${server_name}.log"
    local pid_file="${PID_DIR}/${server_name}.pid"

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            echo "⚠️  ${server_name} is already running (PID: ${pid})"
            return
        else
            rm "$pid_file"
        fi
    fi

    if [ ! -f "${server_path}/server.py" ]; then
        echo "❌ ${server_name}: server.py not found"
        return
    fi

    # Start the server in background
    cd "$server_path"
    python server.py > "../../${log_file}" 2>&1 &
    local pid=$!
    cd - > /dev/null

    # Save PID
    echo "$pid" > "$pid_file"

    # Check if process started successfully
    sleep 0.5
    if kill -0 "$pid" 2>/dev/null; then
        echo "✅ Started ${server_name} (PID: ${pid})"
    else
        echo "❌ Failed to start ${server_name}"
        rm "$pid_file"
    fi
}

# Start all servers
echo "Starting MCP servers..."
echo ""

for server in "${MCP_SERVERS[@]}"; do
    start_server "$server"
done

echo ""
echo "========================================"
echo "MCP Servers Started"
echo "========================================"
echo ""
echo "Log files: ${LOG_DIR}/"
echo "PID files: ${PID_DIR}/"
echo ""
echo "To stop all servers, run: ./stop_mcp_servers.sh"
echo "To check server status, run: ./status_mcp_servers.sh"
echo ""
