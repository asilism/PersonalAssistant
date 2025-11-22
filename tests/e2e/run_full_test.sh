#!/bin/bash
# 전체 테스트를 실행하는 올인원 스크립트
# 서버 시작 -> 테스트 실행 -> 서버 중지를 자동으로 수행

set -e

PROJECT_ROOT="/home/user/PersonalAssistant"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# API 키 확인
if [ -z "$OPENROUTER_API_KEY" ]; then
  echo "❌ Error: OPENROUTER_API_KEY environment variable is not set"
  echo ""
  echo "Usage:"
  echo "  export OPENROUTER_API_KEY=\"your-api-key-here\""
  echo "  ./run_full_test.sh"
  echo ""
  echo "Or:"
  echo "  OPENROUTER_API_KEY=\"your-api-key-here\" ./run_full_test.sh"
  exit 1
fi

echo "======================================"
echo "프론트엔드 질문 전체 테스트 시작"
echo "======================================"
echo ""

# 서버 시작
echo "Step 1/3: Starting all servers..."
"${SCRIPT_DIR}/start_all_servers.sh"

# 테스트 실행
echo ""
echo "Step 2/3: Running tests..."
cd "${PROJECT_ROOT}"
python tests/e2e/test_frontend_questions.py \
  --api-key "${OPENROUTER_API_KEY}" \
  --base-url "http://localhost:8000"

TEST_RESULT=$?

# 서버 중지
echo ""
echo "Step 3/3: Stopping all servers..."
"${SCRIPT_DIR}/stop_all_servers.sh"

# 결과 요약
echo ""
echo "======================================"
if [ $TEST_RESULT -eq 0 ]; then
  echo "✅ 테스트 완료!"
else
  echo "⚠️  테스트 중 일부 오류 발생"
fi
echo "======================================"

# 최신 결과 파일 표시
LATEST_RESULT=$(ls -t "${PROJECT_ROOT}"/test_results_*.json 2>/dev/null | head -1)
if [ -n "$LATEST_RESULT" ]; then
  echo ""
  echo "결과 파일: ${LATEST_RESULT}"
  echo ""
  echo "상세 결과 확인:"
  echo "  cat ${LATEST_RESULT} | jq ."
fi

exit $TEST_RESULT
