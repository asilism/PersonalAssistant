@echo off
REM Start Personal Assistant in Development Mode (Windows)
REM This script runs both Vite (frontend) and FastAPI (backend) simultaneously

echo ========================================
echo Personal Assistant - Development Mode
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

REM Check if Node.js is installed
where node >nul 2>&1
if errorlevel 1 (
    echo Error: Node.js is not installed
    echo Please install Node.js to use Vite for frontend development
    exit /b 1
)

echo Installing Python dependencies...
pip install -r requirements.txt >nul 2>&1
if errorlevel 1 (
    echo Error: Failed to install Python dependencies
    exit /b 1
)
echo Python dependencies installed

REM Install frontend dependencies
echo Installing frontend dependencies...
cd frontend
if not exist node_modules (
    call npm install >nul 2>&1
    if errorlevel 1 (
        echo Error: Failed to install frontend dependencies
        cd ..
        exit /b 1
    )
)
echo Frontend dependencies installed
cd ..

echo.
echo ========================================
echo Starting servers...
echo ========================================
echo.
echo   Frontend (Vite):   http://localhost:5173  ^<-- Open this!
echo   Backend (FastAPI): http://localhost:8000
echo   API Docs:          http://localhost:8000/docs
echo.
echo   Vite will proxy /api requests to FastAPI
echo   Hot Module Replacement (HMR) is enabled
echo.
echo Press Ctrl+C to stop both servers
echo ========================================
echo.

REM Set development mode
set DEV_MODE=true

REM Start Vite dev server in a new window (cmd /k keeps window open on error)
start "Vite Dev Server" cmd /k "cd frontend && npm run dev"

REM Wait a moment for Vite to start
timeout /t 2 /nobreak >nul

REM Start FastAPI server (this window)
python src\api_server.py
