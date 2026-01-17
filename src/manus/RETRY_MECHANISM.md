# Manus Retry Mechanism

## 개요

Manus Coordinator는 작업 실패 시 자동으로 재시도하는 지능형 retry 메커니즘을 제공합니다. 이 메커니즘은 다음과 같은 특징이 있습니다:

- ✅ **자동 재시도**: 작업 실패 시 최대 3번까지 자동 재시도
- ✅ **에러 히스토리 추적**: 이전 시도의 에러와 접근법 기록
- ✅ **중복 에러 감지**: 동일한 에러가 반복되면 조기 종료 (무한 루프 방지)
- ✅ **지능형 재계획**: LLM이 이전 실패를 분석하고 다른 전략 사용

## 작동 방식

### 1. Retry Loop

```python
# ManusCoordinator.run() 호출
coordinator = ManusCoordinator()
result = await coordinator.run(
    request="기상청에 접속해서 오늘 서울 날씨 조사하고 파일로 저장해",
    max_retries=3  # 기본값: 3번 재시도
)
```

### 2. 실행 흐름

```
1. 초기 계획 생성
   ↓
2. 작업 실행 (Attempt 1/4)
   ↓
3. 실패 감지?
   YES → 에러 분석
   ├─ 중복 에러? → 조기 종료 🛑
   ├─ 최대 재시도? → 종료
   └─ 재계획 실행 → Attempt 2/4

   NO → 성공! ✅
```

### 3. 에러 히스토리 추적

`RetryHistory` 클래스가 각 작업의 실패 이력을 추적합니다:

```python
{
  "task_2_save_weather": [
    {
      "attempt_number": 1,
      "error": "pydantic validation error: content should be string",
      "error_signature": "pydantic validation error: content should be string",
      "plan_data": {...},
      "tool_calls": [{...}],
      "timestamp": "2026-01-17T20:08:41"
    }
  ]
}
```

### 4. 에러 정규화 (Duplicate Detection)

동일한 에러를 감지하기 위해 에러 메시지를 정규화합니다:

```python
# 원본 에러
"Error calling tool 'create_file': Task abc-123 failed at 2026-01-17T20:08:41"

# 정규화된 서명 (UUID, 숫자, 타임스탬프 제거)
"error calling tool 'create_file': task uuid failed at timestamp"
```

동일한 서명이 나오면 "중복 에러"로 판단하고 재시도를 중단합니다.

### 5. 지능형 재계획 (Intelligent Replanning)

`SupervisorAgent.replan()`이 실패 이력을 분석하고 새로운 계획을 생성합니다:

#### 입력 정보:
- 원래 요청
- 실패한 작업들
- 에러 메시지
- **이전 시도 히스토리** (핵심!)

#### LLM 프롬프트에 포함되는 정보:

```markdown
## Previous Attempt History

Task task_2_save_weather - Previous Attempts:

  Attempt 1 (at 2026-01-17T20:08:41):
    Error: pydantic validation error - content should be string but got dict
    Tool calls attempted:
      1. create_file
         Parameters: ['path', 'content', 'encoding', 'overwrite']
```

#### 재계획 전략:

LLM이 다음 전략 중 하나를 선택합니다:

**Strategy A - Fix Parameters**:
- 파라미터 타입 수정 (dict → string 변환)
- 파라미터 이름을 tool schema에 맞게 수정
- 누락된 필수 파라미터 추가

**Strategy B - Add Intermediate Step**:
- 중간 데이터 변환 작업 추가
- 예: dict를 JSON string으로 변환하는 작업

**Strategy C - Different Tool**:
- 현재 데이터 형식을 받을 수 있는 다른 도구 사용

**Strategy D - Break Down Task**:
- 복잡한 작업을 여러 단계로 분리

## 사용 예시

### 예제 1: 타입 에러 자동 수정

**초기 계획** (실패):
```json
{
  "task_id": "task_2_save",
  "tool_calls": [{
    "tool": "create_file",
    "params": {
      "path": "weather.txt",
      "content": "{{task_1_get_weather_call_1}}"  // dict를 그대로 전달 ❌
    }
  }]
}
```

**에러**: `pydantic validation error: content should be string but got dict`

**재계획** (성공):
```json
{
  "tasks": [
    {
      "task_id": "task_1_get_weather",
      "tool_calls": [{"tool": "get_current_weather", ...}]
    },
    {
      "task_id": "task_2_format_weather",
      "description": "Format weather data as readable string",
      "agent": "python",
      "tool_calls": [{
        "tool": "json_to_string",
        "params": {
          "data": "{{task_1_get_weather_call_1}}"
        }
      }]
    },
    {
      "task_id": "task_3_save",
      "dependencies": ["task_2_format_weather"],
      "tool_calls": [{
        "tool": "create_file",
        "params": {
          "path": "weather.txt",
          "content": "{{task_2_format_weather_call_1.result}}"  // 문자열 전달 ✅
        }
      }]
    }
  ]
}
```

### 예제 2: 중복 에러 조기 종료

```
Attempt 1: "파라미터 'city' 누락" 에러
  ↓ 재계획
Attempt 2: "파라미터 'city' 누락" 에러 (동일!)
  ↓ 중복 감지!
조기 종료 🛑
```

로그:
```
[ManusCoordinator] ⚠️  Some tasks failed
[ManusCoordinator]   ❌ Task task_1: Missing required parameter 'city'
[ManusCoordinator] 🛑 Task task_1 has DUPLICATE error - same error as previous attempt
[ManusCoordinator] 🛑 Stopping retries to prevent infinite loop
```

## 설정 옵션

### max_retries

재시도 횟수를 조정할 수 있습니다:

```python
# 재시도 없음 (1번만 시도)
await coordinator.run(request, max_retries=0)

# 기본값 (총 4번 시도: 초기 + 3번 재시도)
await coordinator.run(request, max_retries=3)

# 더 많은 재시도 (총 6번 시도)
await coordinator.run(request, max_retries=5)
```

### max_wait_time

각 작업의 최대 대기 시간:

```python
# 빠른 작업 (30초 timeout)
await coordinator.run(request, max_wait_time=30)

# 기본값 (60초)
await coordinator.run(request, max_wait_time=60)

# 느린 작업 (120초)
await coordinator.run(request, max_wait_time=120)
```

## 반환 값

```python
{
    'success': True/False,
    'message': 'Request completed after 2 retry attempts',
    'results': {...},
    'final_response': '...',
    'session_id': '...',
    'workspace_path': '...',
    'retry_count': 2,  # 실제 재시도 횟수
    'failure_reason': 'duplicate_error'  # 실패 시 이유
}
```

## 구현 세부사항

### 파일 구조

```
src/manus/
├── coordinator.py        # Retry loop 구현
├── supervisor.py         # Replan 로직
├── retry_history.py      # 에러 히스토리 추적
└── RETRY_MECHANISM.md    # 이 문서
```

### 주요 클래스

**RetryHistory**:
- `add_attempt()`: 실패 시도 기록
- `is_duplicate_error()`: 중복 에러 감지
- `get_history()`: 히스토리 조회
- `format_history_for_prompt()`: LLM 프롬프트용 포맷

**ManusCoordinator**:
- `run()`: Retry loop 포함
- `_execute_tasks_with_dependencies()`: 작업 실행

**SupervisorAgent**:
- `replan()`: 에러 히스토리 기반 재계획

## 모범 사례

### 1. 적절한 max_retries 설정

- **간단한 작업**: `max_retries=1` (빠른 실패)
- **일반적인 작업**: `max_retries=3` (기본값)
- **복잡한 작업**: `max_retries=5` (더 많은 시도)

### 2. 에러 로그 확인

재시도가 많이 발생한다면 근본 원인을 확인하세요:

```bash
# 로그에서 에러 패턴 찾기
grep "has DUPLICATE error" logs.txt

# 재계획 확인
grep "Replanning failed tasks" logs.txt
```

### 3. 프롬프트 개선

SupervisorAgent의 프롬프트를 조정하여 더 나은 재계획을 유도할 수 있습니다.

## 제한사항

1. **LLM 의존성**: 재계획 품질은 LLM 성능에 의존합니다
2. **비용**: 재시도마다 LLM API 호출 발생
3. **시간**: 재시도로 인한 총 실행 시간 증가

## 향후 개선 방안

- [ ] 에러 유형별 커스텀 재시도 전략
- [ ] 재시도 백오프 (exponential backoff)
- [ ] 부분 성공 처리 (일부 작업만 재시도)
- [ ] 재시도 메트릭 및 분석 도구
- [ ] 사용자 정의 재계획 전략 플러그인

## 참고 자료

- [orchestration/planner.py](../orchestration/planner.py): Main orchestration의 retry 로직 (참고 구현)
- [RetryHistory 클래스](./retry_history.py): 에러 히스토리 추적 구현
- [SupervisorAgent.replan()](./supervisor.py): 재계획 로직
