#!/bin/bash
# Start all MCP servers in the background

echo "Starting MCP servers..."

# Create logs and PID directories if they don't exist
mkdir -p logs/pids

# Kill any existing servers on these ports
lsof -ti:8001,8002,8003,8004,8005 | xargs kill -9 2>/dev/null || true

# Start mail-agent
python3 mcp_servers/mail_agent/server.py > logs/mail_agent.log 2>&1 &
MAIL_PID=$!
echo $MAIL_PID > logs/pids/mail_agent.pid
echo "Started mail-agent on port 8001 (PID: $MAIL_PID)"

# Start calendar-agent
python3 mcp_servers/calendar_agent/server.py > logs/calendar_agent.log 2>&1 &
CALENDAR_PID=$!
echo $CALENDAR_PID > logs/pids/calendar_agent.pid
echo "Started calendar-agent on port 8002 (PID: $CALENDAR_PID)"

# Start calculator-agent
python3 mcp_servers/calculator_agent/server.py > logs/calculator_agent.log 2>&1 &
CALCULATOR_PID=$!
echo $CALCULATOR_PID > logs/pids/calculator_agent.pid
echo "Started calculator-agent on port 8003 (PID: $CALCULATOR_PID)"

# Start jira-agent
python3 mcp_servers/jira_agent/server.py > logs/jira_agent.log 2>&1 &
JIRA_PID=$!
echo $JIRA_PID > logs/pids/jira_agent.pid
echo "Started jira-agent on port 8004 (PID: $JIRA_PID)"

# Start rpa-agent
python3 mcp_servers/rpa_agent/server.py > logs/rpa_agent.log 2>&1 &
RPA_PID=$!
echo $RPA_PID > logs/pids/rpa_agent.pid
echo "Started rpa-agent on port 8005 (PID: $RPA_PID)"

echo "All MCP servers started!"
echo "Logs available in logs/ directory"
echo "PID files available in logs/pids/ directory"
