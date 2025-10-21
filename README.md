# Personal Assistant Orchestration Service

LangGraph-based orchestration service with real MCP agent integration and multi-LLM support.

## Features

✨ **5 MCP Agent Servers** - Mail, Calendar, Jira, Calculator, and RPA agents
🤖 **Multi-LLM Support** - Works with Anthropic Claude, OpenAI GPT, and OpenRouter
🎯 **LangGraph Orchestration** - Robust state machine for task execution
🌐 **Web UI** - Beautiful interface for testing and interaction
📡 **REST API** - FastAPI-based API for programmatic access

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd PersonalAssistant

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and configure your LLM provider:

```env
# Choose your LLM provider: anthropic, openai, or openrouter
LLM_PROVIDER=anthropic

# Set your API key
ANTHROPIC_API_KEY=your_api_key_here
# OPENAI_API_KEY=your_openai_key_here
# OPENROUTER_API_KEY=your_openrouter_key_here

# Choose your model
LLM_MODEL=claude-3-5-sonnet-20241022
# For OpenAI: gpt-4-turbo-preview, gpt-4, gpt-3.5-turbo
# For OpenRouter: anthropic/claude-3.5-sonnet, openai/gpt-4-turbo
```

### 3. Run the Service

#### Linux/Mac:
```bash
./start.sh
```

#### Windows:
```cmd
start.bat
```

#### Manual:
```bash
python src/api_server.py
```

### 4. Access the Web UI

Open your browser and navigate to:
- **Web UI**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

## MCP Agent Servers

The service includes 5 fully-functional MCP agent servers:

### 📧 Mail Agent
CRUD operations for email management:
- `send_email` - Send an email
- `read_emails` - Read emails from inbox
- `get_email` - Get specific email by ID
- `delete_email` - Delete an email
- `search_emails` - Search emails by query

### 📅 Calendar Agent
Event management with full CRUD:
- `create_event` - Create a new calendar event
- `read_event` - Read event details
- `update_event` - Update existing event
- `delete_event` - Delete an event
- `list_events` - List events with filters

### 🎫 Jira Agent
Issue tracking and management:
- `create_issue` - Create a new Jira issue
- `read_issue` - Read issue details
- `update_issue` - Update issue status/fields
- `delete_issue` - Delete an issue
- `search_issues` - Search issues by query

### 🔢 Calculator Agent
Mathematical operations:
- `add` - Add numbers
- `subtract` - Subtract numbers
- `multiply` - Multiply numbers
- `divide` - Divide numbers
- `power` - Power operation

### 🤖 RPA Agent
Automation tasks (3 specialized tools):
- `search_latest_news` - Search for latest news articles
- `write_report` - Generate formatted reports
- `collect_attendance` - Collect and aggregate attendance

## Architecture

### Core Components

1. **Orchestrator** (`src/orchestration/orchestrator.py`)
   - LangGraph-based state machine
   - Coordinates all components
   - Manages execution flow

2. **Planner** (`src/orchestration/planner.py`)
   - Multi-LLM support (Claude, GPT, OpenRouter)
   - Creates execution plans
   - Makes decisions based on results

3. **MCPExecutor** (`src/orchestration/mcp_executor.py`)
   - Connects to real MCP servers via STDIO
   - Dynamically discovers available tools
   - Executes MCP tools

4. **TaskDispatcher** (`src/orchestration/dispatcher.py`)
   - Executes plan steps
   - Tracks execution state

5. **ConfigLoader** (`src/orchestration/config.py`)
   - Loads settings and configuration
   - Manages LLM provider selection

6. **API Server** (`src/api_server.py`)
   - FastAPI-based REST API
   - Web UI for testing
   - Tool discovery endpoint

### State Machine Flow

```
INIT → PLAN_OR_DECIDE → DISPATCH → PLAN_OR_DECIDE → ... → FINAL
                ↓                      ↓
              ERROR                  ERROR
```

### States
- **INIT**: Initial state
- **PLAN_OR_DECIDE**: Planning or decision making
- **DISPATCH**: Executing plan steps
- **HUMAN_IN_THE_LOOP**: Requires human intervention
- **FINAL**: Task completed
- **ERROR**: Error occurred

## Project Structure

```
PersonalAssistant/
├── src/
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── types.py           # Type definitions
│   │   ├── config.py          # ConfigLoader
│   │   ├── tracker.py         # TaskTracker
│   │   ├── planner.py         # Planner (Multi-LLM)
│   │   ├── llm_client.py      # LLM client abstraction
│   │   ├── dispatcher.py      # TaskDispatcher
│   │   ├── mcp_executor.py    # MCP Executor (STDIO)
│   │   ├── listener.py        # ResultListener
│   │   └── orchestrator.py    # Main Orchestrator
│   ├── api_server.py          # FastAPI server + Web UI
│   └── main.py                # CLI entry point
├── mcp_servers/
│   ├── mail_agent/
│   │   └── server.py          # Mail MCP server
│   ├── calendar_agent/
│   │   └── server.py          # Calendar MCP server
│   ├── jira_agent/
│   │   └── server.py          # Jira MCP server
│   ├── calculator_agent/
│   │   └── server.py          # Calculator MCP server
│   └── rpa_agent/
│       └── server.py          # RPA MCP server
├── start.sh                   # Linux/Mac startup script
├── start.bat                  # Windows startup script
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Usage Examples

### Web UI

The easiest way to test the service is through the Web UI at http://localhost:8000.

Example requests:
- "Send an email to john@example.com about the meeting tomorrow"
- "Create a calendar event for team meeting on Friday at 2 PM"
- "Search for issues assigned to me in Jira"
- "Calculate 25 * 8 + 150"
- "Search for latest AI news and write a brief report"

### REST API

```bash
# Execute a request
curl -X POST http://localhost:8000/api/orchestrate \
  -H "Content-Type: application/json" \
  -d '{
    "request_text": "Send an email to john@example.com with subject Hello",
    "user_id": "test_user",
    "tenant": "test_tenant"
  }'

# List available tools
curl http://localhost:8000/api/tools

# Health check
curl http://localhost:8000/api/health
```

### Programmatic Usage

```python
import asyncio
from orchestration.orchestrator import Orchestrator

async def main():
    # Initialize orchestrator
    orchestrator = Orchestrator(
        user_id="user_123",
        tenant="my_tenant"
    )

    # Run a request
    result = await orchestrator.run(
        session_id="session_001",
        request_text="Calculate 100 + 50 and send the result via email"
    )

    print(f"Success: {result['success']}")
    print(f"Message: {result['message']}")
    if result.get('results'):
        print(f"Results: {result['results']}")

asyncio.run(main())
```

### CLI Usage

```bash
# Run example requests
python src/main.py
```

## LLM Provider Configuration

### Anthropic Claude (Default)

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_key_here
LLM_MODEL=claude-3-5-sonnet-20241022
```

Available models:
- `claude-3-5-sonnet-20241022` (recommended)
- `claude-3-opus-20240229`
- `claude-3-sonnet-20240229`

### OpenAI GPT

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key_here
LLM_MODEL=gpt-4-turbo-preview
```

Available models:
- `gpt-4-turbo-preview`
- `gpt-4`
- `gpt-3.5-turbo`

### OpenRouter

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here
LLM_MODEL=anthropic/claude-3.5-sonnet
```

Available models:
- `anthropic/claude-3.5-sonnet`
- `openai/gpt-4-turbo`
- `google/gemini-pro`
- And many more...

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black src/
ruff check src/
```

### Type Checking

```bash
mypy src/
```

### Adding a New MCP Server

1. Create a new directory in `mcp_servers/`
2. Implement the MCP server using the `mcp` package
3. Add tools using `@app.list_tools()` and `@app.call_tool()`
4. Register the server in `src/orchestration/mcp_executor.py`

Example:

```python
# mcp_servers/my_agent/server.py
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

app = Server("my-agent")

@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="my_tool",
            description="My custom tool",
            inputSchema={...}
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Any):
    # Implementation
    pass
```

## Troubleshooting

### MCP Server Connection Issues

If you see connection errors:
1. Ensure Python 3.9+ is installed
2. Check that all dependencies are installed: `pip install -r requirements.txt`
3. Verify the MCP server paths in `src/orchestration/mcp_executor.py`

### LLM API Errors

If you get API errors:
1. Check your API key is correctly set in `.env`
2. Verify you have sufficient API credits
3. Check the model name is correct for your provider

### Port Already in Use

If port 8000 is already in use:
```bash
# Linux/Mac
lsof -ti:8000 | xargs kill -9

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

## Key Features

### 1. Real MCP Integration

Uses actual MCP STDIO protocol to communicate with agent servers, providing:
- True agent separation
- CRUD-focused operations
- Extensible architecture

### 2. Multi-LLM Support

Works with multiple LLM providers:
- Easy provider switching via environment variables
- Unified interface across providers
- Support for latest models

### 3. LangGraph State Machine

Robust orchestration with:
- Clear state transitions
- Error handling
- Decision making

### 4. Beautiful Web UI

Modern, responsive interface with:
- Real-time feedback
- Example requests
- Result visualization

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT

## Acknowledgments

- Built with [LangGraph](https://github.com/langchain-ai/langgraph)
- Uses [MCP (Model Context Protocol)](https://github.com/anthropics/mcp)
- Powered by [FastAPI](https://fastapi.tiangolo.com/)
