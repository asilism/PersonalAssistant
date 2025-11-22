#!/bin/bash
# 모든 서버를 백그라운드로 실행하는 스크립트

set -e

PROJECT_ROOT="/home/user/PersonalAssistant"
LOG_DIR="${PROJECT_ROOT}/logs"

# 로그 디렉토리 생성
mkdir -p "${LOG_DIR}"

echo "=================================="
echo "Starting all servers..."
echo "=================================="

# 기존 서버 프로세스 종료
echo "Stopping existing servers..."
pkill -f "api_server.py" || true
pkill -f "calculator_agent.*server.py" || true
pkill -f "mail_agent.*server.py" || true
pkill -f "calendar_agent.*server.py" || true
pkill -f "jira_agent.*server.py" || true
pkill -f "rpa_agent.*server.py" || true
sleep 2

# API 서버 시작
echo "Starting API server..."
cd "${PROJECT_ROOT}"
PYTHONPATH="${PROJECT_ROOT}/src" nohup python src/api_server.py \
  > "${LOG_DIR}/api_server.log" 2>&1 &
API_PID=$!
echo "  API Server started (PID: ${API_PID})"

# Calculator Agent 시작
echo "Starting Calculator Agent..."
cd "${PROJECT_ROOT}/mcp_servers/calculator_agent"
PYTHONPATH=$(pwd) nohup python server.py \
  > "${LOG_DIR}/calculator_agent.log" 2>&1 &
CALC_PID=$!
echo "  Calculator Agent started (PID: ${CALC_PID})"

# Mail Agent 시작
echo "Starting Mail Agent..."
cd "${PROJECT_ROOT}/mcp_servers/mail_agent"
PYTHONPATH=$(pwd) nohup python server.py \
  > "${LOG_DIR}/mail_agent.log" 2>&1 &
MAIL_PID=$!
echo "  Mail Agent started (PID: ${MAIL_PID})"

# Calendar Agent 시작
echo "Starting Calendar Agent..."
cd "${PROJECT_ROOT}/mcp_servers/calendar_agent"
PYTHONPATH=$(pwd) nohup python server.py \
  > "${LOG_DIR}/calendar_agent.log" 2>&1 &
CAL_PID=$!
echo "  Calendar Agent started (PID: ${CAL_PID})"

# Jira Agent 시작
echo "Starting Jira Agent..."
cd "${PROJECT_ROOT}/mcp_servers/jira_agent"
PYTHONPATH=$(pwd) nohup python server.py \
  > "${LOG_DIR}/jira_agent.log" 2>&1 &
JIRA_PID=$!
echo "  Jira Agent started (PID: ${JIRA_PID})"

# RPA Agent 시작
echo "Starting RPA Agent..."
cd "${PROJECT_ROOT}/mcp_servers/rpa_agent"
PYTHONPATH=$(pwd) nohup python server.py \
  > "${LOG_DIR}/rpa_agent.log" 2>&1 &
RPA_PID=$!
echo "  RPA Agent started (PID: ${RPA_PID})"

# 서버 시작 대기
echo ""
echo "Waiting for servers to start..."
sleep 10

# 서버 상태 확인
echo ""
echo "=================================="
echo "Server Status:"
echo "=================================="

check_server() {
  local url=$1
  local name=$2

  if curl -s -o /dev/null -w "%{http_code}" "${url}" | grep -q "200\|404\|405"; then
    echo "✓ ${name} is running (${url})"
    return 0
  else
    echo "✗ ${name} is NOT running (${url})"
    return 1
  fi
}

check_server "http://localhost:8000/api/health" "API Server"
check_server "http://localhost:8003/mcp" "Calculator Agent"
check_server "http://localhost:8001/mcp" "Mail Agent"
check_server "http://localhost:8002/mcp" "Calendar Agent"
check_server "http://localhost:8004/mcp" "Jira Agent"
check_server "http://localhost:8005/mcp" "RPA Agent"

echo ""
echo "=================================="
echo "All servers started!"
echo "=================================="
echo ""
echo "Logs are available in: ${LOG_DIR}/"
echo ""
echo "To run tests:"
echo "  cd ${PROJECT_ROOT}"
echo "  python tests/e2e/test_frontend_questions.py"
echo ""
echo "To stop all servers:"
echo "  ./tests/e2e/stop_all_servers.sh"
echo ""
