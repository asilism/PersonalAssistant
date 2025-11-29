@echo off
setlocal enabledelayedexpansion

:: Start All MCP Servers
:: This script starts all MCP servers in the background

echo ========================================
echo MCP Servers - Startup Script
echo ========================================
echo.

:: Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: Log directory
set "LOG_DIR=%SCRIPT_DIR%logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

:: PID file
set "PID_FILE=%LOG_DIR%\mcp_servers.pid"

:: Parse command line arguments
if "%~1"=="stop" goto :stop_servers
if "%~1"=="status" goto :show_status
if "%~1"=="-h" goto :show_help
if "%~1"=="--help" goto :show_help

:: Load .env file if exists
if exist "%SCRIPT_DIR%.env" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%SCRIPT_DIR%.env") do (
        set "%%a=%%b"
    )
    echo Environment loaded from .env
)

:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed
    exit /b 1
)

:: Clear previous PID file
if exist "%PID_FILE%" del "%PID_FILE%"

echo.
echo Starting MCP servers...
echo.

:: Start Google Calendar server (port 8010)
echo Starting google-calendar server...
start /b "" python "%SCRIPT_DIR%mcp_servers\google_calendar\server.py" > "%LOG_DIR%\google-calendar.log" 2>&1
echo   [OK] google-calendar starting on port 8010

:: Start YouTube Music server (port 8011)
echo Starting youtube-music server...
start /b "" python "%SCRIPT_DIR%mcp_servers\youtube_music\server.py" > "%LOG_DIR%\youtube-music.log" 2>&1
echo   [OK] youtube-music starting on port 8011

:: Start Weather server (port 8012)
echo Starting weather server...
start /b "" python "%SCRIPT_DIR%mcp_servers\weather\server.py" > "%LOG_DIR%\weather-music.log" 2>&1
echo   [OK] weather starting on port 8012

:: Wait a moment for servers to start
timeout /t 2 /nobreak >nul

echo.
echo ========================================
echo MCP Servers Starting
echo ========================================
echo.
echo Server URLs:
echo   - google-calendar: http://localhost:8010
echo   - youtube-music:   http://localhost:8011
echo   - weather:         http://localhost:8012
echo.
echo Log files: %LOG_DIR%\
echo.
echo To stop servers, close this window or run:
echo   %~nx0 stop
echo ========================================

goto :eof

:stop_servers
echo.
echo Stopping MCP servers...

:: Kill Python processes on MCP ports
for %%p in (8010 8011 8012) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%%p ^| findstr LISTENING 2^>nul') do (
        taskkill /PID %%a /F >nul 2>&1
        echo   Stopped process on port %%p
    )
)

echo MCP servers stopped
goto :eof

:show_status
echo.
echo MCP Server Status:
echo ----------------------------------------

:: Check Google Calendar (8010)
netstat -ano | findstr :8010 | findstr LISTENING >nul 2>&1
if %errorlevel% equ 0 (
    echo   [RUNNING] google-calendar - http://localhost:8010
) else (
    echo   [STOPPED] google-calendar - port 8010
)

:: Check YouTube Music (8011)
netstat -ano | findstr :8011 | findstr LISTENING >nul 2>&1
if %errorlevel% equ 0 (
    echo   [RUNNING] youtube-music - http://localhost:8011
) else (
    echo   [STOPPED] youtube-music - port 8011
)

:: Check Weather (8012)
netstat -ano | findstr :8012 | findstr LISTENING >nul 2>&1
if %errorlevel% equ 0 (
    echo   [RUNNING] weather - http://localhost:8012
) else (
    echo   [STOPPED] weather - port 8012
)

echo ----------------------------------------
goto :eof

:show_help
echo Usage: %~nx0 [command]
echo.
echo Commands:
echo   (no args)  Start all MCP servers
echo   stop       Stop all running MCP servers
echo   status     Show status of MCP servers
echo.
goto :eof
