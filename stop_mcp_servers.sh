#!/bin/bash
# Stop all MCP servers

echo "Stopping MCP servers..."

# PID file directory
PID_DIR="logs/pids"

if [ ! -d "$PID_DIR" ]; then
    echo "No MCP servers running (PID directory not found)"
    exit 0
fi

# MCP server names
MCP_SERVERS=(
    "calculator_agent"
    "calendar_agent"
    "jira_agent"
    "mail_agent"
    "rpa_agent"
)

stopped=0
not_running=0

for server in "${MCP_SERVERS[@]}"; do
    pid_file="${PID_DIR}/${server}.pid"

    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")

        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null
            echo "Stopped ${server} (PID: ${pid})"
            stopped=$((stopped + 1))
        else
            echo "Removing stale PID file for ${server}"
            not_running=$((not_running + 1))
        fi

        # Remove PID file
        rm -f "$pid_file"
    else
        not_running=$((not_running + 1))
    fi
done

echo ""
echo "All MCP servers stopped!"
echo "Stopped: ${stopped}, Not running: ${not_running}"
