#!/bin/bash

# Check status of all MCP servers

echo "========================================"
echo "MCP Servers Status"
echo "========================================"
echo ""

# PID file directory
PID_DIR="logs/pids"

if [ ! -d "$PID_DIR" ]; then
    echo "No MCP servers have been started yet"
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

running=0
stopped=0

for server in "${MCP_SERVERS[@]}"; do
    pid_file="${PID_DIR}/${server}.pid"

    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")

        if kill -0 "$pid" 2>/dev/null; then
            echo "✅ ${server}: Running (PID: ${pid})"
            running=$((running + 1))
        else
            echo "❌ ${server}: Stopped (stale PID file)"
            stopped=$((stopped + 1))
        fi
    else
        echo "⚫ ${server}: Not started"
        stopped=$((stopped + 1))
    fi
done

echo ""
echo "========================================"
echo "Summary: ${running} running, ${stopped} stopped"
echo "========================================"
echo ""
