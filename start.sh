#!/bin/bash

# Start Personal Assistant in Development Mode
# This script runs both Vite (frontend) and FastAPI (backend) simultaneously

set -e

echo "========================================"
echo "Personal Assistant - Development Mode"
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

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is not installed"
    echo "Please install Node.js to use Vite for frontend development"
    exit 1
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Error: Failed to install Python dependencies"
    exit 1
fi
echo "Python dependencies installed"

# Install frontend dependencies
echo "Installing frontend dependencies..."
cd frontend
if [ ! -d "node_modules" ]; then
    npm install > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install frontend dependencies"
        exit 1
    fi
fi
echo "Frontend dependencies installed"
cd ..

echo ""
echo "========================================"
echo "Starting servers..."
echo "========================================"
echo ""
echo "  Frontend (Vite):  http://localhost:5173  <-- Open this!"
echo "  Backend (FastAPI): http://localhost:8000"
echo "  API Docs:          http://localhost:8000/docs"
echo ""
echo "  Vite will proxy /api requests to FastAPI"
echo "  Hot Module Replacement (HMR) is enabled"
echo ""
echo "Press Ctrl+C to stop both servers"
echo "========================================"
echo ""

# Set development mode
export DEV_MODE=true

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "Shutting down servers..."
    kill $VITE_PID 2>/dev/null
    kill $API_PID 2>/dev/null
    wait $VITE_PID 2>/dev/null
    wait $API_PID 2>/dev/null
    echo "Servers stopped"
    exit 0
}

# Set trap to cleanup on Ctrl+C
trap cleanup SIGINT SIGTERM

# Start Vite dev server in background
cd frontend
npm run dev &
VITE_PID=$!
cd ..

# Wait a moment for Vite to start
sleep 2

# Start FastAPI server in background
python src/api_server.py &
API_PID=$!

# Wait for both processes
wait $VITE_PID $API_PID
