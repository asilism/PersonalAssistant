#!/bin/bash
# Stop all MCP servers

echo "Stopping MCP servers..."

# Kill all processes on ports 8001-8005
lsof -ti:8001,8002,8003,8004,8005 | xargs kill -9 2>/dev/null

echo "All MCP servers stopped!"
