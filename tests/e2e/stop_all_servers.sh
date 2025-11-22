#!/bin/bash
# 모든 서버를 중지하는 스크립트

echo "=================================="
echo "Stopping all servers..."
echo "=================================="

# API 서버 중지
echo "Stopping API server..."
pkill -f "api_server.py" && echo "  ✓ API Server stopped" || echo "  - API Server not running"

# Calculator Agent 중지
echo "Stopping Calculator Agent..."
pkill -f "calculator_agent.*server.py" && echo "  ✓ Calculator Agent stopped" || echo "  - Calculator Agent not running"

# Mail Agent 중지
echo "Stopping Mail Agent..."
pkill -f "mail_agent.*server.py" && echo "  ✓ Mail Agent stopped" || echo "  - Mail Agent not running"

# Calendar Agent 중지
echo "Stopping Calendar Agent..."
pkill -f "calendar_agent.*server.py" && echo "  ✓ Calendar Agent stopped" || echo "  - Calendar Agent not running"

# Jira Agent 중지
echo "Stopping Jira Agent..."
pkill -f "jira_agent.*server.py" && echo "  ✓ Jira Agent stopped" || echo "  - Jira Agent not running"

# RPA Agent 중지
echo "Stopping RPA Agent..."
pkill -f "rpa_agent.*server.py" && echo "  ✓ RPA Agent stopped" || echo "  - RPA Agent not running"

sleep 2

echo ""
echo "=================================="
echo "All servers stopped!"
echo "=================================="
