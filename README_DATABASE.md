# Database 관리 가이드

PersonalAssistant는 SQLite 데이터베이스를 사용하여 설정 및 데이터를 저장합니다.

## 데이터베이스 위치

- **DB 파일**: `data/settings.db`
- **암호화 키**: `data/.encryption_key`

## 저장되는 정보

### LLM 설정 (llm_settings 테이블)

데이터베이스에는 다음과 같은 LLM 설정이 저장됩니다:

1. **Provider** - LLM 제공자 (anthropic, openai, openrouter)
2. **API Key** - 암호화된 API 키
3. **Model** - 사용할 모델 이름
4. **Base URL** - 선택적 베이스 URL (커스텀 엔드포인트)

모든 설정은 `user_id`와 `tenant` 조합으로 관리됩니다.

## 보안

### API Key 암호화

- API Key는 Fernet 대칭 암호화를 사용하여 저장됩니다
- 암호화 키는 `data/.encryption_key` 파일에 저장됩니다
- 이 파일은 소유자만 읽을 수 있도록 권한이 설정됩니다 (chmod 600)

### 중요 보안 사항

⚠️ **절대로 다음 파일들을 git에 커밋하지 마세요:**
- `data/settings.db` - 암호화된 설정 데이터
- `data/.encryption_key` - 암호화 키
- `.env` - 환경 변수 파일

이 파일들은 이미 `.gitignore`에 포함되어 있습니다.

## 데이터베이스 스키마

### llm_settings 테이블

```sql
CREATE TABLE llm_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    tenant TEXT NOT NULL,
    provider TEXT NOT NULL,
    api_key_encrypted TEXT NOT NULL,
    model TEXT NOT NULL,
    base_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, tenant)
)
```

## 설정 관리

### Web UI를 통한 관리

가장 간편한 방법은 Web UI의 Settings 탭을 사용하는 것입니다:

1. `http://localhost:8000` 접속
2. **Settings** 탭 클릭
3. Provider, API Key, Model 선택
4. **Test Connection** 버튼으로 연결 테스트
5. **Save Settings** 버튼으로 저장

### API를 통한 관리

```bash
# 설정 조회
curl "http://localhost:8000/api/settings?user_id=test_user&tenant=test_tenant"

# 설정 저장
curl -X POST "http://localhost:8000/api/settings" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "anthropic",
    "api_key": "sk-ant-...",
    "model": "claude-3-5-sonnet-20241022",
    "base_url": null,
    "user_id": "test_user",
    "tenant": "test_tenant"
  }'

# 연결 테스트
curl -X POST "http://localhost:8000/api/settings/test" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "anthropic",
    "api_key": "sk-ant-...",
    "model": "claude-3-5-sonnet-20241022"
  }'
```

## 설정 우선순위

PersonalAssistant는 다음 순서로 설정을 불러옵니다:

1. **데이터베이스 설정** (우선)
2. **환경 변수** (.env 파일)

따라서 데이터베이스에 설정이 저장되어 있으면, 환경 변수보다 우선적으로 사용됩니다.

## 백업 및 복원

### 백업

```bash
# 데이터베이스 백업
cp data/settings.db data/settings.db.backup

# 암호화 키도 함께 백업
cp data/.encryption_key data/.encryption_key.backup
```

### 복원

```bash
# 데이터베이스 복원
cp data/settings.db.backup data/settings.db

# 암호화 키 복원
cp data/.encryption_key.backup data/.encryption_key
```

⚠️ **주의**: 암호화 키 없이는 저장된 API Key를 복호화할 수 없습니다!

## 데이터베이스 초기화

설정을 완전히 초기화하려면:

```bash
# 데이터베이스 삭제
rm data/settings.db

# 암호화 키 삭제 (새 키가 생성됩니다)
rm data/.encryption_key
```

다음 서버 시작 시 새 데이터베이스가 자동으로 생성됩니다.

## 문제 해결

### "No API key configured" 오류

1. Web UI의 Settings 탭에서 API Key 설정
2. 또는 .env 파일에 환경 변수 설정:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```

### 암호화 키 손실

암호화 키를 잃어버린 경우, 저장된 API Key를 복호화할 수 없습니다.
이 경우 데이터베이스를 초기화하고 설정을 다시 입력해야 합니다.

### 데이터베이스 손상

데이터베이스가 손상된 경우:

```bash
# SQLite 무결성 검사
sqlite3 data/settings.db "PRAGMA integrity_check;"

# 문제가 있으면 백업에서 복원하거나 초기화
```
