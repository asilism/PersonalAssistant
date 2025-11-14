#!/bin/bash
# Start all MCP servers in the background

echo "Starting MCP servers..."

# Create logs directory if it doesn't exist
mkdir -p logs

# Kill any existing servers on these ports
lsof -ti:8001,8002,8003,8004,8005 | xargs kill -9 2>/dev/null || true

# Start each MCP server
python3 mcp_servers/mail_agent/server.py > logs/mail_agent.log 2>&1 &
echo "Started mail-agent on port 8001 (PID: $!)"

python3 mcp_servers/calendar_agent/server.py > logs/calendar_agent.log 2>&1 &
echo "Started calendar-agent on port 8002 (PID: $!)"

python3 mcp_servers/calculator_agent/server.py > logs/calculator_agent.log 2>&1 &
echo "Started calculator-agent on port 8003 (PID: $!)"

python3 mcp_servers/jira_agent/server.py > logs/jira_agent.log 2>&1 &
echo "Started jira-agent on port 8004 (PID: $!)"

python3 mcp_servers/rpa_agent/server.py > logs/rpa_agent.log 2>&1 &
echo "Started rpa-agent on port 8005 (PID: $!)"

echo "All MCP servers started!"
echo "Logs available in logs/ directory"
