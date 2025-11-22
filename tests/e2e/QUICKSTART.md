# 🚀 빠른 시작 가이드

프론트엔드 15개 질문을 gpt-oss-20b로 자동 테스트하는 가장 빠른 방법입니다.

## ⚡ 원클릭 실행

### 🪟 Windows

```cmd
cd C:\path\to\PersonalAssistant

REM API 키 설정 후 실행
set OPENROUTER_API_KEY=sk-or-v1-YOUR-API-KEY
tests\e2e\run_full_test.bat
```

### 🐧 Linux / 🍎 macOS

```bash
cd /home/user/PersonalAssistant

# API 키 설정 후 실행
export OPENROUTER_API_KEY="sk-or-v1-YOUR-API-KEY"
./tests/e2e/run_full_test.sh
```

### 🐍 Python (크로스 플랫폼)

```bash
# Windows/Linux/macOS 모두 동일
set OPENROUTER_API_KEY=your-key  # Windows
export OPENROUTER_API_KEY=your-key  # Linux/Mac

python tests/e2e/start_servers.py
python tests/e2e/test_frontend_questions.py
python tests/e2e/stop_servers.py
```

끝! 🎉

## 📝 단계별 설명

### 방법 1️⃣: 올인원 스크립트 (추천)

#### 🪟 Windows
```cmd
REM 1. API 키 환경변수 설정
set OPENROUTER_API_KEY=sk-or-v1-YOUR-API-KEY

REM 2. 테스트 실행 (서버 시작/테스트/서버 중지 자동)
cd C:\path\to\PersonalAssistant
tests\e2e\run_full_test.bat
```

#### 🐧 Linux / 🍎 macOS
```bash
# 1. API 키 환경변수 설정
export OPENROUTER_API_KEY="sk-or-v1-YOUR-API-KEY"

# 2. 테스트 실행 (서버 시작/테스트/서버 중지 자동)
cd /home/user/PersonalAssistant
./tests/e2e/run_full_test.sh
```

### 방법 2️⃣: 수동 실행

#### 🪟 Windows

##### 1단계: 서버 시작
```cmd
cd C:\path\to\PersonalAssistant
tests\e2e\start_all_servers.bat
```

##### 2단계: 테스트 실행
```cmd
python tests\e2e\test_frontend_questions.py --api-key "sk-or-v1-YOUR-API-KEY"
```

##### 3단계: 서버 중지
```cmd
tests\e2e\stop_all_servers.bat
```

#### 🐧 Linux / 🍎 macOS

##### 1단계: 서버 시작
```bash
cd /home/user/PersonalAssistant
./tests/e2e/start_all_servers.sh
```

##### 2단계: 테스트 실행
```bash
python tests/e2e/test_frontend_questions.py --api-key "sk-or-v1-YOUR-API-KEY"
```

##### 3단계: 서버 중지
```bash
./tests/e2e/stop_all_servers.sh
```

#### 🐍 Python (모든 플랫폼)

##### 1단계: 서버 시작
```bash
python tests/e2e/start_servers.py
```

##### 2단계: 테스트 실행
```bash
python tests/e2e/test_frontend_questions.py --api-key "your-key"
```

##### 3단계: 서버 중지
```bash
python tests/e2e/stop_servers.py
```

## 📊 결과 확인

테스트 완료 후 자동으로 생성되는 파일:
- `test_results_YYYYMMDD_HHMMSS.json` - 전체 결과
- `failures_YYYYMMDD_HHMMSS.json` - 실패한 케이스만 (있을 경우)

결과 요약:
```
총 질문 수: 15
✓ 성공: 12
✗ 실패: 3
성공률: 80.0%

전체 결과 저장됨: test_results_20251122_130000.json
실패 케이스 저장됨: failures_20251122_130000.json
👉 이 파일을 Claude에게 제공하여 문제를 수정하세요!
```

## 🔄 실패한 케이스 수정하기

실패한 케이스가 있다면:

```bash
# 1. failures 파일 확인
cat failures_20251122_130000.json

# 2. Claude에게 제공
# Claude Code에서 다음과 같이 요청:
```

**Claude에게:**
```
/home/user/PersonalAssistant/failures_20251122_130000.json

이 파일을 읽고 실패한 케이스들을 분석해서 자동으로 수정해줘.
```

Claude가 자동으로:
1. 실패 원인 분석
2. 관련 코드 수정
3. Git 커밋
4. 재테스트 안내

다시 테스트 실행:
```bash
./tests/e2e/run_full_test.sh
```

**100% 성공률까지 반복!** 🎯

상세한 워크플로우: [WORKFLOW.md](./WORKFLOW.md)

## 🔧 문제 해결

### "permission denied" 오류
```bash
chmod +x tests/e2e/*.sh
```

### "connection refused" 오류
서버가 완전히 시작될 때까지 10-15초 기다리세요.

### 로그 확인
```bash
tail -f logs/api_server.log
tail -f logs/calculator_agent.log
```

## 💡 팁

### 특정 질문만 테스트하고 싶다면?

`frontend_questions.json` 파일을 수정하세요:
```json
{
  "questions": [
    {
      "id": 1,
      "question": "테스트하고 싶은 질문"
    }
  ]
}
```

### 다른 모델로 테스트하고 싶다면?

`test_frontend_questions.py` 파일에서 `MODEL` 변수 수정:
```python
MODEL = "anthropic/claude-3-sonnet"  # 또는 다른 모델
```

## 📞 도움이 필요하신가요?

상세한 가이드: [README.md](./README.md)
