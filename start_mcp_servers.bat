@echo off
REM Start all MCP servers for Personal Assistant
REM This script launches all MCP servers in the background

echo ========================================
echo Starting MCP Servers
echo ========================================
echo.

REM Directory containing MCP servers
set MCP_DIR=mcp_servers

REM Log directory
set LOG_DIR=logs\mcp
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM PID file directory
set PID_DIR=logs\pids
if not exist "%PID_DIR%" mkdir "%PID_DIR%"

REM Array of MCP server directories
set MCP_SERVERS=calculator_agent calendar_agent jira_agent mail_agent rpa_agent

echo Starting MCP servers...
echo.

REM Start each server
for %%s in (%MCP_SERVERS%) do (
    call :start_server %%s
)

echo.
echo ========================================
echo MCP Servers Started
echo ========================================
echo.
echo Log files: %LOG_DIR%\
echo PID files: %PID_DIR%\
echo.
echo To stop all servers, run: stop_mcp_servers.bat
echo To check server status, run: status_mcp_servers.bat
echo.

goto :eof

:start_server
set SERVER_NAME=%1
set SERVER_PATH=%MCP_DIR%\%SERVER_NAME%
set LOG_FILE=%LOG_DIR%\%SERVER_NAME%.log
set PID_FILE=%PID_DIR%\%SERVER_NAME%.pid

REM Check if already running
if exist "%PID_FILE%" (
    set /p PID=<"%PID_FILE%"
    tasklist /FI "PID eq !PID!" 2>NUL | find /I /N "python.exe">NUL
    if not errorlevel 1 (
        echo [WARNING] %SERVER_NAME% is already running (PID: !PID!^)
        goto :eof
    ) else (
        del "%PID_FILE%"
    )
)

REM Check if server.py exists
if not exist "%SERVER_PATH%\server.py" (
    echo [ERROR] %SERVER_NAME%: server.py not found
    goto :eof
)

REM Start the server in background
pushd "%SERVER_PATH%"
start /B python server.py > "..\..\%LOG_FILE%" 2>&1
popd

REM Get the PID of the started process
REM Note: Windows doesn't have a simple way to get PID of background process
REM We'll use a workaround by finding the most recent python.exe process
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /NH ^| find /I "python.exe"') do (
    set PID=%%a
    goto :found_pid
)

:found_pid
echo %PID% > "%PID_FILE%"

REM Wait a moment and check if process is still running
timeout /t 1 /nobreak > NUL
tasklist /FI "PID eq %PID%" 2>NUL | find /I /N "python.exe">NUL
if not errorlevel 1 (
    echo [OK] Started %SERVER_NAME% (PID: %PID%^)
) else (
    echo [ERROR] Failed to start %SERVER_NAME%
    if exist "%PID_FILE%" del "%PID_FILE%"
)

goto :eof
