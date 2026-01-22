# Browser-Use MCP Server

AI 에이전트가 웹 브라우저를 제어하여 복잡한 작업을 자동으로 수행하는 MCP 서버입니다.

## 특징

- 🤖 **AI 에이전트 기반**: 자연어로 task를 지시하면 AI가 브라우저를 자동으로 조작
- 🌐 **복잡한 웹 작업**: 로그인, 폼 작성, 검색, 데이터 추출 등 다단계 작업 지원
- 🚀 **고성능**: ChatBrowserUse 사용 시 3-5배 빠른 작업 완료
- 🔌 **다중 LLM 지원**: ChatBrowserUse, OpenAI, Anthropic 등 선택 가능
- ☁️ **클라우드 옵션**: Browser Use Cloud를 통한 stealth 브라우저 지원 (CAPTCHA 우회)

## 설치

```bash
cd /home/user/PersonalAssistant/mcp_servers/browser_use
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium
```

## 설정

### 1. 환경 변수 설정

`.env` 파일에 다음을 추가:

```bash
# Browser Use Cloud API 키 (권장 - 무료 $10 크레딧 제공)
BROWSER_USE_API_KEY=your-api-key-here

# 또는 다른 LLM 제공자 선택
BROWSER_USE_LLM_PROVIDER=openai  # chat_browser_use, openai, anthropic 중 선택
OPENAI_API_KEY=your-openai-key
# ANTHROPIC_API_KEY=your-anthropic-key

# 선택 사항: 모델 지정
# OPENAI_MODEL=gpt-4o
# ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

### 2. LLM 제공자 비교

| 제공자 | 장점 | 단점 | 가격 |
|--------|------|------|------|
| **ChatBrowserUse** | 가장 빠르고 정확 (3-5배), 브라우저 자동화 최적화 | 유료 | $0.20/1M input, $2.00/1M output |
| **OpenAI** | 범용적, 품질 우수 | 느림 | 모델에 따라 다름 |
| **Anthropic** | 추론 능력 우수 | 느림 | 모델에 따라 다름 |

## 사용 방법

### MCP 서버 시작

```bash
python server.py
```

서버는 `http://0.0.0.0:8016`에서 실행됩니다.

### Available Tools

#### 1. `browse_with_agent`

자연어 task를 받아 AI 에이전트가 브라우저를 조작하여 작업을 수행합니다.

**파라미터:**
- `task` (필수): 수행할 작업을 자연어로 기술
- `llm_provider` (선택): LLM 제공자 (기본: "chat_browser_use")
- `llm_model` (선택): 모델 이름
- `llm_api_key` (선택): API 키 (환경 변수에서 자동 로드 가능)
- `headless` (선택): 헤드리스 모드 (기본: True)
- `use_cloud` (선택): Browser Use Cloud 사용 (기본: False)
- `max_steps` (선택): 최대 단계 수 (기본: 100)
- `timeout` (선택): 타임아웃 (초, 기본: 300)

**예시:**

```json
{
  "task": "구글에서 '날씨'를 검색하고 서울의 현재 온도를 찾아줘",
  "llm_provider": "chat_browser_use",
  "headless": true
}
```

```json
{
  "task": "아마존에서 '무선 마우스'를 검색하고 가격순으로 정렬한 후 상위 3개 제품의 이름과 가격을 알려줘",
  "llm_provider": "openai",
  "llm_model": "gpt-4o"
}
```

#### 2. `check_browser_use_status`

서버 상태 및 설정을 확인합니다.

**예시 응답:**

```json
{
  "success": true,
  "status": {
    "browser_use_installed": true,
    "openai_available": true,
    "anthropic_available": false,
    "api_keys": {
      "BROWSER_USE_API_KEY": true,
      "OPENAI_API_KEY": true,
      "ANTHROPIC_API_KEY": false
    },
    "default_llm_provider": "chat_browser_use",
    "browser_running": false
  }
}
```

#### 3. `close_browser_session`

현재 실행 중인 브라우저 세션을 종료합니다.

## 사용 예시

### 예시 1: 정보 검색

**Task:** "네이버에서 '삼성전자 주가'를 검색하고 현재 주가를 알려줘"

### 예시 2: 온라인 쇼핑

**Task:** "쿠팡에서 '노트북'을 검색하고 평점이 가장 높은 제품의 이름, 가격, 평점을 알려줘"

### 예시 3: 폼 작성

**Task:** "example.com/contact에 가서 이름 필드에 'John', 이메일 필드에 'john@example.com'을 입력하고 제출 버튼을 눌러줘"

### 예시 4: 데이터 추출

**Task:** "github.com/browser-use/browser-use에 가서 star 수를 알려줘"

## 기존 browser MCP 서버와의 차이점

| 기능 | browser (기존) | browser-use (새) |
|------|----------------|------------------|
| **접근 방식** | 정적 스크래핑 | AI 에이전트 자동화 |
| **복잡한 작업** | 제한적 | 다단계 작업 가능 |
| **JavaScript** | Playwright 필요 | 기본 지원 |
| **로그인/세션** | 수동 구현 필요 | 자동 처리 |
| **자연어 인터페이스** | 없음 | 핵심 기능 |
| **속도** | 빠름 | ChatBrowserUse 사용 시 3-5배 빠름 |
| **비용** | 무료 | LLM 사용료 발생 |

## 비용 관리

### ChatBrowserUse 사용 시
- 무료 $10 크레딧으로 시작 가능
- 간단한 작업: ~$0.01-0.05
- 복잡한 작업: ~$0.10-0.50

### OpenAI/Anthropic 사용 시
- 각 제공자의 가격 정책 참고
- 일반적으로 ChatBrowserUse보다 비쌀 수 있음

## 문제 해결

### 1. API 키 오류

```
ValueError: BROWSER_USE_API_KEY가 설정되지 않았습니다.
```

**해결:** `.env` 파일에 API 키를 추가하거나 `llm_api_key` 파라미터로 전달

### 2. LLM 제공자 설치 오류

```
RuntimeError: langchain-openai가 설치되지 않았습니다.
```

**해결:**
```bash
pip install langchain-openai  # OpenAI 사용 시
pip install langchain-anthropic  # Anthropic 사용 시
```

### 3. 타임아웃

작업이 300초 내에 완료되지 않으면 타임아웃됩니다.

**해결:** `timeout` 파라미터를 늘리거나 task를 더 작은 단위로 분할

## 포트

- **8016**: Browser-Use MCP 서버

## 참고 자료

- [browser-use GitHub](https://github.com/browser-use/browser-use)
- [browser-use PyPI](https://pypi.org/project/browser-use/)
- [Browser Use Cloud](https://browseruse.com/)
