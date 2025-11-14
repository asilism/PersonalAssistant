#!/bin/bash

# Stop all MCP servers

echo "========================================"
echo "Stopping MCP Servers"
echo "========================================"
echo ""

# PID file directory
PID_DIR="logs/pids"

if [ ! -d "$PID_DIR" ]; then
    echo "No MCP servers are running"
    exit 0
fi

# Find all PID files
pid_files=$(find "$PID_DIR" -name "*.pid" 2>/dev/null)

if [ -z "$pid_files" ]; then
    echo "No MCP servers are running"
    exit 0
fi

# Stop each server
for pid_file in $pid_files; do
    server_name=$(basename "$pid_file" .pid)

    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")

        if kill -0 "$pid" 2>/dev/null; then
            echo "Stopping ${server_name} (PID: ${pid})..."
            kill "$pid"

            # Wait for process to stop
            for i in {1..10}; do
                if ! kill -0 "$pid" 2>/dev/null; then
                    echo "✅ Stopped ${server_name}"
                    break
                fi
                sleep 0.5
            done

            # Force kill if still running
            if kill -0 "$pid" 2>/dev/null; then
                echo "⚠️  Force killing ${server_name}..."
                kill -9 "$pid" 2>/dev/null
                echo "✅ Stopped ${server_name} (forced)"
            fi
        else
            echo "⚠️  ${server_name} is not running"
        fi

        rm "$pid_file"
    fi
done

echo ""
echo "========================================"
echo "All MCP Servers Stopped"
echo "========================================"
echo ""
