# MCP Server Development Guide

이 가이드는 새로운 MCP 서버를 개발할 때 프론트엔드 표시 시스템과 통합하는 방법을 설명합니다.

## data_type 기반 Formatter 시스템

프론트엔드는 `data_type` 필드를 기반으로 결과를 포맷팅합니다. 새 MCP 서버 추가 시 프론트엔드 수정 없이도 기본적인 렌더링이 가능합니다.

### 현재 등록된 data_type 목록

| data_type | 설명 | Formatter 위치 |
|-----------|------|----------------|
| `jira_issues` | Jira 이슈 목록 | `frontend/src/main.js:formatJiraIssues` |
| `calendar_events` | 캘린더 일정 | `frontend/src/main.js:formatCalendarEvents` |
| `emails` | 이메일 목록 | `frontend/src/main.js:formatEmails` |
| `news_articles` | 뉴스 기사 | `frontend/src/main.js:formatNewsArticles` |
| `report` | 리포트 (markdown/html/text) | `frontend/src/main.js:formatReport` |
| `attendance` | 참석 현황 | `frontend/src/main.js:formatAttendanceSummary` |
| `calculator` | 계산 결과 | `frontend/src/main.js:formatCalculatorResult` |
| `weather` | 날씨 정보 | `frontend/src/main.js:formatWeatherData` |
| `generic` | 기타 (자동 렌더링) | `frontend/src/main.js:formatGenericData` |

### Formatter Registry 위치

```javascript
// frontend/src/main.js (Line ~355)
const dataTypeFormatters = {
    'jira_issues': formatJiraIssues,
    'emails': formatEmails,
    'calendar_events': formatCalendarEvents,
    'news_articles': formatNewsArticles,
    'report': formatReport,
    'attendance': formatAttendanceSummary,
    'calculator': formatCalculatorResult,
    'weather': formatWeatherData,
    'generic': formatGenericData
};
```

## 새 MCP 서버 개발 시 체크리스트

### 1. MCP 서버 응답 형식

MCP 서버 tool의 응답에서 프론트엔드가 사용할 필드명을 일관되게 유지:

```python
# 권장 필드명 예시
def format_response(items):
    return {
        "success": True,
        "count": len(items),
        "items": [  # 또는 구체적인 이름: events, issues, emails 등
            {
                "id": item.id,
                "title": item.title,  # 'summary' 대신 'title' 권장
                "description": item.description,
                "start_time": item.start,  # 'start' 대신 'start_time' 권장
                "end_time": item.end,      # 'end' 대신 'end_time' 권장
                # ...
            }
            for item in items
        ]
    }
```

### 2. Planner 프롬프트 업데이트

`src/orchestration/planner.py`의 data_type 목록에 새 타입 추가:

```python
# Line ~1646
IMPORTANT: Always include "data_type" field to specify the type of data being returned.
Available data_type values:
- "jira_issues" - for Jira issue search results
- "calendar_events" - for calendar event lists
- "your_new_type" - for your new data type  # <-- 추가
```

### 3. (선택) 커스텀 Formatter 추가

Generic formatter가 자동으로 테이블/리스트 렌더링을 지원하므로, 특별한 UI가 필요한 경우에만 추가:

```javascript
// frontend/src/main.js

// 1. Formatter 함수 추가 (formatGenericData 근처에)
function formatYourNewType(message, data) {
    let html = `<div class="message-text">${escapeHtml(message)}</div>`;
    // 커스텀 렌더링 로직
    return html;
}

// 2. Registry에 등록
const dataTypeFormatters = {
    // ...기존 항목들
    'your_new_type': formatYourNewType,  // <-- 추가
};
```

**중요**: `frontend/src/main.js`와 `frontend/static/app.js` 두 파일 모두 동기화해야 합니다.

## Generic Formatter 자동 렌더링

`data_type`이 없거나 등록되지 않은 경우, Generic Formatter가 자동으로:

1. **배열 데이터**: 테이블로 렌더링
2. **단순 객체**: 키-값 쌍으로 렌더링
3. **복잡한 객체**: JSON 펼치기 뷰

따라서 새 MCP 서버 추가 시 **프론트엔드 수정 없이도** 기본적인 표시가 가능합니다.

## 예시: 새 MCP 서버 "Stock" 추가

### Step 1: MCP 서버 구현

```python
# mcp_servers/stock/server.py
@mcp.tool()
def get_stock_price(symbol: str) -> dict:
    # ... API 호출
    return {
        "success": True,
        "symbol": symbol,
        "price": 150.25,
        "change": 2.5,
        "change_percent": 1.69
    }
```

### Step 2: Planner 프롬프트 업데이트

```python
# src/orchestration/planner.py
# data_type 목록에 추가:
- "stock" - for stock price information
```

### Step 3: 테스트

Generic formatter가 자동으로 키-값 쌍으로 표시:
```
Symbol: AAPL
Price: 150.25
Change: 2.5
Change Percent: 1.69
```

### Step 4: (선택) 커스텀 Formatter

더 예쁜 UI가 필요하면 `formatStockData` 함수 추가.

## 관련 파일 위치

| 파일 | 역할 |
|------|------|
| `src/orchestration/planner.py` | LLM 프롬프트, data_type 정의 |
| `src/orchestration/orchestrator.py` | data_type 추출 및 전달 |
| `src/orchestration/event_emitter.py` | 프론트엔드로 이벤트 전송 |
| `frontend/src/main.js` | Formatter Registry, 렌더링 함수 |
| `frontend/static/app.js` | main.js와 동일 (동기화 필요) |
