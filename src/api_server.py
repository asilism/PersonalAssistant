"""
FastAPI server for the Orchestration Service
Provides REST API and web UI for testing
"""

import asyncio
import json
import uuid
import os
from datetime import datetime
from typing import Optional, List
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
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


class BatchTestRequest(BaseModel):
    question_ids: List[int]
    user_id: Optional[str] = "test_user"
    tenant: Optional[str] = "test_tenant"


class SettingsRequest(BaseModel):
    provider: str
    api_key: str
    model: str
    user_id: Optional[str] = "test_user"
    tenant: Optional[str] = "test_tenant"


class TestConnectionRequest(BaseModel):
    provider: str
    api_key: str
    model: str


# Create FastAPI app
app = FastAPI(
    title="Personal Assistant Orchestration Service",
    description="LangGraph-based orchestration with MCP integration",
    version="1.0.0"
)

# Store orchestrator instances per user
orchestrators = {}

# Settings manager
settings_manager = SettingsManager()

# Load test questions
TEST_QUESTIONS_FILE = Path(__file__).parent.parent / "test_questions.json"
test_questions_data = {}

try:
    with open(TEST_QUESTIONS_FILE, 'r') as f:
        test_questions_data = json.load(f)
except Exception as e:
    print(f"Warning: Could not load test questions: {e}")


def get_orchestrator(user_id: str, tenant: str) -> Orchestrator:
    """Get or create an orchestrator for a user"""
    key = f"{tenant}:{user_id}"
    if key not in orchestrators:
        orchestrators[key] = Orchestrator(user_id=user_id, tenant=tenant)
    return orchestrators[key]


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the web UI with settings tab"""
    # Return embedded HTML - moved to separate file for brevity
    # In production, this would be served as static files
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Personal Assistant - Orchestration Service</title>
    <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Personal Assistant - Orchestration Service</h1>
            <p class="subtitle">LangGraph-based orchestration with MCP agent integration • 100 Test Questions</p>
        </div>

        <div class="tabs">
            <div class="tab active" onclick="switchTab('manual')">📝 Manual Testing</div>
            <div class="tab" onclick="switchTab('browser')">🔍 Test Browser</div>
            <div class="tab" onclick="switchTab('batch')">⚡ Batch Testing</div>
            <div class="tab" onclick="switchTab('settings')">⚙️ Settings</div>
        </div>

        <!-- Manual Testing Tab -->
        <div id="manual-tab" class="tab-content active">
            <div class="main-content">
                <div class="card">
                    <h2>📝 Make a Request</h2>
                    <form id="requestForm">
                        <div class="form-group">
                            <label for="requestText">Request</label>
                            <textarea id="requestText" placeholder="Enter your request here..." required></textarea>
                        </div>

                        <div class="form-group">
                            <label for="userId">User ID</label>
                            <input type="text" id="userId" value="test_user" required>
                        </div>

                        <div class="form-group">
                            <label for="tenant">Tenant</label>
                            <input type="text" id="tenant" value="test_tenant" required>
                        </div>

                        <button type="submit" id="submitBtn">Execute Request</button>
                    </form>

                    <div class="examples">
                        <h3>💡 Quick Examples:</h3>
                        <button class="example-btn" onclick="setExample('Send an email to john@example.com about the meeting tomorrow')">📧 Send Email</button>
                        <button class="example-btn" onclick="setExample('Create a calendar event for team meeting on Friday at 2 PM')">📅 Create Event</button>
                        <button class="example-btn" onclick="setExample('Search for issues assigned to me in Jira')">🎫 Search Jira</button>
                        <button class="example-btn" onclick="setExample('Calculate 25 * 8 + 150')">🔢 Calculate</button>
                        <button class="example-btn" onclick="setExample('Search for latest AI news and write a brief report')">📰 RPA: News Report</button>
                    </div>
                </div>

                <div class="card">
                    <h2>📊 Response</h2>
                    <div id="resultContainer">
                        <p style="color: #999; text-align: center; padding: 40px;">
                            Results will appear here after executing a request
                        </p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Test Browser Tab -->
        <div id="browser-tab" class="tab-content">
            <div class="test-browser">
                <h2>🔍 Browse Test Questions (100 Total)</h2>

                <div class="stats">
                    <div class="stat-item">
                        <div class="stat-number" id="statTotal">0</div>
                        <div class="stat-label">Total Questions</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number" id="statSingle">0</div>
                        <div class="stat-label">Single Agent</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number" id="statMulti">0</div>
                        <div class="stat-label">Multi Agent</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number" id="statRPA">0</div>
                        <div class="stat-label">RPA Included</div>
                    </div>
                </div>

                <div class="category-filter">
                    <button class="filter-btn active" data-filter="all">All (100)</button>
                    <button class="filter-btn" data-filter="Mail - Single">📧 Mail Only</button>
                    <button class="filter-btn" data-filter="Calendar - Single">📅 Calendar Only</button>
                    <button class="filter-btn" data-filter="Jira - Single">🎫 Jira Only</button>
                    <button class="filter-btn" data-filter="Calculator - Single">🔢 Calculator Only</button>
                    <button class="filter-btn" data-filter="Multi-Agent">🔀 Multi-Agent</button>
                    <button class="filter-btn" data-filter="RPA Included">🤖 RPA Included</button>
                </div>

                <div class="question-list" id="questionList">
                    <!-- Questions will be loaded here -->
                </div>
            </div>
        </div>

        <!-- Batch Testing Tab -->
        <div id="batch-tab" class="tab-content">
            <div class="test-browser">
                <h2>⚡ Batch Testing</h2>
                <p style="color: #666; margin-bottom: 20px;">Select multiple questions and run them in sequence</p>

                <div class="batch-actions">
                    <button onclick="selectAllQuestions()">Select All</button>
                    <button onclick="clearSelection()">Clear Selection</button>
                    <button onclick="runBatchTests()" id="batchRunBtn">Run Selected Tests</button>
                    <span id="selectionCount" style="margin-left: 10px; align-self: center; color: #666;">0 selected</span>
                </div>

                <div class="question-list" id="batchQuestionList">
                    <!-- Questions will be loaded here -->
                </div>

                <div class="test-results" id="testResults">
                    <!-- Results will appear here -->
                </div>
            </div>
        </div>

        <!-- Settings Tab -->
        <div id="settings-tab" class="tab-content">
            <div class="settings-container">
                <h2>⚙️ LLM Settings</h2>
                <p style="color: #666; margin-bottom: 20px;">Configure your LLM provider and API credentials</p>

                <div class="settings-card">
                    <div class="form-group">
                        <label for="llmProvider">LLM Provider</label>
                        <select id="llmProvider" onchange="updateModelOptions()">
                            <option value="anthropic">Anthropic Claude</option>
                            <option value="openai">OpenAI GPT</option>
                            <option value="openrouter">OpenRouter</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label for="apiKey">API Key</label>
                        <input type="password" id="apiKey" placeholder="Enter your API key">
                        <small style="color: #666;">Your API key is encrypted and stored securely</small>
                    </div>

                    <div class="form-group">
                        <label for="llmModel">Model</label>
                        <select id="llmModel">
                            <!-- Options will be populated based on provider -->
                        </select>
                    </div>

                    <div class="settings-actions">
                        <button onclick="testConnection()" id="testBtn">🧪 Test Connection</button>
                        <button onclick="saveSettings()" id="saveBtn">💾 Save Settings</button>
                    </div>

                    <div id="settingsResult" class="settings-result">
                        <!-- Result messages will appear here -->
                    </div>
                </div>

                <div class="current-settings-card">
                    <h3>Current Settings</h3>
                    <div id="currentSettings">
                        <div class="loading">Loading...</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="/static/app.js"></script>
</body>
</html>
"""
    return html_content


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


@app.get("/api/test-questions")
async def get_test_questions():
    """Get all test questions with statistics"""
    if not test_questions_data.get("single_agent_questions"):
        raise HTTPException(status_code=404, detail="Test questions not found")

    questions = test_questions_data["single_agent_questions"]

    # Calculate statistics
    single_count = sum(1 for q in questions if "Single" in q.get("category", ""))
    multi_count = sum(1 for q in questions if q.get("category") == "Multi-Agent")
    rpa_count = sum(1 for q in questions if q.get("category") == "RPA Included")

    return {
        "questions": questions,
        "statistics": {
            "total": len(questions),
            "single_agent": single_count,
            "multi_agent": multi_count,
            "rpa_included": rpa_count
        }
    }


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
            model=request.model
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
            model=request.model
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
    print("- Test Questions: 100 questions loaded")
    print("\n" + "=" * 80 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
