"""
FastAPI server for the Orchestration Service
Provides REST API and serves web UI
"""

import asyncio
import json
import uuid
import os
from datetime import datetime
from typing import Optional
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import uvicorn

from orchestration.orchestrator import Orchestrator
from orchestration.settings_manager import SettingsManager


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


@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/settings")
async def get_settings(user_id: str = "test_user", tenant: str = "test_tenant"):
    """Get current settings for user"""
    try:
        settings_data = settings_manager.get_all_settings(user_id, tenant)
        return settings_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings")
async def save_settings(request: SettingsRequest):
    """Save LLM settings"""
    try:
        success = settings_manager.save_llm_settings(
            user_id=request.user_id,
            tenant=request.tenant,
            provider=request.provider,
            api_key=request.api_key,
            model=request.model,
            base_url=request.base_url
        )

        if success:
            # Clear orchestrator cache to force reload with new settings
            key = f"{request.tenant}:{request.user_id}"
            if key in orchestrators:
                del orchestrators[key]

            return {"success": True, "message": "Settings saved successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save settings")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings/test")
async def test_connection(request: TestConnectionRequest):
    """Test LLM connection"""
    try:
        result = settings_manager.test_connection(
            provider=request.provider,
            api_key=request.api_key,
            model=request.model,
            base_url=request.base_url
        )
        return result
    except Exception as e:
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


def main():
    """Run the API server"""
    print("=" * 80)
    print("Personal Assistant Orchestration Service - API Server")
    print("=" * 80)
    print("\nStarting server...")
    print("- Web UI: http://localhost:8000")
    print("- API Docs: http://localhost:8000/docs")
    print("- Health Check: http://localhost:8000/api/health")
    print("\n" + "=" * 80 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
