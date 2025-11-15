"""
FastAPI server for the Orchestration Service
Provides REST API and serves web UI
"""

import asyncio
import json
import uuid
import os
import logging
import traceback
from datetime import datetime
from typing import Optional
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from pydantic import BaseModel
import uvicorn

from orchestration.orchestrator import Orchestrator
from orchestration.settings_manager import SettingsManager
from orchestration.event_emitter import get_event_emitter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Request/Response models
class OrchestrationRequest(BaseModel):
    request_text: str
    user_id: Optional[str] = "test_user"
    tenant: Optional[str] = "test_tenant"
    session_id: Optional[str] = None


class OrchestrationResponse(BaseModel):
    success: bool
    message: str
    results: Optional[dict] = None
    execution_time: float
    plan_id: Optional[str] = None
    trace_id: str


class SettingsRequest(BaseModel):
    provider: str
    api_key: str
    model: str
    base_url: Optional[str] = None
    max_retries: Optional[int] = 3
    timeout: Optional[int] = 30000
    user_id: Optional[str] = "test_user"
    tenant: Optional[str] = "test_tenant"


class MCPServerRequest(BaseModel):
    server_name: str
    enabled: bool = True
    transport: str = "http"  # "stdio" or "http"
    url: Optional[str] = None  # URL for HTTP transport
    command: Optional[str] = None  # Command for STDIO transport
    args: Optional[list] = None  # Args for STDIO transport
    env_vars: Optional[dict] = None
    user_id: Optional[str] = "test_user"
    tenant: Optional[str] = "test_tenant"


class TestConnectionRequest(BaseModel):
    provider: str
    api_key: str
    model: str
    base_url: Optional[str] = None


# Create FastAPI app
app = FastAPI(
    title="Personal Assistant Orchestration Service",
    description="LangGraph-based orchestration with MCP integration",
    version="1.0.0"
)

# Mount static files
frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_path / "static")), name="static")

# Store orchestrator instances per user
orchestrators = {}

# Settings manager
settings_manager = SettingsManager()


def get_orchestrator(user_id: str, tenant: str) -> Orchestrator:
    """Get or create an orchestrator for a user"""
    key = f"{tenant}:{user_id}"
    if key not in orchestrators:
        orchestrators[key] = Orchestrator(user_id=user_id, tenant=tenant)
    return orchestrators[key]


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the web UI"""
    index_file = frontend_path / "index.html"
    with open(index_file, 'r', encoding='utf-8') as f:
        return f.read()


@app.post("/api/orchestrate", response_model=OrchestrationResponse)
async def orchestrate(request: OrchestrationRequest):
    """Execute an orchestration request"""
    try:
        orchestrator = get_orchestrator(request.user_id, request.tenant)
        session_id = request.session_id or str(uuid.uuid4())
        trace_id = str(uuid.uuid4())

        result = await orchestrator.run(
            session_id=session_id,
            request_text=request.request_text,
            trace_id=trace_id
        )

        return OrchestrationResponse(
            success=result["success"],
            message=result["message"],
            results=result.get("results"),
            execution_time=result["execution_time"],
            plan_id=result.get("plan_id"),
            trace_id=trace_id
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/orchestrate/stream")
async def orchestrate_stream(request: OrchestrationRequest):
    """Execute an orchestration request with streaming logs via SSE"""
    try:
        orchestrator = get_orchestrator(request.user_id, request.tenant)
        session_id = request.session_id or str(uuid.uuid4())
        trace_id = str(uuid.uuid4())

        event_emitter = get_event_emitter()

        async def event_generator():
            """Generate SSE events"""
            try:
                # Start streaming events for this trace_id
                event_stream = event_emitter.stream_events(trace_id)

                # Run orchestrator in background task
                async def run_orchestrator():
                    try:
                        await orchestrator.run(
                            session_id=session_id,
                            request_text=request.request_text,
                            trace_id=trace_id
                        )
                    except Exception as e:
                        logger.error(f"Error in orchestrator.run: {e}")
                        await event_emitter.emit_execution_error(
                            trace_id=trace_id,
                            error=str(e),
                            error_type=type(e).__name__
                        )

                # Start the orchestrator task
                orchestrator_task = asyncio.create_task(run_orchestrator())

                # Stream events
                async for event_data in event_stream:
                    yield event_data

                # Wait for orchestrator to complete
                await orchestrator_task

            except Exception as e:
                logger.error(f"Error in event_generator: {e}")
                error_data = {
                    "event_type": "stream_error",
                    "error": str(e)
                }
                yield f"data: {json.dumps(error_data)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )

    except Exception as e:
        logger.error(f"Error in orchestrate_stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/settings")
async def get_settings(user_id: str = "test_user", tenant: str = "test_tenant"):
    """Get current settings for user"""
    try:
        logger.info(f"Getting settings for user_id={user_id}, tenant={tenant}")
        settings_data = settings_manager.get_all_settings(user_id, tenant)
        logger.info(f"Successfully retrieved settings for user_id={user_id}")
        return settings_data
    except Exception as e:
        logger.error(f"Error getting settings for user_id={user_id}, tenant={tenant}: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings")
async def save_settings(request: SettingsRequest):
    """Save LLM settings"""
    try:
        logger.info(f"Saving settings for user_id={request.user_id}, tenant={request.tenant}, provider={request.provider}, model={request.model}")

        success = settings_manager.save_llm_settings(
            user_id=request.user_id,
            tenant=request.tenant,
            provider=request.provider,
            api_key=request.api_key,
            model=request.model,
            base_url=request.base_url,
            max_retries=request.max_retries,
            timeout=request.timeout
        )

        if success:
            # Clear orchestrator cache to force reload with new settings
            key = f"{request.tenant}:{request.user_id}"
            if key in orchestrators:
                del orchestrators[key]
                logger.info(f"Cleared orchestrator cache for {key}")

            logger.info(f"Settings saved successfully for user_id={request.user_id}")
            return {"success": True, "message": "Settings saved successfully"}
        else:
            logger.error(f"Failed to save settings for user_id={request.user_id}")
            raise HTTPException(status_code=500, detail="Failed to save settings")

    except Exception as e:
        logger.error(f"Error saving settings for user_id={request.user_id}, tenant={request.tenant}: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings/test")
async def test_connection(request: TestConnectionRequest):
    """Test LLM connection"""
    try:
        logger.info(f"Testing connection for provider={request.provider}, model={request.model}")
        result = settings_manager.test_connection(
            provider=request.provider,
            api_key=request.api_key,
            model=request.model,
            base_url=request.base_url
        )
        logger.info(f"Connection test result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error testing connection for provider={request.provider}: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tools")
async def list_tools():
    """List available MCP tools"""
    try:
        orchestrator = get_orchestrator("system", "system")

        if not orchestrator.settings:
            await orchestrator._initialize()

        tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema
            }
            for tool in orchestrator.settings.available_tools
        ]

        return {"tools": tools, "count": len(tools)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/mcp-servers")
async def get_mcp_servers(user_id: str = "test_user", tenant: str = "test_tenant"):
    """Get all MCP server settings"""
    try:
        servers = settings_manager.get_all_mcp_servers(user_id, tenant)
        return {
            "servers": [
                {
                    "server_name": s.server_name,
                    "enabled": s.enabled,
                    "transport": s.transport if hasattr(s, 'transport') else "stdio",
                    "url": s.url if hasattr(s, 'url') else None,
                    "command": s.command,
                    "args": s.args,
                    "env_vars": s.env_vars
                }
                for s in servers
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mcp-servers")
async def save_mcp_server(request: MCPServerRequest):
    """Save MCP server settings"""
    try:
        success = settings_manager.save_mcp_server_settings(
            user_id=request.user_id,
            tenant=request.tenant,
            server_name=request.server_name,
            enabled=request.enabled,
            transport=request.transport,
            url=request.url,
            command=request.command,
            args=request.args,
            env_vars=request.env_vars
        )

        if success:
            # Clear orchestrator cache to force reload with new settings
            key = f"{request.tenant}:{request.user_id}"
            if key in orchestrators:
                del orchestrators[key]

            return {"success": True, "message": "MCP server settings saved successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save MCP server settings")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/mcp-servers/{server_name}")
async def delete_mcp_server(server_name: str, user_id: str = "test_user", tenant: str = "test_tenant"):
    """Delete MCP server settings"""
    try:
        success = settings_manager.delete_mcp_server_settings(user_id, tenant, server_name)

        if success:
            # Clear orchestrator cache to force reload
            key = f"{tenant}:{user_id}"
            if key in orchestrators:
                del orchestrators[key]

            return {"success": True, "message": "MCP server settings deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="MCP server settings not found")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat-history")
async def get_chat_history(session_id: str, limit: Optional[int] = None):
    """Get chat history for a session"""
    try:
        logger.info(f"Getting chat history for session_id={session_id}, limit={limit}")
        messages = settings_manager.get_chat_history(session_id=session_id, limit=limit)

        return {
            "success": True,
            "session_id": session_id,
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at
                }
                for msg in messages
            ],
            "count": len(messages)
        }

    except Exception as e:
        logger.error(f"Error getting chat history for session_id={session_id}: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/chat-history")
async def delete_chat_history(session_id: str):
    """Delete chat history for a session"""
    try:
        logger.info(f"Deleting chat history for session_id={session_id}")
        success = settings_manager.delete_chat_history(session_id=session_id)

        if success:
            logger.info(f"Chat history deleted successfully for session_id={session_id}")
            return {"success": True, "message": "Chat history deleted successfully"}
        else:
            logger.warning(f"No chat history found for session_id={session_id}")
            return {"success": True, "message": "No chat history found"}

    except Exception as e:
        logger.error(f"Error deleting chat history for session_id={session_id}: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


def main():
    """Run the API server"""
    print("=" * 80)
    print("Personal Assistant Orchestration Service - API Server")
    print("=" * 80)
    print("\nStarting server...")
    print("- Web UI: http://localhost:8000")
    print("- API Docs: http://localhost:8000/docs")
    print("- Health Check: http://localhost:8000/api/health")

    # Check if running in development mode
    dev_mode = os.getenv("DEV_MODE", "true").lower() == "true"

    if dev_mode:
        print("\n⚡ Development mode: Hot reload enabled")
        print("   - Backend changes will auto-reload")
        print("   - Frontend changes will auto-reload")

    print("\n" + "=" * 80 + "\n")

    if dev_mode:
        # Development mode with hot reload
        uvicorn.run(
            "api_server:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            reload_dirs=["src", "frontend"],
            log_level="info"
        )
    else:
        # Production mode without reload
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
