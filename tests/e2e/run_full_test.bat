@echo off
REM 전체 테스트를 실행하는 올인원 Windows 배치 파일
REM 서버 시작 -> 테스트 실행 -> 서버 중지를 자동으로 수행

setlocal enabledelayedexpansion

set PROJECT_ROOT=%~dp0..\..\
set SCRIPT_DIR=%~dp0

REM API 키 확인
if "%OPENROUTER_API_KEY%"=="" (
    echo ❌ Error: OPENROUTER_API_KEY environment variable is not set
    echo.
    echo Usage:
    echo   set OPENROUTER_API_KEY=your-api-key-here
    echo   %~nx0
    echo.
    echo Or:
    echo   set OPENROUTER_API_KEY=your-api-key-here ^&^& %~nx0
    exit /b 1
)

echo ======================================
echo 프론트엔드 질문 전체 테스트 시작
echo ======================================
echo.

REM 서버 시작
echo Step 1/3: Starting all servers...
call "%SCRIPT_DIR%start_all_servers.bat"

REM 테스트 실행
echo.
echo Step 2/3: Running tests...
cd /d "%PROJECT_ROOT%"
python tests\e2e\test_frontend_questions.py --api-key "%OPENROUTER_API_KEY%" --base-url "http://localhost:8000"

set TEST_RESULT=%ERRORLEVEL%

REM 서버 중지
echo.
echo Step 3/3: Stopping all servers...
call "%SCRIPT_DIR%stop_all_servers.bat"

REM 결과 요약
echo.
echo ======================================
if %TEST_RESULT% EQU 0 (
    echo ✅ 테스트 완료!
) else (
    echo ⚠️  테스트 중 일부 오류 발생
)
echo ======================================

REM 최신 결과 파일 표시
cd /d "%PROJECT_ROOT%"
for /f "delims=" %%i in ('dir /b /o-d test_results_*.json 2^>nul') do (
    set LATEST_RESULT=%%i
    goto :found
)
:found

if not "%LATEST_RESULT%"=="" (
    echo.
    echo 결과 파일: %LATEST_RESULT%
    echo.
    echo 상세 결과 확인:
    echo   type %LATEST_RESULT%
)

endlocal
exit /b %TEST_RESULT%
