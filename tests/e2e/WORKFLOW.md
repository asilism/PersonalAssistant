# 🔄 수정-테스트 반복 워크플로우

실패한 테스트를 자동으로 수정하는 반복 프로세스입니다.

## 📋 워크플로우 개요

```
1. 테스트 실행 → 2. 실패 로그 생성 → 3. Claude에게 제공 → 4. 수정 → 5. 재테스트 → 반복
```

---

## 🚀 1단계: 테스트 실행

```bash
cd /home/user/PersonalAssistant

# 서버 시작 + 테스트 실행
export OPENROUTER_API_KEY="your-api-key"
./tests/e2e/run_full_test.sh
```

**출력:**
```
총 질문 수: 15
✓ 성공: 8
✗ 실패: 7
성공률: 53.3%

전체 결과 저장됨: test_results_20251122_130000.json
실패 케이스 저장됨: failures_20251122_130000.json
👉 이 파일을 Claude에게 제공하여 문제를 수정하세요!
```

---

## 📤 2단계: 실패 로그 Claude에게 제공

### 방법 1: 파일 내용 복사

```bash
# 실패 로그 확인
cat failures_20251122_130000.json
```

내용을 복사해서 Claude에게 다음과 같이 요청:

```
실패 로그야:

[여기에 failures_*.json 파일 내용 붙여넣기]

이걸 분석하고 문제를 수정해줘.
```

### 방법 2: 파일 경로 제공 (Claude Code 환경)

```
/home/user/PersonalAssistant/failures_20251122_130000.json

이 파일을 읽고 실패한 케이스들을 분석해서 수정해줘.
```

---

## 🔍 3단계: Claude가 자동으로 수행

Claude가 다음을 자동으로 수행합니다:

### 3.1 실패 로그 분석
```json
{
  "question_id": 1,
  "question": "123 곱하기 456을 계산해줘",
  "error": "Planning failed: Tool 'calculator' not recognized",
  "events": [...],
  "validation_details": {
    "reasons": [
      "실행이 완료되지 않음",
      "계산 결과 불일치"
    ]
  }
}
```

### 3.2 문제 유형 분류

**A. 프롬프트 문제**
- LLM이 올바른 도구를 선택하지 못함
- 수정: `src/orchestration/planner.py`의 시스템 프롬프트 개선

**B. 파싱 문제**
- LLM 응답을 JSON으로 파싱 실패
- 수정: `src/orchestration/planner.py`의 응답 파싱 로직 개선

**C. 도구 호출 문제**
- 도구는 선택했지만 파라미터가 잘못됨
- 수정: 도구 스키마 개선, 예시 추가

**D. 실행 오류**
- 도구 실행 중 오류 발생
- 수정: MCP 에이전트 코드 수정

### 3.3 자동 수정

Claude가 문제에 맞는 파일을 수정:
- `src/orchestration/planner.py` - 프롬프트, 파싱 로직
- `src/orchestration/executor.py` - 실행 로직
- `mcp_servers/*/server.py` - 에이전트 코드

### 3.4 커밋 & 푸시

```bash
git add src/
git commit -m "fix: Improve calculator tool recognition in planner"
git push
```

---

## 🔄 4단계: 재테스트

```bash
# 수정 후 다시 테스트
./tests/e2e/run_full_test.sh
```

**개선된 결과:**
```
총 질문 수: 15
✓ 성공: 12  ← 8에서 증가!
✗ 실패: 3   ← 7에서 감소!
성공률: 80.0%
```

---

## ♻️ 5단계: 반복

성공률 100%까지 또는 원하는 수준까지 반복:

```bash
while [ 실패_케이스_존재 ]; do
  # 1. 실패 로그 Claude에게 제공
  cat failures_*.json

  # 2. Claude가 분석 및 수정

  # 3. 재테스트
  ./tests/e2e/run_full_test.sh
done
```

---

## 📊 실패 로그 구조

`failures_YYYYMMDD_HHMMSS.json`:

```json
{
  "timestamp": "20251122_130000",
  "model": "openai/gpt-oss-20b",
  "provider": "openrouter",
  "total_failures": 7,
  "instructions": "이 파일을 Claude에게 제공하여 문제를 분석하고 수정하세요.",
  "failures": [
    {
      "question_id": 1,
      "question": "123 곱하기 456을 계산해줘",
      "category": "single_agent",
      "success": false,
      "events": [
        {
          "type": "plan_created",
          "data": {...}
        },
        {
          "type": "step_failed",
          "data": {
            "error": "Tool 'calculator' not found"
          }
        }
      ],
      "error": null,
      "execution_time": 2.34,
      "validation_details": {
        "success": false,
        "reasons": [
          "실행이 완료되지 않음",
          "계산 결과 불일치"
        ]
      },
      "full_response": ""
    }
  ]
}
```

---

## 💡 팁

### 특정 실패 케이스만 재테스트

실패한 질문 ID만 남기고 `frontend_questions.json` 수정:

```json
{
  "questions": [
    {
      "id": 1,
      "question": "실패했던 질문만"
    }
  ]
}
```

### 수정 우선순위

1. **가장 많이 실패한 패턴 먼저** - 예: "모든 계산기 질문 실패" → 계산기 관련 문제 집중 수정
2. **간단한 것부터** - 단일 에이전트 → 멀티 에이전트 → RPA
3. **공통 원인 찾기** - 여러 질문이 같은 이유로 실패하면 한 번 수정으로 다수 해결

---

## 🎯 목표

**100% 성공률 달성!**

```
총 질문 수: 15
✓ 성공: 15
✗ 실패: 0
성공률: 100.0%

카테고리별 성공률:
  single_agent: 5/5 (100.0%)
  multi_agent: 5/5 (100.0%)
  rpa: 5/5 (100.0%)
```

---

## 📞 예시 대화

**사용자:**
```
failures_20251122_130000.json

이거 분석하고 수정해줘.
```

**Claude:**
```
파일을 분석했습니다.

발견된 문제:
1. 계산기 도구 인식 실패 (5건)
   - 원인: 프롬프트에서 "calculator" 대신 "calc"로 추천
   - 수정: planner.py 시스템 프롬프트 개선

2. 이메일 주소 파싱 실패 (2건)
   - 원인: 한국어 이름 처리 미흡
   - 수정: contact_agent 검색 로직 개선

수정 중...
[파일들 수정]
커밋 완료!

다시 테스트 실행해주세요:
  ./tests/e2e/run_full_test.sh
```

---

이제 시작해보세요! 🚀
