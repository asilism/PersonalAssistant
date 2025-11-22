@echo off
REM 모든 서버를 중지하는 Windows 배치 파일

echo ==================================
echo Stopping all servers...
echo ==================================

REM API 서버 중지
echo Stopping API server...
taskkill /F /FI "WINDOWTITLE eq API Server*" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   √ API Server stopped
) else (
    echo   - API Server not running
)

REM Calculator Agent 중지
echo Stopping Calculator Agent...
taskkill /F /FI "WINDOWTITLE eq Calculator Agent*" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   √ Calculator Agent stopped
) else (
    echo   - Calculator Agent not running
)

REM Mail Agent 중지
echo Stopping Mail Agent...
taskkill /F /FI "WINDOWTITLE eq Mail Agent*" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   √ Mail Agent stopped
) else (
    echo   - Mail Agent not running
)

REM Calendar Agent 중지
echo Stopping Calendar Agent...
taskkill /F /FI "WINDOWTITLE eq Calendar Agent*" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   √ Calendar Agent stopped
) else (
    echo   - Calendar Agent not running
)

REM Jira Agent 중지
echo Stopping Jira Agent...
taskkill /F /FI "WINDOWTITLE eq Jira Agent*" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   √ Jira Agent stopped
) else (
    echo   - Jira Agent not running
)

REM RPA Agent 중지
echo Stopping RPA Agent...
taskkill /F /FI "WINDOWTITLE eq RPA Agent*" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   √ RPA Agent stopped
) else (
    echo   - RPA Agent not running
)

timeout /t 2 >nul

echo.
echo ==================================
echo All servers stopped!
echo ==================================
