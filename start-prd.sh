#!/bin/bash

# Start Personal Assistant in Production Mode

echo "========================================"
echo "Personal Assistant - Production Mode"
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

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Error: Failed to install Python dependencies"
    exit 1
fi
echo "Python dependencies installed"

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is not installed"
    echo "Please install Node.js to build the frontend"
    exit 1
fi

# Build frontend
echo "Building frontend..."
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
echo "========================================"
echo "Starting server..."
echo "========================================"
echo ""
echo "Available at:"
echo "  - Web UI:       http://localhost:8000"
echo "  - API Docs:     http://localhost:8000/docs"
echo "  - Health Check: http://localhost:8000/api/health"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Set production mode and start
export DEV_MODE=false
python src/api_server.py
