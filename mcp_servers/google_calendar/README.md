# Google Calendar MCP Server

Google Calendar API를 사용한 실제 캘린더 통합 MCP 서버입니다.

## 기능

- **list_calendars**: 사용자의 모든 캘린더 목록 조회
- **list_events**: 기간별 이벤트 목록 조회 (검색 포함)
- **get_event**: 특정 이벤트 상세 조회
- **create_event**: 새 이벤트 생성
- **update_event**: 기존 이벤트 수정
- **delete_event**: 이벤트 삭제
- **quick_add_event**: 자연어로 빠르게 이벤트 추가
- **find_free_time**: 빈 시간대 찾기

## 설정

### 1. Google Cloud Console에서 API 활성화

1. [Google Cloud Console](https://console.cloud.google.com/)에 접속
2. 프로젝트 생성 또는 선택
3. **APIs & Services** > **Library** 이동
4. "Google Calendar API" 검색 후 **Enable** 클릭

### 2. OAuth 2.0 인증 정보 생성

1. **APIs & Services** > **Credentials** 이동
2. **Create Credentials** > **OAuth client ID** 클릭
3. Application type: **Desktop app** 선택
4. Name: `Personal Assistant` 입력
5. **Create** 클릭
6. JSON 파일 다운로드

### 3. 인증 설정

```bash
# 다운로드한 JSON 파일을 설정 디렉토리로 복사
mkdir -p ~/.config/personal-assistant
cp ~/Downloads/client_secret_*.json ~/.config/personal-assistant/google_calendar_credentials.json

# OAuth 설정 실행
cd mcp_servers/google_calendar
python setup_oauth.py setup
```

브라우저에서 Google 로그인 후 권한을 승인하면 설정이 완료됩니다.

### 4. 인증 상태 확인

```bash
python setup_oauth.py status
```

## 서버 실행

```bash
# 직접 실행 (포트 8010)
python server.py

# 또는 모듈로 실행
python -m mcp_servers.google_calendar.server
```

## MCP 도구 사용 예시

### 이벤트 목록 조회
```python
# 오늘부터 7일간의 이벤트
list_events()

# 특정 기간의 이벤트
list_events(time_min="2025-01-01", time_max="2025-01-31")

# 키워드로 검색
list_events(query="회의")
```

### 이벤트 생성
```python
create_event(
    summary="팀 미팅",
    start_time="2025-01-15 14:00",
    end_time="2025-01-15 15:00",
    description="주간 팀 미팅",
    location="회의실 A",
    attendees=["colleague@example.com"]
)
```

### 자연어로 빠른 이벤트 생성
```python
# Google이 자동으로 시간과 장소를 파싱
quick_add_event("내일 오후 3시에 서울역에서 미팅")
```

### 빈 시간대 찾기
```python
# 1시간 짜리 미팅 가능한 시간 찾기
find_free_time(duration_minutes=60)

# 근무 시간 지정
find_free_time(
    duration_minutes=30,
    working_hours_start=10,
    working_hours_end=17
)
```

## 환경 변수 (선택)

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `GOOGLE_CALENDAR_TOKEN_FILE` | 토큰 파일 경로 | `~/.config/personal-assistant/google_calendar_token.json` |
| `GOOGLE_CALENDAR_CREDENTIALS_FILE` | 인증 정보 파일 경로 | `~/.config/personal-assistant/google_calendar_credentials.json` |

## 문제 해결

### "Credentials file not found" 오류
- OAuth 인증 정보 JSON 파일이 올바른 위치에 있는지 확인
- `setup_oauth.py setup --client-secrets /path/to/credentials.json` 사용

### "Token expired" 오류
- 토큰이 만료됨. `setup_oauth.py setup` 재실행

### "Access denied" 오류
- Google Cloud Console에서 Google Calendar API가 활성화되어 있는지 확인
- OAuth consent screen 설정 확인

### 인증 초기화
```bash
python setup_oauth.py revoke
python setup_oauth.py setup
```
