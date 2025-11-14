@echo off
setlocal enabledelayedexpansion

REM Check status of all MCP servers

echo ========================================
echo MCP Servers Status
echo ========================================
echo.

REM PID file directory
set PID_DIR=logs\pids

if not exist "%PID_DIR%" (
    echo No MCP servers have been started yet
    exit /b 0
)

REM MCP server names
set MCP_SERVERS=calculator_agent calendar_agent jira_agent mail_agent rpa_agent

set RUNNING=0
set STOPPED=0

for %%s in (%MCP_SERVERS%) do (
    set PID_FILE=%PID_DIR%\%%s.pid

    if exist "!PID_FILE!" (
        set /p PID=<"!PID_FILE!"

        REM Check if process is running
        tasklist /FI "PID eq !PID!" 2>NUL | find /I /N "python.exe">NUL
        if not errorlevel 1 (
            echo [OK] %%s: Running (PID: !PID!^)
            set /a RUNNING+=1
        ) else (
            echo [ERROR] %%s: Stopped (stale PID file^)
            set /a STOPPED+=1
        )
    ) else (
        echo [INFO] %%s: Not started
        set /a STOPPED+=1
    )
)

echo.
echo ========================================
echo Summary: !RUNNING! running, !STOPPED! stopped
echo ========================================
echo.

endlocal
