# ⚙️ 초기 설정 가이드

테스트를 실행하기 전에 필요한 설정입니다.

---

## 📋 필수 설정

### 1. `.env.validator` 파일 생성

LLM 기반 검증을 사용하려면 Claude API 키가 필요합니다.

#### 🪟 Windows

**PowerShell (추천 - UTF-8 인코딩 보장):**
```powershell
cd C:\Develop\PersonalAssistant

# UTF-8로 파일 생성
@"
CLAUDE_API_KEY=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
CLAUDE_MODEL=claude-sonnet-4-5-20250929
"@ | Out-File -FilePath ".env.validator" -Encoding UTF8 -NoNewline
```

**또는 메모장 사용:**
1. 메모장 열기
2. 다음 내용 입력:
   ```
   CLAUDE_API_KEY=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
   CLAUDE_MODEL=claude-sonnet-4-5-20250929
   ```
3. `C:\Develop\PersonalAssistant\.env.validator`로 저장
4. **중요**: 인코딩을 **UTF-8**로 선택

#### 🐧 Linux / 🍎 macOS

```bash
cd /home/user/PersonalAssistant

cat > .env.validator << 'EOF'
CLAUDE_API_KEY=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
CLAUDE_MODEL=claude-sonnet-4-5-20250929
EOF
```

#### ✅ 확인

파일이 올바르게 생성되었는지 확인:

**Windows:**
```cmd
type .env.validator
```

**Linux/macOS:**
```bash
cat .env.validator
```

**출력 예시:**
```
CLAUDE_API_KEY=sk-ant-api03-...
CLAUDE_MODEL=claude-sonnet-4-5-20250929
```

---

### 2. OpenRouter API 키 환경변수 설정

테스트할 모델(gpt-oss-20b)의 API 키를 설정합니다.

#### 🪟 Windows

```cmd
set OPENROUTER_API_KEY=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
```

**영구 설정 (선택사항):**
```cmd
setx OPENROUTER_API_KEY "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"
```

#### 🐧 Linux / 🍎 macOS

```bash
export OPENROUTER_API_KEY="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"
```

**영구 설정 (선택사항):**
```bash
# ~/.bashrc 또는 ~/.zshrc에 추가
echo 'export OPENROUTER_API_KEY="sk-or-v1-..."' >> ~/.bashrc
source ~/.bashrc
```

---

## 🔍 설정 확인

### .env.validator 파일 확인

**위치:** 프로젝트 루트 디렉토리 (`PersonalAssistant/.env.validator`)

**내용:**
```
CLAUDE_API_KEY=sk-ant-api03-...
CLAUDE_MODEL=claude-sonnet-4-5-20250929
```

**주의:** 이 파일은 `.gitignore`에 포함되어 Git에 커밋되지 않습니다.

### 환경변수 확인

**Windows:**
```cmd
echo %OPENROUTER_API_KEY%
```

**Linux/macOS:**
```bash
echo $OPENROUTER_API_KEY
```

---

## ⚠️ 주의사항

### API 키 보안

- ✅ `.env.validator` 파일은 Git에 커밋되지 않습니다
- ✅ API 키를 절대 공유하지 마세요
- ✅ 코드에 직접 하드코딩하지 마세요

### Windows 파일 확장자

Windows에서 파일을 생성할 때 `.env.validator.txt`가 되지 않도록 주의하세요.

**확인 방법:**
```cmd
dir .env.*
```

**출력:**
```
.env.validator        <--- 정상
.env.validator.txt    <--- 잘못됨! .txt 제거 필요
```

---

## 🚫 LLM 검증 없이 사용하기

`.env.validator` 파일 없이도 테스트를 실행할 수 있습니다:

- ⚠️ 규칙 기반 검증으로 자동 전환됩니다
- ⚠️ LLM 검증보다 정확도가 낮습니다
- ✅ 빠르고 무료입니다
- ✅ 테스트는 정상적으로 실행됩니다

**출력:**
```
⚠ .env.validator 파일이 없습니다. 규칙 기반 검증만 사용됩니다.
검증: 규칙 기반
```

---

## 📚 다음 단계

설정이 완료되었으면 테스트를 실행하세요:

👉 [QUICKSTART.md](./QUICKSTART.md)
