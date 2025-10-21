"""
FastAPI server for the Orchestration Service
Provides REST API and web UI for testing
"""

import asyncio
import uuid
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

from orchestration.orchestrator import Orchestrator


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


# Create FastAPI app
app = FastAPI(
    title="Personal Assistant Orchestration Service",
    description="LangGraph-based orchestration with MCP integration",
    version="1.0.0"
)

# Store orchestrator instances per user
orchestrators = {}


def get_orchestrator(user_id: str, tenant: str) -> Orchestrator:
    """Get or create an orchestrator for a user"""
    key = f"{tenant}:{user_id}"
    if key not in orchestrators:
        orchestrators[key] = Orchestrator(user_id=user_id, tenant=tenant)
    return orchestrators[key]


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the web UI"""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Personal Assistant - Orchestration Service</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
        }
        .subtitle {
            color: #666;
            font-size: 14px;
        }
        .main-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        .card {
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .card h2 {
            color: #333;
            margin-bottom: 20px;
            font-size: 20px;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            color: #555;
            font-weight: 500;
        }
        input, textarea, select {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
        }
        textarea {
            min-height: 120px;
            resize: vertical;
            font-family: inherit;
        }
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            width: 100%;
            transition: opacity 0.2s;
        }
        button:hover { opacity: 0.9; }
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .result-box {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 5px;
            padding: 15px;
            margin-top: 15px;
            max-height: 400px;
            overflow-y: auto;
        }
        .success {
            border-left: 4px solid #28a745;
            background: #d4edda;
        }
        .error {
            border-left: 4px solid #dc3545;
            background: #f8d7da;
        }
        .loading {
            text-align: center;
            padding: 20px;
            color: #667eea;
        }
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .examples {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-top: 15px;
        }
        .examples h3 {
            font-size: 14px;
            margin-bottom: 10px;
            color: #555;
        }
        .example-btn {
            background: white;
            border: 1px solid #ddd;
            padding: 8px 12px;
            margin: 5px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
            display: inline-block;
            transition: all 0.2s;
        }
        .example-btn:hover {
            background: #667eea;
            color: white;
            border-color: #667eea;
        }
        pre {
            background: #2d2d2d;
            color: #f8f8f2;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            font-size: 13px;
        }
        .meta-info {
            display: flex;
            gap: 20px;
            margin-top: 10px;
            font-size: 13px;
            color: #666;
        }
        .meta-item {
            display: flex;
            align-items: center;
            gap: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Personal Assistant - Orchestration Service</h1>
            <p class="subtitle">LangGraph-based orchestration with MCP agent integration</p>
        </div>

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
                    <h3>💡 Example Requests:</h3>
                    <button class="example-btn" onclick="setExample('Send an email to john@example.com about the meeting tomorrow')">📧 Send Email</button>
                    <button class="example-btn" onclick="setExample('Create a calendar event for team meeting on Friday at 2 PM')">📅 Create Event</button>
                    <button class="example-btn" onclick="setExample('Search for issues assigned to me in Jira')">🎫 Search Jira</button>
                    <button class="example-btn" onclick="setExample('Calculate 25 * 8 + 150')">🔢 Calculate</button>
                    <button class="example-btn" onclick="setExample('Search for latest AI news and write a brief report')">📰 RPA: News Report</button>
                    <button class="example-btn" onclick="setExample('Collect attendance for team meeting and show summary')">✅ RPA: Attendance</button>
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

    <script>
        function setExample(text) {
            document.getElementById('requestText').value = text;
        }

        document.getElementById('requestForm').addEventListener('submit', async (e) => {
            e.preventDefault();

            const submitBtn = document.getElementById('submitBtn');
            const resultContainer = document.getElementById('resultContainer');

            // Get form values
            const requestText = document.getElementById('requestText').value;
            const userId = document.getElementById('userId').value;
            const tenant = document.getElementById('tenant').value;

            // Show loading
            submitBtn.disabled = true;
            submitBtn.textContent = 'Executing...';
            resultContainer.innerHTML = `
                <div class="loading">
                    <div class="spinner"></div>
                    <p>Processing your request...</p>
                </div>
            `;

            try {
                const response = await fetch('/api/orchestrate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        request_text: requestText,
                        user_id: userId,
                        tenant: tenant
                    })
                });

                const data = await response.json();

                // Display result
                const resultClass = data.success ? 'success' : 'error';
                let resultHTML = `
                    <div class="result-box ${resultClass}">
                        <h3>${data.success ? '✅ Success' : '❌ Error'}</h3>
                        <p><strong>Message:</strong> ${data.message}</p>
                        <div class="meta-info">
                            <div class="meta-item">⏱️ ${data.execution_time.toFixed(2)}s</div>
                            ${data.plan_id ? `<div class="meta-item">🆔 Plan: ${data.plan_id}</div>` : ''}
                            <div class="meta-item">🔍 Trace: ${data.trace_id}</div>
                        </div>
                `;

                if (data.results) {
                    resultHTML += `
                        <h4 style="margin-top: 15px;">Results:</h4>
                        <pre>${JSON.stringify(data.results, null, 2)}</pre>
                    `;
                }

                resultHTML += `</div>`;
                resultContainer.innerHTML = resultHTML;

            } catch (error) {
                resultContainer.innerHTML = `
                    <div class="result-box error">
                        <h3>❌ Request Failed</h3>
                        <p>${error.message}</p>
                    </div>
                `;
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Execute Request';
            }
        });
    </script>
</body>
</html>
    """


@app.post("/api/orchestrate", response_model=OrchestrationResponse)
async def orchestrate(request: OrchestrationRequest):
    """
    Execute an orchestration request
    """
    try:
        # Get orchestrator
        orchestrator = get_orchestrator(request.user_id, request.tenant)

        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())

        # Generate trace ID
        trace_id = str(uuid.uuid4())

        # Run orchestration
        result = await orchestrator.run(
            session_id=session_id,
            request_text=request.request_text,
            trace_id=trace_id
        )

        # Return response
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


@app.get("/api/tools")
async def list_tools():
    """List available MCP tools"""
    try:
        # Get a default orchestrator to discover tools
        orchestrator = get_orchestrator("system", "system")

        # Initialize if needed
        if not orchestrator.settings:
            await orchestrator._initialize()

        # Return available tools
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
