@echo off
REM Start Personal Assistant in Production Mode (Windows)

echo ========================================
echo Personal Assistant - Production Mode
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

echo Installing Python dependencies...
pip install -r requirements.txt >nul 2>&1

if errorlevel 1 (
    echo Error: Failed to install Python dependencies
    exit /b 1
)

echo Python dependencies installed

REM Check if Node.js is installed
where node >nul 2>&1
if errorlevel 1 (
    echo Error: Node.js is not installed
    echo Please install Node.js to build the frontend
    exit /b 1
)

REM Build frontend
echo Building frontend...
cd frontend
if not exist node_modules (
    call npm install >nul 2>&1
    if errorlevel 1 (
        echo Error: Failed to install frontend dependencies
        cd ..
        exit /b 1
    )
)

call npm run build
if errorlevel 1 (
    echo Error: Failed to build frontend
    cd ..
    exit /b 1
)
cd ..

echo Frontend built successfully
echo.
echo ========================================
echo Starting server...
echo ========================================
echo.
echo Available at:
echo   - Web UI:       http://localhost:8000
echo   - API Docs:     http://localhost:8000/docs
echo   - Health Check: http://localhost:8000/api/health
echo.
echo Press Ctrl+C to stop the server
echo.

REM Set production mode and start
set DEV_MODE=false
python src\api_server.py
