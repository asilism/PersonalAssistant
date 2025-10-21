# Personal Assistant Orchestration Service

LangGraph-based orchestration service with direct MCP integration for testing orchestration accuracy.

## Architecture

This implementation focuses on the **Orchestration** layer from the architecture document, with:

- **RAG Service**: Removed (focus on orchestration)
- **Task Service**: Replaced with direct MCP execution for accuracy testing
- **Orchestration**: Full implementation using LangGraph

## Components

### Core Components

1. **ConfigLoader** (`src/orchestration/config.py`)
   - Loads orchestration settings
   - Manages available MCP tools

2. **TaskTracker** (`src/orchestration/tracker.py`)
   - Tracks task execution state and history
   - Manages plan lifecycle

3. **Planner** (`src/orchestration/planner.py`)
   - Uses LLM to create execution plans
   - Decides next actions based on results

4. **TaskDispatcher** (`src/orchestration/dispatcher.py`)
   - Executes plan steps
   - Coordinates with MCP Executor

5. **MCPExecutor** (`src/orchestration/mcp_executor.py`)
   - Directly executes MCP tools (mock implementation)
   - In production, integrates with real MCP servers

6. **ResultListener** (`src/orchestration/listener.py`)
   - Processes step results
   - Extensible for webhooks, message queues, etc.

7. **Orchestrator** (`src/orchestration/orchestrator.py`)
   - Main LangGraph state machine
   - Coordinates all components

## State Machine Flow

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

## Installation

### Using pip

```bash
pip install -r requirements.txt
```

### Using Poetry

```bash
poetry install
```

## Configuration

Create a `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and set your API key:

```
ANTHROPIC_API_KEY=your_api_key_here
LLM_MODEL=claude-3-5-sonnet-20241022
MAX_RETRIES=3
TIMEOUT=30000
```

## Usage

### Running the Example

```bash
# Using Python
export ANTHROPIC_API_KEY=your_api_key
python src/main.py

# Using Poetry
poetry run python src/main.py
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
        request_text="Search the web for AI news and summarize"
    )

    print(f"Success: {result['success']}")
    print(f"Message: {result['message']}")

asyncio.run(main())
```

## Project Structure

```
PersonalAssistant/
├── src/
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── types.py           # Type definitions
│   │   ├── config.py          # ConfigLoader
│   │   ├── tracker.py         # TaskTracker
│   │   ├── planner.py         # Planner (LLM-based)
│   │   ├── dispatcher.py      # TaskDispatcher
│   │   ├── mcp_executor.py    # MCP Executor
│   │   ├── listener.py        # ResultListener
│   │   └── orchestrator.py    # Main Orchestrator
│   └── main.py                # Entry point
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

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

## Key Features

### 1. LangGraph State Machine

Uses LangGraph for robust state management and flow control.

### 2. Direct MCP Execution

Executes MCP tools directly instead of using a message queue, enabling:
- Faster feedback for accuracy testing
- Simplified debugging
- Direct observation of tool execution

### 3. LLM-based Planning

Uses Claude to:
- Analyze user requests
- Create execution plans
- Decide next actions based on results
- Handle errors gracefully

### 4. Extensible Architecture

Easy to extend with:
- Additional MCP tools
- Custom state transitions
- Result processing hooks
- Integration with external services

## Accuracy Testing

This implementation is designed for testing orchestration accuracy:

1. **Plan Quality**: How well does the LLM break down tasks?
2. **Tool Selection**: Does it choose the right tools?
3. **Execution Flow**: Are dependencies respected?
4. **Error Handling**: How does it recover from failures?
5. **Decision Making**: Are next-step decisions appropriate?

## Future Enhancements

- [ ] Real MCP server integration
- [ ] Parallel step execution (respecting dependencies)
- [ ] Human-in-the-loop UI
- [ ] Plan visualization
- [ ] Metrics and monitoring
- [ ] RAG integration (optional)
- [ ] Message queue for async execution
- [ ] Database persistence

## License

MIT
