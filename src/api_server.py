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


# Create FastAPI app
app = FastAPI(
    title="Personal Assistant Orchestration Service",
    description="LangGraph-based orchestration with MCP integration",
    version="1.0.0"
)

# Store orchestrator instances per user
orchestrators = {}

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
            max-width: 1400px;
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
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        .tab {
            background: white;
            padding: 12px 24px;
            border-radius: 10px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .tab:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
        .tab.active {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
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
            width: auto;
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
        .test-browser {
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .category-filter {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .filter-btn {
            background: white;
            border: 2px solid #667eea;
            padding: 8px 16px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
            width: auto;
        }
        .filter-btn.active {
            background: #667eea;
            color: white;
        }
        .question-list {
            max-height: 600px;
            overflow-y: auto;
        }
        .question-item {
            background: #f8f9fa;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 5px;
            border-left: 4px solid #667eea;
            cursor: pointer;
            transition: all 0.2s;
        }
        .question-item:hover {
            background: #e9ecef;
            transform: translateX(5px);
        }
        .question-item.selected {
            background: #d4edda;
            border-left-color: #28a745;
        }
        .question-id {
            font-weight: 600;
            color: #667eea;
            margin-bottom: 5px;
        }
        .question-category {
            font-size: 12px;
            color: #666;
            margin-bottom: 5px;
        }
        .question-text {
            color: #333;
            font-size: 14px;
        }
        .batch-actions {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        .batch-actions button {
            width: auto;
            padding: 10px 20px;
        }
        .stats {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
        }
        .stat-item {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            flex: 1;
            text-align: center;
        }
        .stat-number {
            font-size: 24px;
            font-weight: 600;
            color: #667eea;
        }
        .stat-label {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }
        .full-width {
            grid-column: 1 / -1;
        }
        .test-results {
            margin-top: 20px;
        }
        .test-result-item {
            background: #f8f9fa;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 5px;
        }
        .test-result-item.success {
            border-left: 4px solid #28a745;
        }
        .test-result-item.failed {
            border-left: 4px solid #dc3545;
        }
    </style>
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
        </div>

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
    </div>

    <script>
        let testQuestions = [];
        let selectedQuestions = new Set();

        // Load test questions
        async function loadTestQuestions() {
            try {
                const response = await fetch('/api/test-questions');
                const data = await response.json();
                testQuestions = data.questions;

                // Update stats
                const stats = data.statistics;
                document.getElementById('statTotal').textContent = stats.total;
                document.getElementById('statSingle').textContent = stats.single_agent;
                document.getElementById('statMulti').textContent = stats.multi_agent;
                document.getElementById('statRPA').textContent = stats.rpa_included;

                renderQuestions();
                renderBatchQuestions();
            } catch (error) {
                console.error('Failed to load test questions:', error);
            }
        }

        function renderQuestions(filter = 'all') {
            const list = document.getElementById('questionList');
            const filtered = filter === 'all'
                ? testQuestions
                : testQuestions.filter(q => q.category === filter);

            list.innerHTML = filtered.map(q => `
                <div class="question-item" onclick="executeQuestion(${q.id})">
                    <div class="question-id">Question #${q.id}</div>
                    <div class="question-category">${q.category}</div>
                    <div class="question-text">${q.question}</div>
                </div>
            `).join('');
        }

        function renderBatchQuestions() {
            const list = document.getElementById('batchQuestionList');
            list.innerHTML = testQuestions.map(q => `
                <div class="question-item ${selectedQuestions.has(q.id) ? 'selected' : ''}"
                     onclick="toggleQuestion(${q.id})">
                    <div class="question-id">Question #${q.id}</div>
                    <div class="question-category">${q.category}</div>
                    <div class="question-text">${q.question}</div>
                </div>
            `).join('');

            document.getElementById('selectionCount').textContent = `${selectedQuestions.size} selected`;
        }

        function toggleQuestion(id) {
            if (selectedQuestions.has(id)) {
                selectedQuestions.delete(id);
            } else {
                selectedQuestions.add(id);
            }
            renderBatchQuestions();
        }

        function selectAllQuestions() {
            testQuestions.forEach(q => selectedQuestions.add(q.id));
            renderBatchQuestions();
        }

        function clearSelection() {
            selectedQuestions.clear();
            renderBatchQuestions();
        }

        async function runBatchTests() {
            if (selectedQuestions.size === 0) {
                alert('Please select at least one question');
                return;
            }

            const btn = document.getElementById('batchRunBtn');
            const resultsDiv = document.getElementById('testResults');

            btn.disabled = true;
            btn.textContent = 'Running Tests...';
            resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>Running batch tests...</p></div>';

            const results = [];
            let successCount = 0;
            let failCount = 0;

            for (const id of Array.from(selectedQuestions)) {
                const question = testQuestions.find(q => q.id === id);

                try {
                    const response = await fetch('/api/orchestrate', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            request_text: question.question,
                            user_id: 'test_user',
                            tenant: 'test_tenant'
                        })
                    });

                    const data = await response.json();

                    if (data.success) {
                        successCount++;
                    } else {
                        failCount++;
                    }

                    results.push({
                        id: id,
                        question: question.question,
                        category: question.category,
                        success: data.success,
                        message: data.message,
                        execution_time: data.execution_time
                    });

                    // Update results in real-time
                    displayBatchResults(results, successCount, failCount);

                } catch (error) {
                    failCount++;
                    results.push({
                        id: id,
                        question: question.question,
                        category: question.category,
                        success: false,
                        message: error.message,
                        execution_time: 0
                    });
                    displayBatchResults(results, successCount, failCount);
                }
            }

            btn.disabled = false;
            btn.textContent = 'Run Selected Tests';
        }

        function displayBatchResults(results, successCount, failCount) {
            const resultsDiv = document.getElementById('testResults');
            const total = successCount + failCount;
            const successRate = total > 0 ? ((successCount / total) * 100).toFixed(1) : 0;

            let html = `
                <h3>Test Results (${total} tests)</h3>
                <div class="stats">
                    <div class="stat-item">
                        <div class="stat-number" style="color: #28a745;">${successCount}</div>
                        <div class="stat-label">Passed</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number" style="color: #dc3545;">${failCount}</div>
                        <div class="stat-label">Failed</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">${successRate}%</div>
                        <div class="stat-label">Success Rate</div>
                    </div>
                </div>
                <div style="margin-top: 20px;">
            `;

            results.forEach(r => {
                html += `
                    <div class="test-result-item ${r.success ? 'success' : 'failed'}">
                        <div style="font-weight: 600; margin-bottom: 5px;">
                            ${r.success ? '✅' : '❌'} Question #${r.id} - ${r.category}
                        </div>
                        <div style="font-size: 14px; color: #666; margin-bottom: 5px;">${r.question}</div>
                        <div style="font-size: 13px; color: ${r.success ? '#28a745' : '#dc3545'};">
                            ${r.message} (${r.execution_time.toFixed(2)}s)
                        </div>
                    </div>
                `;
            });

            html += '</div>';
            resultsDiv.innerHTML = html;
        }

        // Category filter
        document.addEventListener('DOMContentLoaded', () => {
            loadTestQuestions();

            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                    e.target.classList.add('active');
                    renderQuestions(e.target.dataset.filter);
                });
            });
        });

        function switchTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            event.target.classList.add('active');
            document.getElementById(`${tabName}-tab`).classList.add('active');
        }

        function setExample(text) {
            document.getElementById('requestText').value = text;
        }

        async function executeQuestion(id) {
            const question = testQuestions.find(q => q.id === id);
            if (!question) return;

            // Switch to manual tab and fill in the question
            switchTab('manual');
            document.querySelectorAll('.tab')[0].classList.add('active');
            setExample(question.question);

            // Auto-submit
            setTimeout(() => {
                document.getElementById('requestForm').dispatchEvent(new Event('submit'));
            }, 100);
        }

        document.getElementById('requestForm').addEventListener('submit', async (e) => {
            e.preventDefault();

            const submitBtn = document.getElementById('submitBtn');
            const resultContainer = document.getElementById('resultContainer');

            const requestText = document.getElementById('requestText').value;
            const userId = document.getElementById('userId').value;
            const tenant = document.getElementById('tenant').value;

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
