# 🔍 실패 케이스 분석 가이드 (Claude용)

이 문서는 Claude가 `failures_*.json` 파일을 분석하고 수정하는 방법을 설명합니다.

---

## 📥 입력 받는 방법

사용자가 다음과 같이 요청합니다:

### 방법 1: 파일 경로 제공
```
/home/user/PersonalAssistant/failures_20251122_130000.json
이 파일 읽고 분석해서 수정해줘
```

### 방법 2: 파일 내용 제공
```
failures 로그야:
{
  "timestamp": "20251122_130000",
  "failures": [...]
}

분석하고 수정해줘
```

---

## 🔎 분석 프로세스

### Step 1: failures 파일 읽기

```python
# Read tool 사용
Read("/home/user/PersonalAssistant/failures_20251122_130000.json")
```

### Step 2: 각 실패 케이스 분류

실패 케이스를 다음 카테고리로 분류:

#### A. 실행 미완료 (Execution Not Completed)

**증상:**
```json
{
  "validation_details": {
    "reasons": ["실행이 완료되지 않음 (execution_completed 이벤트 없음)"]
  },
  "events": []  // 이벤트가 거의 없음
}
```

**가능한 원인:**
1. LLM API 호출 실패 (API 키, 모델명 문제)
2. 프롬프트 파싱 실패
3. Planning 단계에서 예외 발생

**확인 방법:**
- `events` 배열 확인
- `error` 필드 확인
- API 서버 로그 확인 필요

#### B. 도구 인식 실패 (Tool Recognition Failed)

**증상:**
```json
{
  "events": [
    {
      "type": "step_failed",
      "data": {
        "error": "Tool 'calculator' not found"
      }
    }
  ]
}
```

**원인:**
- Planner가 잘못된 도구 이름 생성
- 도구가 MCP에서 제대로 로드되지 않음

**수정 위치:**
- `src/orchestration/planner.py` - 시스템 프롬프트
- `src/orchestration/mcp_executor.py` - 도구 발견 로직

#### C. 파라미터 오류 (Invalid Parameters)

**증상:**
```json
{
  "events": [
    {
      "type": "step_failed",
      "data": {
        "error": "Missing required parameter: 'to_email'"
      }
    }
  ]
}
```

**원인:**
- Planner가 잘못된 파라미터 생성
- 도구 스키마와 실제 파라미터 불일치

**수정 위치:**
- `src/orchestration/planner.py` - 파라미터 생성 로직
- `mcp_servers/*/server.py` - 도구 스키마 검증

#### D. 검증 실패 (Validation Failed)

**증상:**
```json
{
  "validation_details": {
    "success": false,
    "reasons": [
      "실행 완료됨",
      "누락된 키워드: email, sent"
    ]
  },
  "events": [
    {
      "type": "execution_completed",
      "data": {...}
    }
  ]
}
```

**원인:**
- 실행은 성공했지만 응답에 필요한 정보 없음
- 검증 기준이 너무 엄격함

**수정 위치:**
- `tests/e2e/test_frontend_questions.py` - 검증 로직
- `mcp_servers/*/server.py` - 응답 형식 개선

---

## 🛠️ 수정 전략

### 전략 1: 공통 패턴 찾기

```python
# 실패 케이스를 에러 타입별로 그룹화
error_groups = {}
for failure in failures:
    error_type = extract_error_type(failure)
    if error_type not in error_groups:
        error_groups[error_type] = []
    error_groups[error_type].append(failure)

# 가장 많이 발생한 에러부터 처리
sorted_errors = sorted(error_groups.items(), key=lambda x: len(x[1]), reverse=True)
```

### 전략 2: 영향도 분석

**높은 우선순위:**
- 5개 이상의 질문이 같은 이유로 실패 → 즉시 수정
- 단일 에이전트 실패 → 기본 기능이므로 우선 수정
- API 호출 실패 → 모든 질문에 영향

**낮은 우선순위:**
- 1-2개 질문만 실패 → 나중에 수정
- RPA 복잡한 케이스 → 기본 기능 수정 후 처리
- 검증 기준 문제 → 실제 기능은 작동함

### 전략 3: 점진적 개선

```
Round 1: API/Planning 기본 문제 해결 → 성공률 30% → 60%
Round 2: 단일 에이전트 수정 → 60% → 80%
Round 3: 멀티 에이전트 수정 → 80% → 93%
Round 4: RPA 복잡한 케이스 → 93% → 100%
```

---

## 📝 분석 보고서 템플릿

```markdown
## 실패 케이스 분석 결과

### 📊 요약
- 총 실패: 7건
- 가장 많은 실패 유형: 도구 인식 실패 (5건)
- 예상 수정 시간: 15분

### 🔍 상세 분석

#### 1. 도구 인식 실패 (5건)

**영향받은 질문:**
- #1: "123 곱하기 456을 계산해줘"
- #2: "jiho@samsung.com에게 이메일 보내줘"
- ...

**원인:**
Planner가 "calculator" 대신 "calc"로 도구 이름 생성

**로그 예시:**
```json
{
  "type": "step_failed",
  "error": "Tool 'calc' not found. Available tools: ['calculator', 'send_email', ...]"
}
```

**수정 계획:**
1. `src/orchestration/planner.py:45` - 시스템 프롬프트에 정확한 도구 이름 강조
2. 도구 목록을 프롬프트에 명시적으로 포함

**예상 효과:**
5건 → 0건 (100% 해결)

---

#### 2. 파라미터 누락 (2건)

**영향받은 질문:**
- #7: "김민지에게 이메일 보내줘"

**원인:**
연락처 검색 결과를 이메일 도구 파라미터로 전달하지 못함

**수정 계획:**
1. `src/orchestration/executor.py` - 이전 단계 결과를 다음 단계에 전달하는 로직 개선

**예상 효과:**
2건 → 0건

---

### 🎯 수정 우선순위

1. **HIGH** - 도구 인식 실패 (5건, 33% 성공률 개선)
2. **MEDIUM** - 파라미터 누락 (2건, 13% 개선)
3. **LOW** - 검증 기준 조정 (0건, 기능 정상 작동)

### 🚀 시작합니다!

수정 작업을 시작하겠습니다...
```

---

## 🔧 실제 수정 예시

### 예시 1: Planner 프롬프트 개선

**문제:**
```json
{
  "error": "Tool 'send_mail' not found",
  "question": "이메일 보내줘"
}
```

**수정 전** (`src/orchestration/planner.py`):
```python
system_prompt = """
You are a task planner. Use the available tools to complete tasks.
"""
```

**수정 후:**
```python
system_prompt = """
You are a task planner. Use ONLY these exact tool names:
- calculator (NOT calc, compute, or calculate)
- send_email (NOT send_mail, email, or mail)
- create_calendar_event (NOT add_event or create_event)
- create_jira_issue (NOT add_jira or create_issue)

Available tools:
{tools_description}
"""
```

### 예시 2: 도구 스키마 개선

**문제:**
```json
{
  "error": "Missing required parameter: 'recipient_email'",
  "question": "김민지에게 이메일 보내줘"
}
```

**수정** (`mcp_servers/mail_agent/server.py`):
```python
# 스키마에 예시 추가
@mcp.tool()
async def send_email(
    to: str,  # "minji@samsung.com" or "김민지" (will lookup)
    subject: str,
    body: str
) -> str:
    """
    Send an email.

    Examples:
    - to="minji@samsung.com" (direct email)
    - to="김민지" (will lookup from contacts)
    """
    # 이름이면 연락처 검색
    if "@" not in to:
        to = await lookup_contact(to)

    # 이메일 전송
    ...
```

---

## ✅ 수정 후 체크리스트

- [ ] 관련 코드 파일 수정
- [ ] 수정 사항 테스트 (로컬)
- [ ] Git 커밋
- [ ] Git 푸시
- [ ] 사용자에게 재테스트 요청

---

## 💬 사용자 응답 템플릿

```markdown
## 수정 완료! ✅

### 발견된 문제
1. **도구 인식 실패** (5건) - Planner가 잘못된 도구 이름 생성
2. **파라미터 누락** (2건) - 이전 단계 결과 전달 누락

### 수정 내용
1. `src/orchestration/planner.py` - 시스템 프롬프트에 정확한 도구 이름 명시
2. `src/orchestration/executor.py` - 단계 간 결과 전달 로직 개선

### 커밋
- `fix: Improve tool recognition in planner (5 cases)`
- `fix: Pass previous step results to next step (2 cases)`

### 다음 단계
재테스트를 실행해주세요:

```bash
./tests/e2e/run_full_test.sh
```

예상 결과:
- 이전: 53.3% 성공률 (8/15)
- 예상: 100% 성공률 (15/15) 🎯

새로운 `failures_*.json` 파일이 생성되면 다시 제공해주세요!
```

---

이제 준비 완료! 실패 로그를 제공하면 자동으로 분석하고 수정하겠습니다. 🚀
