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

echo Installing Python dependencies...
pip install -r requirements.txt >nul 2>&1

if errorlevel 1 (
    echo Error: Failed to install Python dependencies
    exit /b 1
)

echo Python dependencies installed

REM Check if production mode is requested
if "%1"=="--prod" (
    set DEV_MODE=false
    echo.
    echo Building frontend for production...

    REM Check if Node.js is installed
    where node >nul 2>&1
    if errorlevel 1 (
        echo Error: Node.js is not installed
        echo Please install Node.js to build the frontend
        exit /b 1
    )

    REM Install frontend dependencies and build
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
    echo Starting in PRODUCTION mode...
    echo.
    echo Available at:
    echo   - Web UI:       http://localhost:8000
    echo   - API Docs:     http://localhost:8000/docs
    echo   - Health Check: http://localhost:8000/api/health
) else (
    set DEV_MODE=true
    echo.
    echo Starting in DEVELOPMENT mode...
    echo.
    echo For frontend development with HMR, use 'start-dev.bat' instead
    echo This will start both Vite and FastAPI servers together
    echo.
    echo Available at:
    echo   - API Backend:  http://localhost:8000
    echo   - API Docs:     http://localhost:8000/docs
)

echo.
echo Press Ctrl+C to stop the server
echo.

REM Start the server
python src\api_server.py
