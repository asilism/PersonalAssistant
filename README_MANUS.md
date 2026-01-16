# Manus Multi-Agent System

PersonalAssistant에 통합된 **Manus 스타일 멀티-에이전트 시스템**입니다.

## 개요

Manus 시스템은 다음과 같은 특징을 가진 멀티-에이전트 아키텍처입니다:

- **Supervisor Agent**: 전체 작업을 계획하고 하위 에이전트들을 조율
- **Specialized Agents**: MCP 서버 기반의 전문화된 에이전트들 (브라우저, 파일시스템, 캘린더 등)
- **Markdown 통신**: 에이전트 간 통신은 Markdown 파일을 통해 이루어짐
- **비동기 협업**: 각 에이전트가 독립적으로 작업을 수행하며 병렬 실행 가능

## 아키텍처

```
User Request
    ↓
Supervisor Agent (분석 & 계획)
    ↓
plan.md (전체 계획 기록)
    ↓
tasks/{agent}/task.md (각 에이전트에게 작업 할당)
    ↓
MCP Agent Wrappers (병렬 실행)
    ├─ Browser Agent
    ├─ Filesystem Agent
    ├─ Calendar Agent
    └─ ...
    ↓
tasks/{agent}/result.md (결과 기록)
    ↓
Supervisor Agent (결과 수집 & 종합)
    ↓
Final Response
```

## 사용 방법

### 1. API를 통한 사용

#### 요청 실행

```bash
curl -X POST http://localhost:8000/api/manus/run \
  -H "Content-Type: application/json" \
  -d '{
    "request_text": "Search for the latest AI news and save it to a file",
    "user_id": "test_user",
    "tenant": "test_tenant"
  }'
```

**응답:**
```json
{
  "success": true,
  "message": "Request completed",
  "final_response": "I found 5 latest AI news articles and saved them to ai_news.txt",
  "results": {
    "browser": {
      "status": "completed",
      "summary": "Successfully searched for AI news"
    },
    "filesystem": {
      "status": "completed",
      "summary": "Saved content to ai_news.txt"
    }
  },
  "session_id": "session_20260116_153045_a1b2c3d4",
  "workspace_path": "workspaces/session_20260116_153045_a1b2c3d4",
  "execution_time": 12.34
}
```

#### 세션 정보 조회

```bash
curl http://localhost:8000/api/manus/session/{session_id}/info
```

#### 실행 계획 조회

```bash
curl http://localhost:8000/api/manus/session/{session_id}/plan
```

#### 에이전트 상태 조회

```bash
curl http://localhost:8000/api/manus/session/{session_id}/agents
```

### 2. Python 코드를 통한 사용

```python
import asyncio
from manus.coordinator import ManusCoordinator

async def main():
    # Coordinator 생성
    coordinator = ManusCoordinator(
        user_id="user_123",
        tenant="my_tenant"
    )

    # 요청 실행
    result = await coordinator.run(
        request="Download the file from example.com and extract text from it",
        max_wait_time=60  # 최대 60초 대기
    )

    print(f"Success: {result['success']}")
    print(f"Response: {result['final_response']}")

    # Cleanup
    await coordinator.cleanup()

asyncio.run(main())
```

### 3. 테스트 스크립트 실행

```bash
python test_manus.py
```

## 작업 공간 (Workspace) 구조

각 세션마다 독립적인 작업 공간이 생성됩니다:

```
workspaces/
└── session_20260116_153045_a1b2c3d4/
    ├── plan.md                    # 전체 실행 계획 및 상태
    ├── tasks/
    │   ├── browser/
    │   │   ├── task.md            # 브라우저 에이전트 작업
    │   │   └── result.md          # 브라우저 에이전트 결과
    │   ├── filesystem/
    │   │   ├── task.md
    │   │   └── result.md
    │   └── calendar/
    │       ├── task.md
    │       └── result.md
    └── logs/
        └── supervisor.log         # Supervisor 로그
```

### plan.md 예시

```markdown
# Execution Plan

## Request
Search for latest AI news and save to file

## Analysis
User wants to search for recent AI-related news articles and save the results to a file. This requires:
1. Web browsing to search for news
2. File system access to save the results

## Task Breakdown

### Task 1: Search for AI news
- **Agent**: browser
- **Status**: completed
- **Priority**: high
- **Dependencies**: []
- **Description**: Navigate to a news site and search for "latest AI news"

### Task 2: Save results to file
- **Agent**: filesystem
- **Status**: completed
- **Priority**: medium
- **Dependencies**: [task_1]
- **Description**: Write the search results to ai_news.txt

## Progress
- Total Tasks: 2
- Completed: 2
- In Progress: 0
- Pending: 0
- Failed: 0

## Results Summary
Successfully found 5 AI news articles and saved them to ai_news.txt
```

### task.md 예시

```markdown
# Task Assignment

## Task ID
task_browser_001

## Assigned At
2026-01-16 15:30:00

## Description
Navigate to news site and search for "latest AI news"

## Tool Calls

### Call 1: navigate
```json
{
  "url": "https://news.ycombinator.com"
}
```

### Call 2: search
```json
{
  "query": "latest AI news",
  "limit": 5
}
```

## Status
pending
```

### result.md 예시

```markdown
# Task Result

## Task ID
task_browser_001

## Status
completed

## Executed At
2026-01-16 15:30:15

## Results

### Call 1: navigate
```json
{
  "success": true,
  "url": "https://news.ycombinator.com"
}
```

### Call 2: search
```json
{
  "success": true,
  "results": [
    {"title": "OpenAI releases GPT-5", "url": "..."},
    {"title": "Google announces Gemini 2.0", "url": "..."},
    ...
  ]
}
```

## Summary
Successfully navigated to Hacker News and found 5 AI-related articles

## Errors
None
```

## 주요 컴포넌트

### 1. ManusCoordinator

전체 시스템을 조율하는 최상위 컴포넌트

**주요 메서드:**
- `run(request, session_id, max_wait_time)`: 요청 실행
- `get_session_info()`: 세션 정보 조회
- `get_plan_status()`: 계획 상태 조회
- `get_agent_statuses()`: 에이전트 상태 조회
- `cleanup()`: 리소스 정리

### 2. SupervisorAgent

계획 수립 및 조율을 담당하는 에이전트

**주요 메서드:**
- `analyze_request(request)`: 요청 분석
- `create_plan(request, analysis)`: 실행 계획 생성
- `assign_tasks(plan_data)`: 에이전트에게 작업 할당
- `monitor_progress()`: 진행 상황 모니터링
- `collect_results()`: 결과 수집
- `synthesize_final_response()`: 최종 응답 생성

### 3. MCPAgentWrapper

MCP 서버를 감싸는 에이전트 래퍼

**주요 메서드:**
- `start_monitoring()`: 작업 모니터링 시작
- `stop_monitoring()`: 모니터링 중지
- `execute_task(task_data)`: 작업 실행
- `execute_single_tool(tool_name, params)`: 단일 도구 실행

### 4. MDCommunicator

Markdown 파일 통신 관리

**주요 메서드:**
- `write_plan(plan_data)`: 계획 파일 작성
- `read_plan()`: 계획 파일 읽기
- `write_task(agent_name, task_data)`: 작업 파일 작성
- `read_task(agent_name)`: 작업 파일 읽기
- `write_result(agent_name, result_data)`: 결과 파일 작성
- `read_result(agent_name)`: 결과 파일 읽기

## 기존 시스템과의 차이점

| 특징 | 기존 시스템 (LangGraph) | Manus 시스템 |
|------|------------------------|--------------|
| 실행 방식 | 중앙집중식 (Dispatcher) | 분산형 (각 에이전트 독립) |
| 통신 방식 | 메모리 기반 | Markdown 파일 기반 |
| 병렬 실행 | 제한적 | 완전 병렬 |
| 추적성 | 로그 기반 | MD 파일로 모든 과정 기록 |
| 디버깅 | 로그 분석 필요 | MD 파일 읽으면 즉시 파악 |
| 확장성 | MCP 서버 추가 시 재설정 필요 | MCP 서버 추가 시 자동 인식 |

## 사용 시나리오

### 시나리오 1: 웹 리서치 및 문서 작성

```python
request = """
Search for the top 5 recent papers on quantum computing,
download their PDFs, and create a summary document.
"""

result = await coordinator.run(request)
```

**실행 흐름:**
1. Browser Agent: 논문 검색
2. Browser Agent: PDF 다운로드
3. Filesystem Agent: PDF 저장
4. Filesystem Agent: 요약 문서 작성

### 시나리오 2: 일정 관리 및 알림

```python
request = """
Check my calendar for tomorrow,
and if there's a meeting at 2 PM,
send a reminder email 1 hour before.
"""

result = await coordinator.run(request)
```

**실행 흐름:**
1. Calendar Agent: 내일 일정 조회
2. Calendar Agent: 2시 회의 확인
3. (조건부) Email Agent: 리마인더 이메일 발송 예약

## 설정

### LLM 설정

Manus 시스템은 기존 PersonalAssistant의 LLM 설정을 사용합니다:

1. Web UI의 Settings 탭에서 LLM provider, API key, model 설정
2. 또는 `.env` 파일에서 설정

### MCP 서버 설정

1. Web UI의 MCP Servers 탭에서 서버 추가/관리
2. 또는 직접 DB에 서버 설정 저장

Manus 시스템은 활성화된 MCP 서버를 자동으로 에이전트로 인식합니다.

## 문제 해결

### 에이전트가 작업을 실행하지 않음

**원인:** MCP 서버 연결 문제
**해결:**
1. `/api/mcp-servers/status` 엔드포인트로 서버 상태 확인
2. `/api/mcp-servers/sync`로 서버 재동기화

### 작업이 타임아웃됨

**원인:** `max_wait_time`이 너무 짧음
**해결:** `max_wait_time` 파라미터를 늘림 (기본값: 60초)

```python
result = await coordinator.run(request, max_wait_time=120)  # 2분
```

### MD 파일 파싱 오류

**원인:** MD 파일 형식 손상
**해결:** Workspace 디렉토리를 확인하고 해당 MD 파일을 수동으로 검사

## 개발 및 확장

### 새로운 에이전트 추가

1. MCP 서버 구현 (`mcp_servers/my_agent/server.py`)
2. Web UI에서 MCP 서버 등록
3. 서버 동기화 (`/api/mcp-servers/sync`)
4. Manus 시스템이 자동으로 새 에이전트 인식

### 커스텀 Supervisor 로직

`src/manus/supervisor.py`를 수정하여 계획 생성 로직 커스터마이징 가능

### MD 통신 프로토콜 확장

`src/manus/md_communicator.py`에서 MD 파일 포맷 변경 가능

## 성능 최적화

### 병렬 실행 최대화

Supervisor가 의존성이 없는 작업들을 동시에 할당하도록 계획을 생성하면
여러 에이전트가 병렬로 작업을 수행합니다.

### 폴링 주기 조정

`MCPAgentWrapper`의 `poll_interval` 파라미터로 작업 확인 주기 조정:

```python
agent_wrapper = MCPAgentWrapper(
    agent_name="browser",
    mcp_executor=executor,
    md_communicator=md_comm,
    poll_interval=0.5  # 0.5초마다 확인 (기본값)
)
```

## 라이선스

MIT License

## 기여

PR과 이슈는 언제나 환영합니다!

---

**작성일**: 2026-01-16
**버전**: 1.0
