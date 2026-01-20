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
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from pydantic import BaseModel
import uvicorn

from orchestration.orchestrator import Orchestrator
from orchestration.settings_manager import SettingsManager

from orchestration.event_emitter import get_event_emitter

from orchestration.mcp_executor import MCPExecutor
from orchestration.types import ToolDefinition

# Manus system imports
from manus.coordinator import ManusCoordinator


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
    config_name: str  # Configuration name (e.g., "Claude Prod", "GPT Dev")
    provider: str
    api_key: str
    model: str
    base_url: Optional[str] = None
    max_retries: Optional[int] = 3
    timeout: Optional[int] = 30000
    is_active: Optional[bool] = False  # Whether to set as active configuration
    user_id: Optional[str] = "test_user"
    tenant: Optional[str] = "test_tenant"


class MCPServerRequest(BaseModel):
    server_name: str
    enabled: bool = True
    transport: str = "http"  # "stdio", "http", "streamable-http", or "sse"
    url: Optional[str] = None  # URL for HTTP/SSE transport
    command: Optional[str] = None  # Command for STDIO transport
    args: Optional[list] = None  # Args for STDIO transport
    env_vars: Optional[dict] = None
    headers: Optional[dict] = None  # Custom headers for HTTP/SSE transport (e.g., API keys)
    user_id: Optional[str] = "test_user"
    tenant: Optional[str] = "test_tenant"


class TestConnectionRequest(BaseModel):
    provider: str
    api_key: str
    model: str
    base_url: Optional[str] = None


# Global MCP tools cache and tool-server mapping
global_mcp_tools = []
global_tool_server_map = {}


async def sync_mcp_servers(user_id: str = "test_user", tenant: str = "test_tenant"):
    """Sync MCP servers and update global tools cache"""
    global global_mcp_tools, global_tool_server_map

    logger.info(f"Syncing MCP servers for {user_id}@{tenant}...")

    try:
        # Create MCP executor and discover tools
        mcp_executor = MCPExecutor(user_id=user_id, tenant=tenant)
        await mcp_executor.initialize_servers()
        global_mcp_tools = await mcp_executor.discover_tools()
        global_tool_server_map = mcp_executor.get_tool_server_map()

        logger.info(f"✓ Synced {len(global_mcp_tools)} MCP tools from {len(global_tool_server_map)} unique tool mappings")

        # Clear orchestrator cache to force reload with new tools
        orchestrators.clear()
        logger.info("Cleared orchestrator cache")

        # Cleanup MCP executor after discovery
        await mcp_executor.cleanup()

        return {
            "success": True,
            "tools_count": len(global_mcp_tools),
            "servers_synced": len(set(global_tool_server_map.values())),
            "message": f"Successfully synced {len(global_mcp_tools)} tools"
        }

    except Exception as e:
        logger.error(f"✗ Failed to sync MCP servers: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to sync: {str(e)}"
        }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler to preload MCP tools on startup"""
    global global_mcp_tools, global_tool_server_map

    logger.info("=" * 80)
    logger.info("Starting Personal Assistant - Preloading MCP tools...")
    logger.info("=" * 80)

    try:
        # Create MCP executor and discover tools
        mcp_executor = MCPExecutor()
        await mcp_executor.initialize_servers()
        global_mcp_tools = await mcp_executor.discover_tools()
        global_tool_server_map = mcp_executor.get_tool_server_map()

        logger.info(f"✓ Successfully preloaded {len(global_mcp_tools)} MCP tools")
        logger.info("=" * 80)

        # Cleanup MCP executor after discovery
        await mcp_executor.cleanup()

    except Exception as e:
        logger.error(f"✗ Failed to preload MCP tools: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        logger.warning("Server will continue, but first request may be slow")

    yield

    # Cleanup on shutdown
    logger.info("Shutting down Personal Assistant...")

    # Cleanup orchestrator checkpointers
    for key, orchestrator in orchestrators.items():
        try:
            await orchestrator.cleanup()
            logger.info(f"Cleaned up orchestrator: {key}")
        except Exception as e:
            logger.error(f"Error cleaning up orchestrator {key}: {e}")
    orchestrators.clear()

    # Cleanup Manus coordinators
    for key, coordinator in manus_coordinators.items():
        try:
            await coordinator.cleanup()
            logger.info(f"Cleaned up Manus coordinator: {key}")
        except Exception as e:
            logger.error(f"Error cleaning up Manus coordinator {key}: {e}")
    manus_coordinators.clear()


# Create FastAPI app with lifespan
app = FastAPI(
    title="Personal Assistant Orchestration Service",
    description="LangGraph-based orchestration with MCP integration",
    version="1.0.0",
    lifespan=lifespan
)

# Frontend paths
frontend_path = Path(__file__).parent.parent / "frontend"
frontend_dist_path = frontend_path / "dist"

# Check if running in development mode (Vite handles frontend)
dev_mode = os.getenv("DEV_MODE", "true").lower() == "true"

# Mount static files only in production mode (when dist folder exists)
if not dev_mode and frontend_dist_path.exists():
    # Production: serve built assets from dist
    app.mount("/assets", StaticFiles(directory=str(frontend_dist_path / "assets")), name="assets")
else:
    # Development fallback: serve from static folder (for non-Vite access)
    static_path = frontend_path / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Store orchestrator instances per user
orchestrators = {}

# Store Manus coordinator instances per user
manus_coordinators = {}

# Settings manager
settings_manager = SettingsManager()


def get_orchestrator(user_id: str, tenant: str) -> Orchestrator:
    """Get or create an orchestrator for a user"""
    key = f"{tenant}:{user_id}"
    if key not in orchestrators:
        orchestrators[key] = Orchestrator(
            user_id=user_id,
            tenant=tenant,
            preloaded_mcp_tools=global_mcp_tools,
            preloaded_tool_server_map=global_tool_server_map
        )
    return orchestrators[key]


def get_manus_coordinator(user_id: str, tenant: str) -> ManusCoordinator:
    """Get or create a Manus coordinator for a user"""
    key = f"{tenant}:{user_id}"
    if key not in manus_coordinators:
        manus_coordinators[key] = ManusCoordinator(
            user_id=user_id,
            tenant=tenant
        )
    return manus_coordinators[key]


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the web UI"""
    # In production mode, serve from dist folder
    if not dev_mode and frontend_dist_path.exists():
        index_file = frontend_dist_path / "index.html"
    else:
        # Development mode or fallback: serve original index.html
        # Note: In dev mode, Vite serves at port 5173, this is just a fallback
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
        logger.info(f"Saving settings for user_id={request.user_id}, tenant={request.tenant}, config_name={request.config_name}, provider={request.provider}, model={request.model}")

        success = settings_manager.save_llm_settings(
            user_id=request.user_id,
            tenant=request.tenant,
            config_name=request.config_name,
            provider=request.provider,
            api_key=request.api_key,
            model=request.model,
            base_url=request.base_url,
            max_retries=request.max_retries,
            timeout=request.timeout,
            is_active=request.is_active
        )

        if success:
            # Clear orchestrator cache to force reload with new settings
            key = f"{request.tenant}:{request.user_id}"
            if key in orchestrators:
                del orchestrators[key]
                logger.info(f"Cleared orchestrator cache for {key}")

            logger.info(f"Settings saved successfully for user_id={request.user_id}, config_name={request.config_name}")
            return {"success": True, "message": f"Settings '{request.config_name}' saved successfully"}
        else:
            logger.error(f"Failed to save settings for user_id={request.user_id}, config_name={request.config_name}")
            raise HTTPException(status_code=500, detail="Failed to save settings")

    except Exception as e:
        logger.error(f"Error saving settings for user_id={request.user_id}, tenant={request.tenant}, config_name={request.config_name}: {str(e)}")
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


@app.post("/api/settings/{config_name}/activate")
async def activate_settings(config_name: str, user_id: str = "test_user", tenant: str = "test_tenant"):
    """Activate a specific LLM configuration"""
    try:
        logger.info(f"Activating settings config_name={config_name} for user_id={user_id}, tenant={tenant}")

        success = settings_manager.set_active_llm_settings(
            user_id=user_id,
            tenant=tenant,
            config_name=config_name
        )

        if success:
            # Clear orchestrator cache to force reload with new active settings
            key = f"{tenant}:{user_id}"
            if key in orchestrators:
                del orchestrators[key]
                logger.info(f"Cleared orchestrator cache for {key}")

            logger.info(f"Configuration '{config_name}' activated successfully")
            return {"success": True, "message": f"Configuration '{config_name}' activated successfully"}
        else:
            logger.error(f"Configuration '{config_name}' not found")
            raise HTTPException(status_code=404, detail=f"Configuration '{config_name}' not found")

    except Exception as e:
        logger.error(f"Error activating settings config_name={config_name}: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/settings/{config_name}")
async def delete_settings(config_name: str, user_id: str = "test_user", tenant: str = "test_tenant"):
    """Delete a specific LLM configuration"""
    try:
        logger.info(f"Deleting settings config_name={config_name} for user_id={user_id}, tenant={tenant}")

        success = settings_manager.delete_llm_settings(
            user_id=user_id,
            tenant=tenant,
            config_name=config_name
        )

        if success:
            # Clear orchestrator cache to force reload
            key = f"{tenant}:{user_id}"
            if key in orchestrators:
                del orchestrators[key]
                logger.info(f"Cleared orchestrator cache for {key}")

            logger.info(f"Configuration '{config_name}' deleted successfully")
            return {"success": True, "message": f"Configuration '{config_name}' deleted successfully"}
        else:
            logger.error(f"Configuration '{config_name}' not found")
            raise HTTPException(status_code=404, detail=f"Configuration '{config_name}' not found")

    except Exception as e:
        logger.error(f"Error deleting settings config_name={config_name}: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tools")
async def list_tools():
    """List available MCP tools"""
    try:
        # Use preloaded tools if available
        if global_mcp_tools:
            tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema
                }
                for tool in global_mcp_tools
            ]
            return {"tools": tools, "count": len(tools)}

        # Fallback to orchestrator-based discovery
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
                    "env_vars": s.env_vars,
                    "headers": s.headers if hasattr(s, 'headers') else None
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
            env_vars=request.env_vars,
            headers=request.headers
        )

        if success:
            # Auto-sync MCP servers to update global tools cache
            logger.info(f"Auto-syncing MCP servers after saving {request.server_name}...")
            sync_result = await sync_mcp_servers(user_id=request.user_id, tenant=request.tenant)

            if sync_result["success"]:
                logger.info(f"Auto-sync completed: {sync_result['tools_count']} tools discovered")
                return {
                    "success": True,
                    "message": f"MCP server '{request.server_name}' saved and synced successfully",
                    "tools_synced": sync_result["tools_count"]
                }
            else:
                logger.warning(f"Auto-sync failed: {sync_result.get('message')}")
                return {
                    "success": True,
                    "message": f"MCP server '{request.server_name}' saved, but sync failed. Please sync manually.",
                    "sync_error": sync_result.get("message")
                }
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


@app.post("/api/mcp-servers/{server_name}/toggle")
async def toggle_mcp_server(server_name: str, user_id: str = "test_user", tenant: str = "test_tenant"):
    """Toggle MCP server enabled/disabled status"""
    try:
        # Get current server settings
        server = settings_manager.get_mcp_server_settings(user_id, tenant, server_name)

        if not server:
            raise HTTPException(status_code=404, detail=f"MCP server '{server_name}' not found")

        # Toggle enabled status
        new_enabled = not server.enabled

        # Update server settings
        success = settings_manager.save_mcp_server_settings(
            user_id=user_id,
            tenant=tenant,
            server_name=server.server_name,
            enabled=new_enabled,
            transport=server.transport,
            url=server.url,
            command=server.command,
            args=server.args,
            env_vars=server.env_vars,
            headers=server.headers
        )

        if success:
            # Auto-sync MCP servers to update global tools cache
            status_text = "enabled" if new_enabled else "disabled"
            logger.info(f"MCP server '{server_name}' {status_text}, auto-syncing...")
            sync_result = await sync_mcp_servers(user_id=user_id, tenant=tenant)

            if sync_result["success"]:
                logger.info(f"Auto-sync completed: {sync_result['tools_count']} tools")
            else:
                logger.warning(f"Auto-sync failed: {sync_result.get('message')}")

            return {
                "success": True,
                "server_name": server_name,
                "enabled": new_enabled,
                "message": f"MCP server '{server_name}' is now {status_text}",
                "tools_synced": sync_result.get("tools_count", 0) if sync_result["success"] else None
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update server status")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling MCP server '{server_name}': {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mcp-servers/sync")
async def sync_mcp_servers_api(user_id: str = "test_user", tenant: str = "test_tenant"):
    """Sync MCP servers - re-discover tools from all enabled servers"""
    try:
        result = await sync_mcp_servers(user_id=user_id, tenant=tenant)

        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "Sync failed"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing MCP servers: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/mcp-servers/status")
async def get_mcp_servers_status(user_id: str = "test_user", tenant: str = "test_tenant"):
    """Get detailed status of all MCP servers including tool counts"""
    try:
        servers = settings_manager.get_all_mcp_servers(user_id, tenant)

        # Build status info with tool counts from global mapping
        server_status = []
        for s in servers:
            tool_count = len([t for t, srv in global_tool_server_map.items() if srv == s.server_name])
            server_status.append({
                "server_name": s.server_name,
                "enabled": s.enabled,
                "transport": s.transport if hasattr(s, 'transport') else "stdio",
                "url": s.url if hasattr(s, 'url') else None,
                "command": s.command,
                "tool_count": tool_count,
                "status": "connected" if tool_count > 0 else ("disabled" if not s.enabled else "disconnected")
            })

        return {
            "servers": server_status,
            "total_tools": len(global_mcp_tools),
            "total_servers": len(servers),
            "enabled_servers": len([s for s in servers if s.enabled])
        }

    except Exception as e:
        logger.error(f"Error getting MCP servers status: {str(e)}")
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
    """Delete chat history for a session and return a new session ID"""
    try:
        logger.info(f"Deleting chat history for session_id={session_id}")
        success = settings_manager.delete_chat_history(session_id=session_id)

        # Generate new session ID for fresh start
        new_session_id = str(uuid.uuid4())
        logger.info(f"Generated new session_id={new_session_id} for fresh conversation")

        if success:
            logger.info(f"Chat history deleted successfully for session_id={session_id}")
            return {
                "success": True,
                "message": "Chat history deleted successfully",
                "new_session_id": new_session_id
            }
        else:
            logger.warning(f"No chat history found for session_id={session_id}")
            return {
                "success": True,
                "message": "No chat history found",
                "new_session_id": new_session_id
            }

    except Exception as e:
        logger.error(f"Error deleting chat history for session_id={session_id}: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Session Management Endpoints ====================

@app.get("/api/sessions")
async def get_sessions(
    user_id: str = "test_user",
    tenant: str = "test_tenant",
    limit: Optional[int] = None
):
    """Get all sessions for a user"""
    try:
        logger.info(f"Getting sessions for user_id={user_id}, tenant={tenant}, limit={limit}")
        sessions = settings_manager.get_all_sessions(user_id=user_id, tenant=tenant, limit=limit)

        return {
            "success": True,
            "sessions": [
                {
                    "session_id": session.session_id,
                    "title": session.title,
                    "created_at": session.created_at,
                    "updated_at": session.updated_at
                }
                for session in sessions
            ],
            "count": len(sessions)
        }

    except Exception as e:
        logger.error(f"Error getting sessions: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


class CreateSessionRequest(BaseModel):
    session_id: Optional[str] = None
    user_id: str = "test_user"
    tenant: str = "test_tenant"
    title: Optional[str] = None


@app.post("/api/sessions")
async def create_session(request: CreateSessionRequest):
    """Create a new session"""
    try:
        session_id = request.session_id or str(uuid.uuid4())
        logger.info(f"Creating session with session_id={session_id}, title={request.title}")

        success = settings_manager.create_session(
            session_id=session_id,
            user_id=request.user_id,
            tenant=request.tenant,
            title=request.title
        )

        if success:
            return {
                "success": True,
                "session_id": session_id,
                "message": "Session created successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create session")

    except Exception as e:
        logger.error(f"Error creating session: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


class UpdateSessionTitleRequest(BaseModel):
    title: str


@app.put("/api/sessions/{session_id}/title")
async def update_session_title(session_id: str, request: UpdateSessionTitleRequest):
    """Update session title"""
    try:
        logger.info(f"Updating title for session_id={session_id} to '{request.title}'")

        success = settings_manager.update_session_title(
            session_id=session_id,
            title=request.title
        )

        if success:
            return {
                "success": True,
                "message": "Session title updated successfully"
            }
        else:
            raise HTTPException(status_code=404, detail="Session not found")

    except Exception as e:
        logger.error(f"Error updating session title: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and all related data"""
    try:
        logger.info(f"Deleting session_id={session_id}")

        success = settings_manager.delete_session(session_id=session_id)

        if success:
            return {
                "success": True,
                "message": "Session deleted successfully"
            }
        else:
            raise HTTPException(status_code=404, detail="Session not found")

    except Exception as e:
        logger.error(f"Error deleting session: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Manus Endpoints ====================

class ManusRequest(BaseModel):
    request_text: str
    user_id: Optional[str] = "test_user"
    tenant: Optional[str] = "test_tenant"
    session_id: Optional[str] = None
    max_wait_time: Optional[int] = 60


@app.post("/api/manus/stream")
async def manus_stream(request: ManusRequest):
    """
    Execute a request using Manus-style multi-agent system with streaming logs via SSE
    """
    try:
        coordinator = get_manus_coordinator(request.user_id, request.tenant)
        session_id = request.session_id or str(uuid.uuid4())
        trace_id = session_id  # Use session_id as trace_id for Manus

        # Check if this is a new session and create/update session metadata
        existing_session = settings_manager.get_session(session_id)
        if not existing_session:
            # Extract title from first message (first 60 chars, remove newlines)
            title = request.request_text.replace('\n', ' ')[:60]
            if len(request.request_text) > 60:
                title += "..."

            # Create new session with auto-generated title
            settings_manager.create_session(
                session_id=session_id,
                user_id=request.user_id,
                tenant=request.tenant,
                title=title
            )
            logger.info(f"Created new session {session_id} with title: {title}")
        else:
            # Update session timestamp to move it to top of list
            settings_manager.update_session_timestamp(session_id)

        event_emitter = get_event_emitter()

        async def event_generator():
            """Generate SSE events"""
            try:
                # Start streaming events for this trace_id
                event_stream = event_emitter.stream_events(trace_id)

                # Run coordinator in background task
                async def run_coordinator():
                    try:
                        await coordinator.run(
                            request=request.request_text,
                            session_id=session_id,
                            max_wait_time=request.max_wait_time
                        )
                    except Exception as e:
                        logger.error(f"Error in coordinator.run: {e}")
                        await event_emitter.emit_execution_error(
                            trace_id=trace_id,
                            error=str(e),
                            error_type=type(e).__name__
                        )

                # Start the coordinator task
                coordinator_task = asyncio.create_task(run_coordinator())

                # Stream events
                async for event_data in event_stream:
                    yield event_data

                # Wait for coordinator to complete
                await coordinator_task

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
        logger.error(f"Error in manus_stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/manus/run")
async def manus_run(request: ManusRequest):
    """
    Execute a request using Manus-style multi-agent system (non-streaming)

    This endpoint uses a supervisor agent to coordinate multiple specialized agents
    that work asynchronously via Markdown file communication.
    """
    try:
        start_time = datetime.now()
        coordinator = get_manus_coordinator(request.user_id, request.tenant)

        # Handle session creation/update (similar to manus_stream)
        session_id = request.session_id or str(uuid.uuid4())
        existing_session = settings_manager.get_session(session_id)
        if not existing_session:
            # Extract title from first message
            title = request.request_text.replace('\n', ' ')[:60]
            if len(request.request_text) > 60:
                title += "..."

            settings_manager.create_session(
                session_id=session_id,
                user_id=request.user_id,
                tenant=request.tenant,
                title=title
            )
            logger.info(f"Created new session {session_id} with title: {title}")
        else:
            settings_manager.update_session_timestamp(session_id)

        logger.info(f"[Manus] Processing request: {request.request_text[:100]}...")

        result = await coordinator.run(
            request=request.request_text,
            session_id=session_id,
            max_wait_time=request.max_wait_time
        )

        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        logger.info(f"[Manus] Request completed in {execution_time:.2f}s")

        return {
            "success": result.get("success", False),
            "message": result.get("message", ""),
            "final_response": result.get("final_response", ""),
            "results": result.get("results", {}),
            "session_id": result.get("session_id"),
            "workspace_path": result.get("workspace_path"),
            "execution_time": execution_time
        }

    except Exception as e:
        logger.error(f"[Manus] Error executing request: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/manus/session/{session_id}/info")
async def manus_session_info(
    session_id: str,
    user_id: str = "test_user",
    tenant: str = "test_tenant"
):
    """Get information about a Manus session"""
    try:
        coordinator = get_manus_coordinator(user_id, tenant)

        # Check if this is the active session
        if coordinator.session_id != session_id:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found or not active"
            )

        info = coordinator.get_session_info()
        return info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Manus] Error getting session info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/manus/session/{session_id}/plan")
async def manus_get_plan(
    session_id: str,
    user_id: str = "test_user",
    tenant: str = "test_tenant"
):
    """Get the execution plan for a Manus session"""
    try:
        coordinator = get_manus_coordinator(user_id, tenant)

        # Check if this is the active session
        if coordinator.session_id != session_id:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found or not active"
            )

        plan = await coordinator.get_plan_status()

        if plan is None:
            raise HTTPException(
                status_code=404,
                detail=f"No plan found for session {session_id}"
            )

        return {
            "success": True,
            "session_id": session_id,
            "plan": plan
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Manus] Error getting plan: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/manus/session/{session_id}/agents")
async def manus_get_agent_statuses(
    session_id: str,
    user_id: str = "test_user",
    tenant: str = "test_tenant"
):
    """Get status of all agents in a Manus session"""
    try:
        coordinator = get_manus_coordinator(user_id, tenant)

        # Check if this is the active session
        if coordinator.session_id != session_id:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found or not active"
            )

        statuses = await coordinator.get_agent_statuses()

        return {
            "success": True,
            "session_id": session_id,
            "agent_statuses": statuses
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Manus] Error getting agent statuses: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def main():
    """Run the API server"""
    print("=" * 80)
    print("Personal Assistant Orchestration Service - API Server")
    print("=" * 80)
    print("\nStarting server...")

    # Check if running in development mode
    is_dev_mode = os.getenv("DEV_MODE", "true").lower() == "true"

    if is_dev_mode:
        print("\n⚡ Development mode")
        print("   - Backend API: http://localhost:8000")
        print("   - Frontend (Vite): http://localhost:5173  <-- Use this!")
        print("   - API Docs: http://localhost:8000/docs")
        print("\n   Run 'npm run dev' in frontend/ folder to start Vite dev server")
        print("   Or use './start.sh' (or 'start.bat') to start both servers together")
    else:
        print("   - Web UI: http://localhost:8000")
        print("   - API Docs: http://localhost:8000/docs")
        print("   - Health Check: http://localhost:8000/api/health")

    print("\n" + "=" * 80 + "\n")

    if is_dev_mode:
        # Development mode with hot reload (API only, frontend via Vite)
        uvicorn.run(
            "api_server:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            reload_dirs=["src"],  # Only watch backend code
            log_level="info"
        )
    else:
        # Production mode without reload
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
