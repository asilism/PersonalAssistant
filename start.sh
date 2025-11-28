#!/bin/bash

# Start the Personal Assistant Orchestration Service

echo "========================================"
echo "Personal Assistant Orchestration Service"
echo "========================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    echo "Please copy .env.example to .env and configure your API keys:"
    echo "  cp .env.example .env"
    echo ""
    exit 1
fi

# Check if API key is set
source .env
if [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$OPENAI_API_KEY" ] && [ -z "$OPENROUTER_API_KEY" ]; then
    echo "Error: No API key configured"
    echo "Please set at least one of the following in your .env file:"
    echo "  - ANTHROPIC_API_KEY"
    echo "  - OPENAI_API_KEY"
    echo "  - OPENROUTER_API_KEY"
    echo ""
    exit 1
fi

echo "Configuration loaded"
echo "Installing Python dependencies..."
pip install -r requirements.txt > /dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "Error: Failed to install Python dependencies"
    exit 1
fi

echo "Python dependencies installed"

# Check if production mode is requested
if [ "$1" = "--prod" ]; then
    export DEV_MODE=false
    echo ""
    echo "Building frontend for production..."

    # Check if Node.js is installed
    if ! command -v node &> /dev/null; then
        echo "Error: Node.js is not installed"
        echo "Please install Node.js to build the frontend"
        exit 1
    fi

    # Install frontend dependencies and build
    cd frontend
    if [ ! -d "node_modules" ]; then
        npm install > /dev/null 2>&1
        if [ $? -ne 0 ]; then
            echo "Error: Failed to install frontend dependencies"
            exit 1
        fi
    fi

    npm run build
    if [ $? -ne 0 ]; then
        echo "Error: Failed to build frontend"
        exit 1
    fi
    cd ..

    echo "Frontend built successfully"
    echo ""
    echo "Starting in PRODUCTION mode..."
    echo ""
    echo "Available at:"
    echo "  - Web UI:       http://localhost:8000"
    echo "  - API Docs:     http://localhost:8000/docs"
    echo "  - Health Check: http://localhost:8000/api/health"
else
    export DEV_MODE=true
    echo ""
    echo "Starting in DEVELOPMENT mode..."
    echo ""
    echo "For frontend development with HMR, use './start-dev.sh' instead"
    echo "This will start both Vite and FastAPI servers together"
    echo ""
    echo "Available at:"
    echo "  - API Backend:  http://localhost:8000"
    echo "  - API Docs:     http://localhost:8000/docs"
fi

echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server
python src/api_server.py
