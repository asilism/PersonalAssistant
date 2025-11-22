@echo off
REM 모든 서버를 백그라운드로 실행하는 Windows 배치 파일

setlocal enabledelayedexpansion

set PROJECT_ROOT=%~dp0..\..\
set LOG_DIR=%PROJECT_ROOT%logs

echo ==================================
echo Starting all servers...
echo ==================================

REM 로그 디렉토리 생성
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM 기존 서버 프로세스 종료
echo Stopping existing servers...
taskkill /F /FI "WINDOWTITLE eq API Server*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Calculator Agent*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Mail Agent*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Calendar Agent*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Jira Agent*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq RPA Agent*" >nul 2>&1
timeout /t 2 >nul

REM API 서버 시작
echo Starting API server...
cd /d "%PROJECT_ROOT%"
set PYTHONPATH=%PROJECT_ROOT%src
start "API Server" cmd /c "python src\api_server.py > logs\api_server.log 2>&1"
echo   API Server started

REM Calculator Agent 시작
echo Starting Calculator Agent...
cd /d "%PROJECT_ROOT%mcp_servers\calculator_agent"
set PYTHONPATH=%CD%
start "Calculator Agent" cmd /c "python server.py > ..\..\logs\calculator_agent.log 2>&1"
echo   Calculator Agent started

REM Mail Agent 시작
echo Starting Mail Agent...
cd /d "%PROJECT_ROOT%mcp_servers\mail_agent"
set PYTHONPATH=%CD%
start "Mail Agent" cmd /c "python server.py > ..\..\logs\mail_agent.log 2>&1"
echo   Mail Agent started

REM Calendar Agent 시작
echo Starting Calendar Agent...
cd /d "%PROJECT_ROOT%mcp_servers\calendar_agent"
set PYTHONPATH=%CD%
start "Calendar Agent" cmd /c "python server.py > ..\..\logs\calendar_agent.log 2>&1"
echo   Calendar Agent started

REM Jira Agent 시작
echo Starting Jira Agent...
cd /d "%PROJECT_ROOT%mcp_servers\jira_agent"
set PYTHONPATH=%CD%
start "Jira Agent" cmd /c "python server.py > ..\..\logs\jira_agent.log 2>&1"
echo   Jira Agent started

REM RPA Agent 시작
echo Starting RPA Agent...
cd /d "%PROJECT_ROOT%mcp_servers\rpa_agent"
set PYTHONPATH=%CD%
start "RPA Agent" cmd /c "python server.py > ..\..\logs\rpa_agent.log 2>&1"
echo   RPA Agent started

REM 서버 시작 대기
echo.
echo Waiting for servers to start (15 seconds)...
timeout /t 15 >nul

echo.
echo ==================================
echo All servers started!
echo ==================================
echo.
echo Logs are available in: %LOG_DIR%
echo.
echo To run tests:
echo   cd %PROJECT_ROOT%
echo   python tests\e2e\test_frontend_questions.py
echo.
echo To stop all servers:
echo   tests\e2e\stop_all_servers.bat
echo.

endlocal
