# Manus-Style Multi-Agent Architecture Plan

## Overview

이 문서는 PersonalAssistant 프로젝트를 **Manus 스타일 멀티-에이전트 시스템**으로 구현하기 위한 아키텍처 계획입니다.

## Manus Architecture 핵심 개념

### 1. Supervisor Agent (감독 에이전트)
- 전체 작업을 분석하고 실행 계획 수립
- 하위 에이전트들에게 작업 할당 및 조율
- 결과를 수집하고 종합하여 최종 응답 생성

### 2. Markdown 기반 통신
- **계획 문서 (`plan.md`)**: 전체 계획, 작업 분해, 실행 상태
- **작업 문서 (`tasks/{agent}/task.md`)**: 각 에이전트에게 할당된 작업
- **결과 문서 (`tasks/{agent}/result.md`)**: 각 에이전트의 실행 결과
- **상태 동기화**: MD 파일을 읽고 쓰며 상태 공유

### 3. MCP-Based Specialized Agents
- 각 MCP 서버가 specialized agent 역할
- 독립적으로 작동하며 자신의 도메인(브라우저, 파일시스템, 캘린더 등) 담당
- MD 파일을 모니터링하고 작업 수행 후 결과 기록

### 4. Asynchronous Collaboration
- 각 에이전트가 비동기적으로 작업 수행
- Supervisor는 에이전트 결과를 모니터링하고 다음 단계 결정
- 병렬 실행으로 효율성 향상

## 현재 시스템 분석

### 기존 구조
```
PersonalAssistant/
├── src/orchestration/
│   ├── orchestrator.py      # LangGraph 기반 오케스트레이션
│   ├── planner.py           # LLM 기반 계획 수립
│   ├── dispatcher.py        # 작업 실행
│   ├── mcp_executor.py      # MCP 서버 통신
│   └── tracker.py           # 작업 추적
└── mcp_servers/
    ├── browser/             # 브라우저 자동화
    ├── computer/            # 컴퓨터 제어
    ├── filesystem/          # 파일 시스템 조작
    ├── google_calendar/     # 구글 캘린더
    ├── weather/             # 날씨 정보
    └── youtube_music/       # 유튜브 뮤직
```

### 강점
✅ MCP 서버들이 이미 구현되어 있음
✅ LangGraph를 통한 상태 관리
✅ 멀티 LLM 지원 (Claude, GPT, OpenRouter)
✅ HTTP/SSE 기반 MCP 통신

### 개선 필요 사항
❌ 중앙집중식 실행 (dispatcher가 모든 작업 수행)
❌ 에이전트 간 직접 통신 불가
❌ 병렬 실행 제한적
❌ 상태 공유 메커니즘 부재

## Manus 스타일 아키텍처 설계

### 1. 폴더 구조

```
PersonalAssistant/
├── src/
│   ├── manus/                       # NEW: Manus 스타일 구현
│   │   ├── __init__.py
│   │   ├── supervisor.py            # Supervisor Agent
│   │   ├── agent_wrapper.py         # MCP Agent Wrapper
│   │   ├── md_communicator.py       # MD 파일 통신 관리
│   │   └── coordinator.py           # 전체 조율
│   └── orchestration/               # 기존 코드 (필요시 통합)
│       └── ...
├── workspaces/                      # NEW: 작업 공간 (세션별)
│   └── {session_id}/
│       ├── plan.md                  # 전체 계획 및 상태
│       ├── tasks/                   # 에이전트별 작업
│       │   ├── browser/
│       │   │   ├── task.md          # 할당된 작업
│       │   │   └── result.md        # 실행 결과
│       │   ├── filesystem/
│       │   │   ├── task.md
│       │   │   └── result.md
│       │   └── ...
│       └── logs/                    # 실행 로그
│           └── supervisor.log
└── mcp_servers/                     # 기존 MCP 서버들
    └── ...
```

### 2. 핵심 컴포넌트

#### 2.1 Supervisor Agent (`supervisor.py`)

**역할:**
- 사용자 요청 분석
- 전체 계획 수립 및 MD 파일에 기록
- 하위 에이전트에게 작업 할당
- 결과 수집 및 종합
- 재계획 및 에러 처리

**주요 메서드:**
```python
class SupervisorAgent:
    async def analyze_request(self, request: str) -> Plan
    async def create_plan(self, request: str, available_agents: List[str]) -> Plan
    async def assign_tasks(self, plan: Plan) -> None
    async def monitor_progress(self) -> AgentStatus
    async def collect_results(self) -> Dict[str, Any]
    async def replan(self, failed_tasks: List[Task]) -> Plan
    async def synthesize_final_response(self, results: Dict) -> str
```

**계획 MD 파일 포맷:**
```markdown
# Execution Plan

## Request
{user_request}

## Analysis
{supervisor_analysis}

## Task Breakdown

### Task 1: {task_name}
- **Agent**: browser
- **Status**: pending | in_progress | completed | failed
- **Priority**: high | medium | low
- **Dependencies**: []

### Task 2: {task_name}
- **Agent**: filesystem
- **Status**: in_progress
- **Dependencies**: [task_1]

## Progress
- Total Tasks: 5
- Completed: 2
- In Progress: 1
- Pending: 2
- Failed: 0

## Results Summary
{results_when_completed}
```

#### 2.2 MCP Agent Wrapper (`agent_wrapper.py`)

**역할:**
- MCP 서버를 감싸는 에이전트 래퍼
- MD 파일 모니터링 (task.md 변경 감지)
- 작업 실행 (MCP 도구 호출)
- 결과를 MD 파일에 기록

**주요 메서드:**
```python
class MCPAgentWrapper:
    def __init__(self, agent_name: str, mcp_server_name: str, workspace_path: Path)

    async def start_monitoring(self) -> None
    async def read_task(self) -> Optional[Task]
    async def execute_task(self, task: Task) -> TaskResult
    async def write_result(self, result: TaskResult) -> None
    async def call_mcp_tool(self, tool_name: str, params: dict) -> Any
```

**작업 MD 파일 포맷 (`task.md`):**
```markdown
# Task Assignment

## Task ID
task_browser_001

## Assigned At
2026-01-16 15:30:00

## Description
Navigate to example.com and extract the main heading text

## Tool Calls

### Call 1: navigate
```json
{
  "url": "https://example.com"
}
```

### Call 2: extract_text
```json
{
  "selector": "h1"
}
```

## Status
pending
```

**결과 MD 파일 포맷 (`result.md`):**
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
  "url": "https://example.com"
}
```

### Call 2: extract_text
```json
{
  "success": true,
  "text": "Example Domain"
}
```

## Summary
Successfully navigated to example.com and extracted heading: "Example Domain"

## Errors
None
```

#### 2.3 MD Communicator (`md_communicator.py`)

**역할:**
- MD 파일 읽기/쓰기 추상화
- 파일 변경 감지 (watchdog)
- Locking 및 동기화

**주요 메서드:**
```python
class MDCommunicator:
    async def write_plan(self, plan: Plan) -> None
    async def read_plan(self) -> Plan
    async def write_task(self, agent_name: str, task: Task) -> None
    async def read_task(self, agent_name: str) -> Optional[Task]
    async def write_result(self, agent_name: str, result: TaskResult) -> None
    async def read_result(self, agent_name: str) -> Optional[TaskResult]
    async def update_task_status(self, task_id: str, status: str) -> None
    async def watch_file(self, file_path: Path, callback: Callable) -> None
```

#### 2.4 Coordinator (`coordinator.py`)

**역할:**
- 전체 시스템 조율
- Supervisor와 Agent Wrappers 생성 및 관리
- 세션별 작업 공간 관리

**주요 메서드:**
```python
class ManusCoordinator:
    async def initialize_session(self, session_id: str, user_id: str, tenant: str) -> None
    async def run(self, request: str) -> Dict[str, Any]
    async def create_supervisor(self) -> SupervisorAgent
    async def create_agent_wrappers(self) -> List[MCPAgentWrapper]
    async def start_agents(self) -> None
    async def stop_agents(self) -> None
```

### 3. 실행 흐름

```
1. User Request
   ↓
2. ManusCoordinator.run(request)
   ↓
3. Create workspace: workspaces/{session_id}/
   ↓
4. SupervisorAgent.analyze_request()
   ↓
5. SupervisorAgent.create_plan()
   → Write to plan.md
   ↓
6. SupervisorAgent.assign_tasks()
   → Write to tasks/{agent}/task.md
   ↓
7. MCPAgentWrapper (각 에이전트별 병렬 실행)
   - Monitor task.md
   - Execute MCP tools
   - Write to result.md
   ↓
8. SupervisorAgent.monitor_progress()
   - Read result.md files
   - Update plan.md
   ↓
9. SupervisorAgent.collect_results()
   ↓
10. SupervisorAgent.synthesize_final_response()
    ↓
11. Return to user
```

### 4. 에이전트 목록 (MCP 서버 기반)

| Agent Name | MCP Server | Domain | Example Tools |
|-----------|-----------|---------|--------------|
| browser | browser | 웹 자동화 | navigate, click, extract_text, screenshot |
| computer | computer | 시스템 제어 | execute_command, keyboard_input, mouse_move |
| filesystem | filesystem | 파일 관리 | read_file, write_file, list_directory |
| calendar | google_calendar | 일정 관리 | create_event, list_events, update_event |
| weather | weather | 날씨 정보 | get_weather, get_forecast |
| music | youtube_music | 음악 재생 | search_music, play_song, create_playlist |

## 구현 단계

### Phase 1: 핵심 인프라 구축
1. ✅ MD 파일 구조 정의
2. ⏳ `MDCommunicator` 구현
3. ⏳ 작업 공간 관리 시스템 구축

### Phase 2: Supervisor Agent 구현
1. ⏳ `SupervisorAgent` 기본 구조
2. ⏳ LLM 기반 계획 수립
3. ⏳ 작업 분해 및 할당 로직
4. ⏳ 결과 수집 및 종합

### Phase 3: MCP Agent Wrapper 구현
1. ⏳ `MCPAgentWrapper` 기본 구조
2. ⏳ MD 파일 모니터링 (watchdog)
3. ⏳ MCP 도구 실행 통합
4. ⏳ 결과 기록 시스템

### Phase 4: Coordinator 구현
1. ⏳ `ManusCoordinator` 구조
2. ⏳ 세션 관리
3. ⏳ 에이전트 생명주기 관리
4. ⏳ 에러 처리 및 재시도

### Phase 5: 통합 및 테스트
1. ⏳ 기존 시스템과 통합
2. ⏳ 엔드-투-엔드 테스트
3. ⏳ 성능 최적화
4. ⏳ 문서화

## 기술 스택

- **Python 3.11+**
- **FastMCP**: MCP 서버 통신
- **Watchdog**: 파일 변경 감지
- **Anthropic/OpenAI SDK**: LLM 통신
- **aiofiles**: 비동기 파일 I/O
- **LangGraph**: 상태 관리 (기존 시스템과 호환)

## 예상 효과

### 장점
✅ **진정한 멀티-에이전트 협업**: 각 에이전트가 독립적으로 작동
✅ **병렬 실행**: 여러 에이전트가 동시에 작업 수행
✅ **투명성**: MD 파일로 모든 과정 추적 가능
✅ **확장성**: 새로운 MCP 서버 추가 시 자동으로 에이전트 생성
✅ **디버깅 용이**: MD 파일을 읽으면 전체 실행 흐름 파악

### 도전 과제
⚠️ **파일 동기화**: 여러 프로세스의 동시 파일 접근
⚠️ **에러 전파**: 에이전트 실패 시 다른 에이전트 영향
⚠️ **상태 일관성**: MD 파일과 메모리 상태 동기화

## 다음 단계

1. ✅ 아키텍처 계획 문서 작성
2. ⏳ `MDCommunicator` 구현
3. ⏳ `SupervisorAgent` 프로토타입 구현
4. ⏳ 간단한 테스트 시나리오로 검증

---

**작성일**: 2026-01-16
**버전**: 1.0
**상태**: 계획 단계
