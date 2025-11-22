# 프론트엔드 질문 자동 테스트 가이드

## 📋 개요

이 테스트 시스템은 프론트엔드의 15개 예시 질문을 자동으로 실행하고 Claude API로 검증합니다.

**주요 기능:**
- 🤖 **LLM 기반 검증**: Claude API를 사용하여 지능적으로 성공/실패 판단
- 📊 **상세 로그 수집**: Planning, 실행 단계, 도구 호출, 최종 응답 등 모든 과정 기록
- 🔄 **Fallback 지원**: LLM 검증 실패 시 규칙 기반 검증 자동 전환
- 📁 **실패 케이스 분리 저장**: 실패한 케이스만 따로 저장하여 분석 용이

## 🚀 사용 방법

### 1. 필요한 서버들 실행

터미널을 **6개** 열어서 다음 명령어들을 각각 실행하세요:

#### Terminal 1: API 서버
```bash
cd /home/user/PersonalAssistant
PYTHONPATH=/home/user/PersonalAssistant/src python src/api_server.py
```

#### Terminal 2: Calculator Agent
```bash
cd /home/user/PersonalAssistant/mcp_servers/calculator_agent
PYTHONPATH=$(pwd) python server.py
```

#### Terminal 3: Mail Agent
```bash
cd /home/user/PersonalAssistant/mcp_servers/mail_agent
PYTHONPATH=$(pwd) python server.py
```

#### Terminal 4: Calendar Agent
```bash
cd /home/user/PersonalAssistant/mcp_servers/calendar_agent
PYTHONPATH=$(pwd) python server.py
```

#### Terminal 5: Jira Agent
```bash
cd /home/user/PersonalAssistant/mcp_servers/jira_agent
PYTHONPATH=$(pwd) python server.py
```

#### Terminal 6: RPA Agent
```bash
cd /home/user/PersonalAssistant/mcp_servers/rpa_agent
PYTHONPATH=$(pwd) python server.py
```

### 2. 테스트 실행

새 터미널에서:

```bash
cd /home/user/PersonalAssistant
python tests/e2e/test_frontend_questions.py
```

API 키를 입력하라는 메시지가 나타나면 OpenRouter API 키를 입력하세요.

또는 커맨드라인으로 바로 실행:

```bash
python tests/e2e/test_frontend_questions.py \
  --api-key "sk-or-v1-YOUR-API-KEY" \
  --base-url "http://localhost:8000"
```

## 📊 테스트 결과

테스트 완료 후:
- 콘솔에 상세한 결과 출력
- `test_results_YYYYMMDD_HHMMSS.json` 파일 자동 생성

### 결과 리포트 예시

```
================================================================================
최종 테스트 결과
================================================================================

총 질문 수: 15
✓ 성공: 12
✗ 실패: 3
성공률: 80.0%

카테고리별 성공률:
  single_agent: 5/5 (100.0%)
  multi_agent: 4/5 (80.0%)
  rpa: 3/5 (60.0%)
```

## 🔍 결과 JSON 파일 구조

```json
{
  "timestamp": "20251122_125000",
  "model": "openai/gpt-oss-20b",
  "provider": "openrouter",
  "total": 15,
  "success": 12,
  "fail": 3,
  "results": [
    {
      "question_id": 1,
      "question": "123 곱하기 456을 계산해줘",
      "category": "single_agent",
      "success": true,
      "execution_time": 2.34,
      "validation_details": {
        "success": true,
        "reasons": [
          "실행 완료됨",
          "계산 결과 일치: 56088"
        ]
      }
    }
  ]
}
```

## 🔧 트러블슈팅

### 문제: "Connection refused" 오류
**해결**: 모든 서버(API + 5개 MCP 에이전트)가 실행 중인지 확인

### 문제: "Access denied" 오류
**해결**: OpenRouter API 키 권한 및 크레딧 확인

### 문제: "Module not found" 오류
**해결**:
```bash
pip install -r requirements.txt
```

### 문제: 특정 질문만 실패
**해결**: 해당 MCP 에이전트 서버 로그 확인

## 📝 질문 목록

### 단일 Agent (5개)
1. 계산기: `123 곱하기 456을 계산해줘`
2. 이메일: `jiho@samsung.com에게 "See you at 2 PM"이라는 내용으로 이메일 보내줘`
3. 캘린더: `내일 오전 10시부터 11시까지 "Team Meeting" 일정 만들어줘`
4. Jira: `"Implement user authentication"라는 제목으로 Jira 이슈 만들어줘`
5. 연락처: `김민지의 이메일 주소를 찾아줘`

### 복수 Agent (5개)
6. 계산 + 이메일
7. 연락처 + 이메일
8. 일정 + 연락처 + 이메일
9. Jira + 이메일
10. 일정 + Jira

### RPA 포함 (5개)
11. 뉴스 검색 + 리포트
12. 뉴스 + 리포트 + 이메일
13. 참석 수집 + 요약 이메일
14. Jira 검색 + 리포트 + 이메일
15. 뉴스 + 리포트 + Jira + 이메일

## 🎯 성공 기준

각 질문 타입별 검증 기준:

- **계산기**: 올바른 계산 결과 포함
- **이메일**: "email", "sent" 키워드 + 수신자 이메일 주소
- **캘린더**: "calendar", "event", "created" 키워드 + 일정 제목
- **Jira**: "jira", "issue", "created" 키워드 + 이슈 제목
- **연락처**: 이름 + "@" (이메일 형식)
- **RPA**: "report", "summary" 등 키워드 + 모든 단계 완료

## 🔄 자동 수정 루프 (향후 구현 예정)

```python
while 실패_케이스_존재:
    1. 실패 로그 분석
    2. 문제 카테고리 분류
    3. 프롬프트 자동 개선
    4. 재테스트
    5. 결과 비교
```

## 📞 문의

문제가 발생하면 `test_results_*.json` 파일과 함께 문의하세요.
