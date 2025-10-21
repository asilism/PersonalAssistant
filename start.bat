@echo off
REM Start the Personal Assistant Orchestration Service (Windows)

echo ========================================
echo Personal Assistant Orchestration Service
echo ========================================
echo.

REM Check if .env file exists
if not exist .env (
    echo Error: .env file not found
    echo Please copy .env.example to .env and configure your API keys:
    echo   copy .env.example .env
    echo.
    exit /b 1
)

echo Installing dependencies...
pip install -r requirements.txt >nul 2>&1

if errorlevel 1 (
    echo Error: Failed to install dependencies
    exit /b 1
)

echo Dependencies installed
echo.
echo Starting Web UI and API Server...
echo.
echo Available at:
echo   - Web UI:       http://localhost:8000
echo   - API Docs:     http://localhost:8000/docs
echo   - Health Check: http://localhost:8000/api/health
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start the server
python src\api_server.py
