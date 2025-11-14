#!/bin/bash

# Start the Personal Assistant Orchestration Service

echo "========================================"
echo "Personal Assistant Orchestration Service"
echo "========================================"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "Please copy .env.example to .env and configure your API keys:"
    echo "  cp .env.example .env"
    echo ""
    exit 1
fi

# Check if API key is set
source .env
if [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$OPENAI_API_KEY" ] && [ -z "$OPENROUTER_API_KEY" ]; then
    echo "❌ Error: No API key configured"
    echo "Please set at least one of the following in your .env file:"
    echo "  - ANTHROPIC_API_KEY"
    echo "  - OPENAI_API_KEY"
    echo "  - OPENROUTER_API_KEY"
    echo ""
    exit 1
fi

echo "✅ Configuration loaded"
echo "📦 Installing dependencies..."
pip install -r requirements.txt > /dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to install dependencies"
    exit 1
fi

echo "✅ Dependencies installed"
echo ""

# Check if production mode is requested
if [ "$1" = "--prod" ]; then
    export DEV_MODE=false
    echo "🚀 Starting in PRODUCTION mode..."
else
    export DEV_MODE=true
    echo "🚀 Starting in DEVELOPMENT mode (hot reload enabled)..."
fi

echo ""
echo "Available at:"
echo "  - Web UI:       http://localhost:8000"
echo "  - API Docs:     http://localhost:8000/docs"
echo "  - Health Check: http://localhost:8000/api/health"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server
python src/api_server.py
