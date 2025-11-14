@echo off
REM Stop all MCP servers

echo ========================================
echo Stopping MCP Servers
echo ========================================
echo.

REM PID file directory
set PID_DIR=logs\pids

if not exist "%PID_DIR%" (
    echo No MCP servers are running
    exit /b 0
)

REM Check if there are any PID files
dir /b "%PID_DIR%\*.pid" >NUL 2>&1
if errorlevel 1 (
    echo No MCP servers are running
    exit /b 0
)

REM Stop each server
for %%f in ("%PID_DIR%\*.pid") do (
    set PID_FILE=%%f
    for %%n in (%%~nf) do set SERVER_NAME=%%n

    set /p PID=<"!PID_FILE!"

    REM Check if process is running
    tasklist /FI "PID eq !PID!" 2>NUL | find /I /N "python.exe">NUL
    if not errorlevel 1 (
        echo Stopping !SERVER_NAME! (PID: !PID!^)...
        taskkill /PID !PID! /T /F >NUL 2>&1

        REM Wait for process to stop
        timeout /t 2 /nobreak > NUL

        REM Check if stopped
        tasklist /FI "PID eq !PID!" 2>NUL | find /I /N "python.exe">NUL
        if errorlevel 1 (
            echo [OK] Stopped !SERVER_NAME!
        ) else (
            echo [WARNING] Failed to stop !SERVER_NAME!
        )
    ) else (
        echo [WARNING] !SERVER_NAME! is not running
    )

    del "!PID_FILE!"
)

echo.
echo ========================================
echo All MCP Servers Stopped
echo ========================================
echo.
