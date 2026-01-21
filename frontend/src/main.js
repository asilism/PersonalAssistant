// Import styles
import './styles.css'

// Tab switching
function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.nav-item').forEach(nav => {
        nav.classList.remove('active');
    });

    // Show selected tab
    document.getElementById(`${tabName}-tab`).classList.add('active');
    event.target.classList.add('active');

    // Load settings if switching to settings tab
    if (tabName === 'settings') {
        loadCurrentSettings();
    } else if (tabName === 'mcp') {
        loadMCPServers();
        loadMCPTools();
    }
}

// Auto-resize textarea
document.addEventListener('DOMContentLoaded', () => {
    const textarea = document.getElementById('requestText');
    if (textarea) {
        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });

        // Submit on Enter (without Shift)
        textarea.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                document.getElementById('requestForm').dispatchEvent(new Event('submit'));
            }
        });
    }
});

// Model options for each provider
const modelOptions = {
    anthropic: [
        'claude-sonnet-4-5-20250929',
        'claude-haiku-4-5-20251001'
    ],
    openai: [
        'gpt-4-turbo-preview',
        'gpt-4',
        'gpt-3.5-turbo'
    ],
    openrouter: [
        'openai/gpt-oss-20b',
        'openai/gpt-oss-120b',
    ]
};

// Update model options based on selected provider
function updateModelOptions() {
    const provider = document.getElementById('llmProvider').value;
    const modelSelect = document.getElementById('llmModel');

    modelSelect.innerHTML = '';
    modelOptions[provider].forEach(model => {
        const option = document.createElement('option');
        option.value = model;
        option.textContent = model;
        modelSelect.appendChild(option);
    });
}

// Session ID management
let sessionId = null;

// Get session ID without creating a new one
function getSessionId() {
    if (!sessionId) {
        sessionId = localStorage.getItem('sessionId');
    }
    return sessionId;
}

// Get or create session ID (only used when sending messages)
function getOrCreateSessionId() {
    if (!sessionId) {
        // Try to get from localStorage
        sessionId = localStorage.getItem('sessionId');
        if (!sessionId) {
            // Create new session ID
            sessionId = 'session-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('sessionId', sessionId);
        }
    }
    return sessionId;
}

// Clear current session
function clearSession() {
    sessionId = null;
    localStorage.removeItem('sessionId');
}

// Execution mode management
function getExecutionMode() {
    // Try to get from localStorage, default to 'langgraph'
    const mode = localStorage.getItem('executionMode');
    return mode || 'langgraph';
}

function saveExecutionMode(mode) {
    localStorage.setItem('executionMode', mode);
}

function loadExecutionMode() {
    const mode = getExecutionMode();
    const radioBtn = document.querySelector(`input[name="executionMode"][value="${mode}"]`);
    if (radioBtn) {
        radioBtn.checked = true;
    }
}

function setupExecutionModeListeners() {
    const radios = document.querySelectorAll('input[name="executionMode"]');
    radios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            saveExecutionMode(e.target.value);
            console.log('Execution mode changed to:', e.target.value);
        });
    });
}

// User profile menu management
function setupUserProfileMenu() {
    const profileBtn = document.getElementById('userProfileBtn');
    const dropdownMenu = document.getElementById('userDropdownMenu');

    if (!profileBtn || !dropdownMenu) return;

    // Toggle dropdown on button click
    profileBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isActive = dropdownMenu.classList.contains('show');

        if (isActive) {
            closeUserDropdown();
        } else {
            openUserDropdown();
        }
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!profileBtn.contains(e.target) && !dropdownMenu.contains(e.target)) {
            closeUserDropdown();
        }
    });

    // Close dropdown when clicking menu items
    dropdownMenu.querySelectorAll('.dropdown-item').forEach(item => {
        item.addEventListener('click', () => {
            closeUserDropdown();
        });
    });
}

function openUserDropdown() {
    const profileBtn = document.getElementById('userProfileBtn');
    const dropdownMenu = document.getElementById('userDropdownMenu');

    if (profileBtn && dropdownMenu) {
        profileBtn.classList.add('active');
        dropdownMenu.classList.add('show');
    }
}

function closeUserDropdown() {
    const profileBtn = document.getElementById('userProfileBtn');
    const dropdownMenu = document.getElementById('userDropdownMenu');

    if (profileBtn && dropdownMenu) {
        profileBtn.classList.remove('active');
        dropdownMenu.classList.remove('show');
    }
}

function handleLogout() {
    if (confirm('Are you sure you want to logout?')) {
        // Clear session data
        localStorage.clear();
        sessionStorage.clear();

        // Redirect to login page or reload
        alert('Logged out successfully. In a real application, you would be redirected to the login page.');
        // window.location.href = '/login';  // Uncomment when login page is available
    }
}

// Load chat history
async function loadChatHistory() {
    const currentSessionId = getSessionId();
    const chatMessages = document.getElementById('chatMessages');

    console.log('[loadChatHistory] Loading for session:', currentSessionId);

    if (!chatMessages) {
        console.error('[loadChatHistory] chatMessages element not found');
        return;
    }

    // If no session exists, show welcome message
    if (!currentSessionId) {
        console.log('[loadChatHistory] No session exists, showing empty state');
        chatMessages.innerHTML = `
            <div class="welcome-message">
                <h2>대화를 시작해보세요</h2>
                <p>아래 입력창에 메시지를 입력하면 새로운 대화가 시작됩니다.</p>
                <p style="font-size: 14px; color: var(--text-tertiary); margin-top: 16px;">
                    MCP 서버에 등록된 도구들을 활용하여 다양한 작업을 수행할 수 있습니다.
                </p>
            </div>
        `;
        return;
    }

    try {
        const response = await fetch(`/api/chat-history?session_id=${currentSessionId}`);
        const data = await response.json();

        console.log('[loadChatHistory] Response:', response.ok, 'Messages:', data.messages?.length || 0);

        if (response.ok && data.messages && data.messages.length > 0) {
            // Clear existing messages
            chatMessages.innerHTML = '';

            // Add each message
            data.messages.forEach(msg => {
                console.log('[loadChatHistory] Adding message:', msg.role, msg.content.substring(0, 50) + '...');
                addMessageBubble(msg.role, msg.content, false, false);
            });
            console.log('[loadChatHistory] Added', data.messages.length, 'messages');
        } else {
            // No messages - show welcome message
            console.log('[loadChatHistory] No messages, showing welcome');
            chatMessages.innerHTML = `
                <div class="welcome-message">
                    <h2>What can I help you with?</h2>
                    <p>MCP 서버에 등록된 도구들을 활용하여 다양한 작업을 수행할 수 있습니다.</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('[loadChatHistory] Error:', error);
        // Show welcome message on error too
        chatMessages.innerHTML = `
            <div class="welcome-message">
                <h2>What can I help you with?</h2>
                <p>MCP 서버에 등록된 도구들을 활용하여 다양한 작업을 수행할 수 있습니다.</p>
            </div>
        `;
    }
}

// Clear chat history
async function clearChatHistory() {
    if (!confirm('정말로 대화 이력을 삭제하시겠습니까?')) {
        return;
    }

    const currentSessionId = getOrCreateSessionId();

    try {
        // Delete the entire session (including chat history)
        const response = await fetch(`/api/sessions/${currentSessionId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (response.ok) {
            // Start a new chat
            await startNewChat();
            alert('대화 이력이 삭제되었습니다. 새로운 대화가 시작됩니다.');
        }
    } catch (error) {
        alert('대화 이력 삭제에 실패했습니다: ' + error.message);
    }
}

// Initialize model options on page load
document.addEventListener('DOMContentLoaded', () => {
    updateModelOptions();
    loadCurrentSettings();
    loadChatHistory();
    loadSessions();  // Load chat sessions in sidebar
    loadExecutionMode();
    setupExecutionModeListeners();
    setupUserProfileMenu();  // Set up user profile dropdown

    // Set up form submission
    document.getElementById('requestForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await executeRequest();
    });
});

// Ensure session exists in database
async function ensureSessionExists(userId, tenant) {
    const currentSessionId = getSessionId();

    // If no session exists, create a new one
    if (!currentSessionId) {
        console.log('[ensureSessionExists] No session exists, creating new session');
        const response = await fetch('/api/sessions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: userId,
                tenant: tenant,
                title: 'New conversation'
            })
        });

        const data = await response.json();

        if (response.ok) {
            // Update session ID
            sessionId = data.session_id;
            localStorage.setItem('sessionId', data.session_id);

            // Update chat title
            const chatTitle = document.querySelector('.chat-title');
            if (chatTitle) {
                chatTitle.textContent = 'New conversation';
            }

            // Reload sessions list to show the new session
            await loadSessions();

            console.log('[ensureSessionExists] New session created:', sessionId);
            return sessionId;
        } else {
            throw new Error('Failed to create session: ' + (data.detail || 'Unknown error'));
        }
    }

    return currentSessionId;
}

// Execute orchestration request - supports both LangGraph and Manus modes
async function executeRequest() {
    const requestText = document.getElementById('requestText').value;
    const userId = document.getElementById('userId').value;
    const tenant = document.getElementById('tenant').value;
    const submitBtn = document.getElementById('submitBtn');
    const chatMessages = document.getElementById('chatMessages');

    if (!requestText.trim()) return;

    // Ensure session exists before sending request
    const currentSessionId = await ensureSessionExists(userId, tenant);
    const executionMode = getExecutionMode();

    // Remove placeholder or welcome message if exists
    const placeholder = chatMessages.querySelector('.placeholder');
    const welcome = chatMessages.querySelector('.welcome-message');
    if (placeholder) placeholder.remove();
    if (welcome) welcome.remove();

    // Add user message bubble
    addMessageBubble('user', requestText);

    // Clear input
    document.getElementById('requestText').value = '';
    document.getElementById('requestText').style.height = 'auto';

    // Disable button and show loading
    submitBtn.disabled = true;

    // Add loading bubble for streaming content
    const loadingId = addMessageBubble('assistant', '', true);

    // Clear previous logs
    clearExecutionLogs();

    try {
        if (executionMode === 'manus') {
            // Manus mode - non-streaming
            await executeManusMode(requestText, userId, tenant, currentSessionId, loadingId);
        } else {
            // LangGraph mode - SSE streaming (default)
            await executeLangGraphMode(requestText, userId, tenant, currentSessionId, loadingId);
        }
    } catch (error) {
        if (loadingId) removeMessageBubble(loadingId);
        addMessageBubble('error', `Network error: ${error.message}`);
        addExecutionLogEntry({
            event_type: 'execution_error',
            message: error.message,
            timestamp: new Date().toISOString()
        });
    } finally {
        submitBtn.disabled = false;
        // Auto-update session title if it's a new conversation
        await autoUpdateSessionTitle(currentSessionId, requestText);
        // Reload sessions list to show the new/updated session
        await loadSessions();
    }
}

// Execute in LangGraph mode (original SSE streaming)
async function executeLangGraphMode(requestText, userId, tenant, sessionId, loadingId) {
    addExecutionLogEntry({
        event_type: 'execution_started',
        message: 'LangGraph mode: Starting execution with SSE streaming',
        timestamp: new Date().toISOString()
    });

    // Use fetch to initiate SSE stream
    const response = await fetch('/api/orchestrate/stream', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            request_text: requestText,
            user_id: userId,
            tenant: tenant,
            session_id: sessionId
        })
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    // Process SSE stream
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalMessage = '';
    let executionCompleted = false;

    while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop(); // Keep incomplete line in buffer

        for (const line of lines) {
            if (!line.trim() || line.startsWith(':')) continue;

            const dataMatch = line.match(/^data: (.+)$/);
            if (!dataMatch) continue;

            try {
                const eventData = JSON.parse(dataMatch[1]);

                // Check for done signal
                if (eventData.done) {
                    executionCompleted = true;
                    break;
                }

                // Add execution log entry
                addExecutionLogEntry(eventData);

                // Store final message and data if execution completed
                if (eventData.event_type === 'execution_completed') {
                    finalMessage = eventData.message;
                    // Check if there's structured data to display
                    if (eventData.data && eventData.data.results) {
                        const dataType = eventData.data.data_type;
                        finalMessage = formatExecutionResults(eventData.message, eventData.data.results, dataType);
                    }
                }
            } catch (e) {
                console.error('Error parsing SSE data:', e);
            }
        }

        if (executionCompleted) break;
    }

    // Remove loading bubble (if exists)
    if (loadingId) removeMessageBubble(loadingId);

    // Add assistant response bubble with final message
    if (finalMessage) {
        addMessageBubble('assistant', finalMessage);
    } else {
        addMessageBubble('assistant', 'Execution completed');
    }
}

// Execute in Manus mode (multi-agent SSE streaming)
async function executeManusMode(requestText, userId, tenant, sessionId, loadingId) {
    addExecutionLogEntry({
        event_type: 'execution_started',
        message: 'Manus mode: Starting multi-agent execution with real-time streaming',
        timestamp: new Date().toISOString()
    });

    // Add planning indicator message to chat
    showPlanningIndicator();

    // Use fetch to initiate SSE stream
    const response = await fetch('/api/manus/stream', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            request_text: requestText,
            user_id: userId,
            tenant: tenant,
            session_id: sessionId,
            max_wait_time: 60
        })
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    // Process SSE stream
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalMessage = '';
    let workspacePath = '';
    let executionCompleted = false;

    while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop(); // Keep incomplete line in buffer

        for (const line of lines) {
            if (!line.trim() || line.startsWith(':')) continue;

            const dataMatch = line.match(/^data: (.+)$/);
            if (!dataMatch) continue;

            try {
                const eventData = JSON.parse(dataMatch[1]);

                // Check for done signal
                if (eventData.done) {
                    executionCompleted = true;
                    break;
                }

                // Handle plan_generation_progress - show in CHAT WINDOW, not execution log
                if (eventData.event_type === 'plan_generation_progress') {
                    const step = eventData.data?.step || 'create_plan';
                    const content = eventData.data?.content || '';
                    const isComplete = eventData.data?.is_complete || false;

                    // Update loading bubble with streaming content
                    if (loadingId) {
                        let displayContent = '';
                        if (step === 'analyze_request') {
                            displayContent = `📘 Step 1: Analyzing Request...\n\n${content}`;
                        } else if (step === 'create_plan') {
                            displayContent = `📙 Step 2: Creating Execution Plan...\n\n${content}`;
                        } else {
                            displayContent = content;
                        }
                        updateMessageBubble(loadingId, displayContent, isComplete);
                    }

                    // DON'T add to execution log - only show in chat
                } else {
                    // Add all OTHER events to execution log
                    addExecutionLogEntry(eventData);
                }

                // Store final message and workspace info if execution completed
                if (eventData.event_type === 'execution_completed') {
                    finalMessage = eventData.data?.final_response || eventData.message;
                    workspacePath = eventData.data?.workspace_path || '';

                    // Store task summary for completion message
                    if (eventData.data?.task_summary) {
                        window.lastTaskSummary = eventData.data.task_summary;
                        window.lastExecutionSuccess = eventData.data?.success;
                        window.lastExecutionTime = eventData.data?.execution_time;
                    }
                }

                // Update plan in chat if plan_created or plan_updated
                if ((eventData.event_type === 'plan_created' || eventData.event_type === 'plan_updated') && eventData.data) {
                    updatePlanMessageInChat(eventData.data);
                }
            } catch (e) {
                console.error('Error parsing SSE data:', e);
            }
        }

        if (executionCompleted) break;
    }

    // Remove loading bubble (if exists)
    if (loadingId) removeMessageBubble(loadingId);

    // Add assistant response bubble with final message
    if (finalMessage) {
        // Format the response with final message as main content
        let formattedMessage = '';

        // Add the LLM-generated final response as the main message
        formattedMessage += `<div class="message-text">${escapeHtml(finalMessage)}</div>`;

        // Add collapsible task summary if available
        if (window.lastTaskSummary) {
            const taskSummary = window.lastTaskSummary;
            const success = window.lastExecutionSuccess;
            const executionTime = window.lastExecutionTime;

            let summaryClass = 'task-summary-compact';
            if (!success && taskSummary.completed > 0) {
                summaryClass += ' partial';
            } else if (!success) {
                summaryClass += ' failed';
            }

            formattedMessage += `<details class="${summaryClass}" style="margin-top: 12px;" ${success ? '' : 'open'}>`;
            formattedMessage += `<summary class="task-summary-header">`;
            if (success) {
                formattedMessage += `✅ 작업 완료 (${taskSummary.completed}/${taskSummary.total})`;
            } else if (taskSummary.completed > 0) {
                formattedMessage += `⚠️ 일부 완료 (${taskSummary.completed}/${taskSummary.total})`;
            } else {
                formattedMessage += `❌ 작업 실패 (${taskSummary.failed}/${taskSummary.total})`;
            }
            formattedMessage += `</summary>`;

            formattedMessage += `<div class="task-summary-content">`;
            formattedMessage += `<div class="task-summary-stats">`;
            formattedMessage += `<div class="task-summary-stat">`;
            formattedMessage += `<span class="stat-label">완료</span>`;
            formattedMessage += `<span class="stat-value">${taskSummary.completed}/${taskSummary.total}</span>`;
            formattedMessage += `</div>`;
            if (taskSummary.failed > 0) {
                formattedMessage += `<div class="task-summary-stat">`;
                formattedMessage += `<span class="stat-label">실패</span>`;
                formattedMessage += `<span class="stat-value stat-error">${taskSummary.failed}</span>`;
                formattedMessage += `</div>`;
            }
            if (executionTime) {
                formattedMessage += `<div class="task-summary-stat">`;
                formattedMessage += `<span class="stat-label">실행 시간</span>`;
                formattedMessage += `<span class="stat-value">${(executionTime / 1000).toFixed(1)}초</span>`;
                formattedMessage += `</div>`;
            }
            formattedMessage += `</div>`;
            formattedMessage += `</div>`;
            formattedMessage += `</details>`;

            // Clean up temporary data
            delete window.lastTaskSummary;
            delete window.lastExecutionSuccess;
            delete window.lastExecutionTime;
        }

        if (workspacePath) {
            formattedMessage += `<div style="margin-top: 10px; padding: 8px; background: #f3f4f6; border-radius: 4px; font-size: 12px; color: #6b7280;">`;
            formattedMessage += `<strong>📁 Workspace:</strong> <code>${escapeHtml(workspacePath)}</code>`;
            formattedMessage += `</div>`;
        }

        addMessageBubble('assistant', formattedMessage);
    } else {
        addMessageBubble('assistant', 'Execution completed');
    }
}

// Add message bubble
function addMessageBubble(type, content, isLoading = false, showTimestamp = true) {
    const chatMessages = document.getElementById('chatMessages');
    const messageId = 'msg-' + Date.now() + '-' + Math.random();

    const messageDiv = document.createElement('div');
    messageDiv.id = messageId;
    messageDiv.className = `message-bubble ${type}-message`;

    if (isLoading) {
        messageDiv.innerHTML = `
            <div class="loading-dots">
                <span></span><span></span><span></span>
            </div>
        `;
    } else {
        if (type === 'user') {
            messageDiv.innerHTML = `<div class="message-content">${escapeHtml(content)}</div>`;
        } else if (type === 'error') {
            messageDiv.innerHTML = `
                <div class="message-icon">⚠️</div>
                <div class="message-content">${escapeHtml(content)}</div>
            `;
        } else {
            // Render markdown for assistant messages
            const renderedContent = window.marked ? window.marked.parse(content) : content;
            messageDiv.innerHTML = `
                <div class="message-icon">🤖</div>
                <div class="message-content">${renderedContent}</div>
            `;
        }

        if (showTimestamp) {
            const timestamp = document.createElement('div');
            timestamp.className = 'message-timestamp';
            timestamp.textContent = new Date().toLocaleTimeString();
            messageDiv.appendChild(timestamp);
        }
    }

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return messageId;
}

// Remove message bubble
function removeMessageBubble(messageId) {
    const element = document.getElementById(messageId);
    if (element) {
        element.remove();
    }
}

// Update message bubble content (for streaming)
function updateMessageBubble(messageId, content, isComplete = false) {
    const element = document.getElementById(messageId);
    if (!element) {
        console.warn('[updateMessageBubble] Element not found:', messageId);
        return;
    }

    if (isComplete) {
        // Final message - convert to normal assistant message with markdown rendering
        const renderedContent = window.marked ? window.marked.parse(content) : escapeHtml(content);
        element.innerHTML = `
            <div class="message-icon">🤖</div>
            <div class="message-content">${renderedContent}</div>
        `;
        const timestamp = document.createElement('div');
        timestamp.className = 'message-timestamp';
        timestamp.textContent = new Date().toLocaleTimeString();
        element.appendChild(timestamp);
    } else {
        // Streaming content - show with robot icon
        element.innerHTML = `
            <div class="message-icon">🤖</div>
            <div class="message-content" style="font-family: monospace; white-space: pre-wrap; font-size: 13px; color: #555;">${escapeHtml(content)}</div>
        `;
    }

    // Auto-scroll
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

// Format results for display
function formatResults(results) {
    if (typeof results === 'object') {
        return `<pre style="margin: 0; white-space: pre-wrap;">${JSON.stringify(results, null, 2)}</pre>`;
    }
    return escapeHtml(String(results));
}

/**
 * Formatter Registry - Maps data_type to formatter function
 *
 * HOW TO ADD A NEW FORMATTER:
 * 1. Create a formatter function: function formatYourType(message, data) { ... }
 * 2. Add entry here: 'your_type': formatYourType
 * 3. Update planner.py data_type list
 * 4. Sync changes to frontend/static/app.js
 *
 * NOTE: If data_type is not registered, formatGenericData will auto-render
 * arrays as tables and objects as key-value pairs.
 *
 * See: mcp_servers/DEVELOPMENT_GUIDE.md for full documentation
 */
const dataTypeFormatters = {
    'jira_issues': formatJiraIssues,
    'emails': formatEmails,
    'calendar_events': formatCalendarEvents,
    'news_articles': formatNewsArticles,
    'report': formatReport,
    'attendance': formatAttendanceSummary,
    'calculator': formatCalculatorResult,
    'weather': formatWeatherData,
    'generic': formatGenericData
};

// Format execution results (e.g., Jira issues, emails, calendar events, etc.)
function formatExecutionResults(message, data, dataType) {
    // 1. First, try data_type based routing (preferred)
    if (dataType && dataTypeFormatters[dataType]) {
        return dataTypeFormatters[dataType](message, data);
    }

    // 2. Fallback: field-based detection for backward compatibility
    // Jira issues
    if (data.issues && Array.isArray(data.issues)) {
        return formatJiraIssues(message, data);
    }

    // Email data
    if (data.emails && Array.isArray(data.emails)) {
        return formatEmails(message, data);
    }

    // Email search results
    if (data.results && Array.isArray(data.results) && data.results.length > 0 && data.results[0].subject) {
        return formatEmails(message, { emails: data.results, count: data.count });
    }

    // Calendar events
    if (data.events && Array.isArray(data.events)) {
        return formatCalendarEvents(message, data);
    }

    // Single calendar event
    if (data.event && data.event.title && data.event.start_time) {
        return formatCalendarEvents(message, { events: [data.event], count: 1 });
    }

    // News articles
    if (data.articles && Array.isArray(data.articles)) {
        return formatNewsArticles(message, data);
    }

    // Report content
    if (data.content && (data.format === 'markdown' || data.format === 'html' || data.format === 'text')) {
        return formatReport(message, data);
    }

    // Attendance summary
    if (data.summary && data.responses && Array.isArray(data.responses)) {
        return formatAttendanceSummary(message, data);
    }

    // Calculator result
    if (data.operation && data.result !== undefined) {
        return formatCalculatorResult(message, data);
    }

    // Single email
    if (data.email && data.email.subject) {
        return formatEmails(message, { emails: [data.email], count: 1 });
    }

    // Weather data
    if (data.current && (data.current.temperature !== undefined || data.current.temp !== undefined)) {
        return formatWeatherData(message, data);
    }

    // 3. Generic formatter for unknown data types
    return formatGenericData(message, data);
}

// Format Jira issues
function formatJiraIssues(message, data) {
    let html = `<div class="message-text">${escapeHtml(message)}</div>`;
    html += `<div class="data-container" style="margin-top: 15px;">`;
    html += `<div class="data-summary" style="margin-bottom: 10px; padding: 8px; background: #e3f2fd; border-radius: 4px;">`;
    html += `<strong>📋 Found ${data.count || data.issues.length} issue(s)</strong>`;
    html += `</div>`;

    data.issues.forEach((issue, index) => {
        html += `
            <div class="data-item" style="margin-bottom: 12px; padding: 12px; border-left: 4px solid #1976D2; border-radius: 4px; background: #fafafa;">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                    <div style="flex: 1;">
                        <strong style="color: #1976D2; font-size: 14px;">${escapeHtml(issue.key || `Issue ${index + 1}`)}</strong>
                        <span style="margin-left: 10px; padding: 2px 8px; background: ${getPriorityColor(issue.priority)}; color: white; border-radius: 3px; font-size: 11px;">
                            ${escapeHtml(issue.priority || 'N/A')}
                        </span>
                        <span style="margin-left: 5px; padding: 2px 8px; background: ${getStatusColor(issue.status)}; color: white; border-radius: 3px; font-size: 11px;">
                            ${escapeHtml(issue.status || 'N/A')}
                        </span>
                    </div>
                </div>
                <div style="margin-bottom: 6px; font-size: 13px; font-weight: 500;">
                    ${escapeHtml(issue.summary || 'No summary')}
                </div>
                <div style="margin-bottom: 6px; font-size: 12px; color: #666;">
                    ${escapeHtml(issue.description || 'No description')}
                </div>
                <div style="font-size: 11px; color: #999;">
                    ${issue.assignee ? `<span><strong>Assignee:</strong> ${escapeHtml(issue.assignee)}</span>` : ''}
                    ${issue.reporter ? `<span style="margin-left: 15px;"><strong>Reporter:</strong> ${escapeHtml(issue.reporter)}</span>` : ''}
                    ${issue.created_at ? `<span style="margin-left: 15px;"><strong>Created:</strong> ${formatDate(issue.created_at)}</span>` : ''}
                </div>
            </div>
        `;
    });

    html += `</div>`;
    return html;
}

// Format emails
function formatEmails(message, data) {
    let html = `<div class="message-text">${escapeHtml(message)}</div>`;
    html += `<div class="data-container" style="margin-top: 15px;">`;
    html += `<div class="data-summary" style="margin-bottom: 10px; padding: 8px; background: #fff3e0; border-radius: 4px;">`;
    html += `<strong>📧 Found ${data.count || data.emails.length} email(s)</strong>`;
    html += `</div>`;

    data.emails.forEach((email, index) => {
        const isUnread = email.read === false;
        html += `
            <div class="data-item" style="margin-bottom: 12px; padding: 12px; border-left: 4px solid ${isUnread ? '#f57c00' : '#9e9e9e'}; border-radius: 4px; background: ${isUnread ? '#fff8f0' : '#fafafa'};">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                    <div style="flex: 1;">
                        <strong style="color: #f57c00; font-size: 14px;">${escapeHtml(email.subject || 'No subject')}</strong>
                        ${isUnread ? '<span style="margin-left: 10px; padding: 2px 8px; background: #f57c00; color: white; border-radius: 3px; font-size: 11px;">UNREAD</span>' : ''}
                    </div>
                </div>
                <div style="margin-bottom: 6px; font-size: 12px;">
                    <strong>From:</strong> ${escapeHtml(email.from || 'Unknown')}
                    ${email.to ? ` <strong>To:</strong> ${escapeHtml(email.to)}` : ''}
                </div>
                <div style="margin-bottom: 6px; font-size: 12px; color: #666;">
                    ${escapeHtml(email.body || 'No content')}
                </div>
                <div style="font-size: 11px; color: #999;">
                    ${email.timestamp ? `<span><strong>Date:</strong> ${formatDate(email.timestamp)}</span>` : ''}
                    ${email.id ? `<span style="margin-left: 15px;"><strong>ID:</strong> ${escapeHtml(email.id)}</span>` : ''}
                </div>
            </div>
        `;
    });

    html += `</div>`;
    return html;
}

// Format calendar events
function formatCalendarEvents(message, data) {
    let html = `<div class="message-text">${escapeHtml(message)}</div>`;
    html += `<div class="data-container" style="margin-top: 15px;">`;
    html += `<div class="data-summary" style="margin-bottom: 10px; padding: 8px; background: #e8f5e9; border-radius: 4px;">`;
    html += `<strong>📅 Found ${data.count || data.events.length} event(s)</strong>`;
    html += `</div>`;

    data.events.forEach((event, index) => {
        html += `
            <div class="data-item" style="margin-bottom: 12px; padding: 12px; border-left: 4px solid #4caf50; border-radius: 4px; background: #fafafa;">
                <div style="margin-bottom: 8px;">
                    <strong style="color: #4caf50; font-size: 14px;">${escapeHtml(event.title || 'No title')}</strong>
                </div>
                <div style="margin-bottom: 6px; font-size: 12px; color: #666;">
                    ${escapeHtml(event.description || 'No description')}
                </div>
                <div style="margin-bottom: 6px; font-size: 12px;">
                    <strong>📍 Time:</strong> ${formatDate(event.start_time)} - ${formatDate(event.end_time)}
                </div>
                ${event.location ? `<div style="margin-bottom: 6px; font-size: 12px;"><strong>📌 Location:</strong> ${escapeHtml(event.location)}</div>` : ''}
                ${event.attendees && event.attendees.length > 0 ? `<div style="font-size: 11px; color: #999;"><strong>👥 Attendees:</strong> ${event.attendees.map(a => escapeHtml(a)).join(', ')}</div>` : ''}
            </div>
        `;
    });

    html += `</div>`;
    return html;
}

// Format news articles
function formatNewsArticles(message, data) {
    let html = `<div class="message-text">${escapeHtml(message)}</div>`;
    html += `<div class="data-container" style="margin-top: 15px;">`;
    html += `<div class="data-summary" style="margin-bottom: 10px; padding: 8px; background: #f3e5f5; border-radius: 4px;">`;
    html += `<strong>📰 Found ${data.count || data.articles.length} article(s)</strong>`;
    if (data.topic) {
        html += ` about "${escapeHtml(data.topic)}"`;
    }
    html += `</div>`;

    data.articles.forEach((article, index) => {
        html += `
            <div class="data-item" style="margin-bottom: 12px; padding: 12px; border-left: 4px solid #9c27b0; border-radius: 4px; background: #fafafa;">
                <div style="margin-bottom: 8px;">
                    <strong style="color: #9c27b0; font-size: 14px;">${escapeHtml(article.title || 'No title')}</strong>
                </div>
                <div style="margin-bottom: 6px; font-size: 12px; color: #666;">
                    ${escapeHtml(article.summary || 'No summary')}
                </div>
                <div style="font-size: 11px; color: #999;">
                    <strong>Source:</strong> ${escapeHtml(article.source || 'Unknown')}
                    ${article.date ? ` | <strong>Date:</strong> ${escapeHtml(article.date)}` : ''}
                    ${article.url ? ` | <a href="${escapeHtml(article.url)}" target="_blank" style="color: #9c27b0;">Read more</a>` : ''}
                </div>
            </div>
        `;
    });

    html += `</div>`;
    return html;
}

// Format report
function formatReport(message, data) {
    let html = `<div class="message-text">${escapeHtml(message)}</div>`;
    html += `<div class="data-container" style="margin-top: 15px;">`;
    html += `<div class="data-summary" style="margin-bottom: 10px; padding: 8px; background: #e0f2f1; border-radius: 4px;">`;
    html += `<strong>📄 Report Generated</strong>`;
    html += `</div>`;

    html += `<div class="data-item" style="padding: 12px; border-left: 4px solid #009688; border-radius: 4px; background: #fafafa;">`;

    if (data.format === 'markdown' || data.format === 'text') {
        html += `<pre style="white-space: pre-wrap; font-family: monospace; font-size: 12px; line-height: 1.6; margin: 0;">${escapeHtml(data.content)}</pre>`;
    } else if (data.format === 'html') {
        html += `<div style="font-size: 12px; line-height: 1.6;">${data.content}</div>`;
    }

    html += `</div></div>`;
    return html;
}

// Format attendance summary
function formatAttendanceSummary(message, data) {
    let html = `<div class="message-text">${escapeHtml(message)}</div>`;
    html += `<div class="data-container" style="margin-top: 15px;">`;
    html += `<div class="data-summary" style="margin-bottom: 10px; padding: 8px; background: #fce4ec; border-radius: 4px;">`;
    html += `<strong>👥 Attendance Summary for "${escapeHtml(data.event_name || 'Event')}"</strong>`;
    html += `</div>`;

    // Summary stats
    const summary = data.summary;
    html += `
        <div class="data-item" style="margin-bottom: 12px; padding: 12px; border-left: 4px solid #e91e63; border-radius: 4px; background: #fafafa;">
            <div style="display: flex; gap: 20px; margin-bottom: 10px;">
                <div><strong>✅ Attending:</strong> ${summary.attending}</div>
                <div><strong>❌ Not Attending:</strong> ${summary.not_attending}</div>
                <div><strong>❓ Maybe:</strong> ${summary.maybe}</div>
                <div><strong>📊 Total:</strong> ${summary.total_responses}</div>
            </div>
        </div>
    `;

    // Individual responses
    if (data.responses && data.responses.length > 0) {
        html += `<div style="margin-top: 10px; font-size: 12px;">`;
        html += `<strong>Individual Responses:</strong>`;
        html += `<ul style="margin: 5px 0; padding-left: 20px;">`;
        data.responses.forEach(response => {
            const statusIcon = response.status === 'attending' ? '✅' : response.status === 'not_attending' ? '❌' : '❓';
            html += `<li>${statusIcon} ${escapeHtml(response.attendee)} - ${escapeHtml(response.status)}</li>`;
        });
        html += `</ul></div>`;
    }

    html += `</div>`;
    return html;
}

// Format calculator result
function formatCalculatorResult(message, data) {
    let html = `<div class="message-text">${escapeHtml(message)}</div>`;
    html += `<div class="data-container" style="margin-top: 15px;">`;
    html += `<div class="data-item" style="padding: 12px; border-left: 4px solid #00bcd4; border-radius: 4px; background: #fafafa;">`;
    html += `<div style="font-size: 14px; margin-bottom: 8px;"><strong>🔢 Calculation Result</strong></div>`;
    html += `<div style="font-size: 16px; font-weight: 500; color: #00bcd4; margin-bottom: 8px;">`;
    html += `${escapeHtml(String(data.result))}`;
    html += `</div>`;
    html += `<div style="font-size: 12px; color: #666;">`;
    html += `<strong>Operation:</strong> ${escapeHtml(data.operation)}`;
    if (data.numbers) {
        html += ` | <strong>Numbers:</strong> ${data.numbers.join(', ')}`;
    } else if (data.base !== undefined && data.exponent !== undefined) {
        html += ` | <strong>Base:</strong> ${data.base} | <strong>Exponent:</strong> ${data.exponent}`;
    }
    html += `</div>`;
    html += `</div></div>`;
    return html;
}

// Format weather data
function formatWeatherData(message, data) {
    let html = `<div class="message-text">${escapeHtml(message)}</div>`;
    html += `<div class="data-container" style="margin-top: 15px;">`;

    // Location info
    if (data.location) {
        const loc = data.location;
        html += `<div style="margin-bottom: 10px; padding: 8px; background: #e3f2fd; border-radius: 4px;">`;
        html += `<strong>📍 ${escapeHtml(loc.name || loc.city || 'Unknown location')}</strong>`;
        if (loc.country) html += ` (${escapeHtml(loc.country)})`;
        html += `</div>`;
    }

    // Current weather
    if (data.current) {
        const current = data.current;
        const temp = current.temperature ?? current.temp ?? current.temp_c ?? 'N/A';
        const humidity = current.humidity ?? 'N/A';
        const condition = current.condition?.text || current.weather || current.description || '';
        const feelsLike = current.feels_like ?? current.feelslike_c ?? null;

        html += `<div class="data-item" style="padding: 15px; border-left: 4px solid #2196F3; border-radius: 4px; background: #fafafa;">`;
        html += `<div style="font-size: 24px; font-weight: bold; color: #1976D2;">🌡️ ${temp}°C</div>`;
        if (feelsLike !== null) {
            html += `<div style="color: #666; font-size: 13px;">체감 온도: ${feelsLike}°C</div>`;
        }
        if (condition) {
            html += `<div style="margin-top: 8px; color: #333;">${escapeHtml(condition)}</div>`;
        }
        html += `<div style="margin-top: 8px; color: #666;">💧 습도: ${humidity}%</div>`;
        if (current.wind_kph || current.wind_speed) {
            html += `<div style="color: #666;">💨 바람: ${current.wind_kph || current.wind_speed} km/h</div>`;
        }
        html += `</div>`;
    }

    html += `</div>`;
    return html;
}

function formatGenericData(message, data) {
    let html = `<div class="message-text">${escapeHtml(message)}</div>`;
    html += `<div style="margin-top: 10px;">`;

    // Try to render data intelligently based on structure
    const rendered = renderDataIntelligently(data);
    if (rendered) {
        html += rendered;
    } else {
        // Fallback to JSON view
        html += `<details style="cursor: pointer;">`;
        html += `<summary style="font-weight: 500; color: #1976D2; padding: 8px; background: #f5f5f5; border-radius: 4px;">📦 View detailed results</summary>`;
        html += `<pre style="margin: 10px 0 0 0; padding: 10px; background: #f5f5f5; border-radius: 4px; overflow-x: auto; font-size: 12px; line-height: 1.5;">${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
        html += `</details>`;
    }

    html += `</div>`;
    return html;
}

// Intelligently render data based on its structure
function renderDataIntelligently(data) {
    if (data === null || data === undefined) return null;

    // If it's a primitive, just show it
    if (typeof data !== 'object') {
        return `<div style="padding: 10px; background: #f5f5f5; border-radius: 4px;">${escapeHtml(String(data))}</div>`;
    }

    // Find array fields to render as table
    const arrayFields = Object.entries(data).filter(([_, v]) => Array.isArray(v) && v.length > 0);

    if (arrayFields.length > 0) {
        let html = '';

        // Show non-array fields first as summary
        const nonArrayFields = Object.entries(data).filter(([_, v]) => !Array.isArray(v));
        if (nonArrayFields.length > 0) {
            html += `<div style="margin-bottom: 10px; padding: 8px; background: #e8f5e9; border-radius: 4px;">`;
            nonArrayFields.forEach(([key, value]) => {
                if (value !== null && value !== undefined && typeof value !== 'object') {
                    html += `<span style="margin-right: 15px;"><strong>${escapeHtml(formatFieldName(key))}:</strong> ${escapeHtml(String(value))}</span>`;
                }
            });
            html += `</div>`;
        }

        // Render each array as a table
        arrayFields.forEach(([fieldName, items]) => {
            html += renderArrayAsTable(fieldName, items);
        });

        return html;
    }

    // If it's a flat object, render as key-value pairs
    const entries = Object.entries(data);
    if (entries.length > 0 && entries.every(([_, v]) => typeof v !== 'object' || v === null)) {
        let html = `<div style="padding: 10px; background: #f5f5f5; border-radius: 4px;">`;
        entries.forEach(([key, value]) => {
            html += `<div style="margin-bottom: 5px;"><strong>${escapeHtml(formatFieldName(key))}:</strong> ${escapeHtml(String(value ?? 'N/A'))}</div>`;
        });
        html += `</div>`;
        return html;
    }

    return null; // Fall back to JSON view
}

// Render array as HTML table
function renderArrayAsTable(fieldName, items) {
    if (!items || items.length === 0) return '';

    // Get all unique keys from items
    const allKeys = [...new Set(items.flatMap(item => Object.keys(item || {})))];
    // Filter out complex nested objects and limit columns
    const columns = allKeys.filter(key => {
        const sampleValue = items.find(i => i && i[key] !== undefined)?.[key];
        return typeof sampleValue !== 'object' || sampleValue === null;
    }).slice(0, 6); // Limit to 6 columns for readability

    if (columns.length === 0) return '';

    let html = `<div style="margin-bottom: 15px;">`;
    html += `<div style="font-weight: 500; margin-bottom: 8px; color: #1976D2;">📋 ${escapeHtml(formatFieldName(fieldName))} (${items.length})</div>`;
    html += `<div style="overflow-x: auto;">`;
    html += `<table style="width: 100%; border-collapse: collapse; font-size: 13px;">`;

    // Header
    html += `<thead><tr style="background: #e3f2fd;">`;
    columns.forEach(col => {
        html += `<th style="padding: 8px; text-align: left; border-bottom: 2px solid #1976D2;">${escapeHtml(formatFieldName(col))}</th>`;
    });
    html += `</tr></thead>`;

    // Body
    html += `<tbody>`;
    items.slice(0, 20).forEach((item, idx) => { // Limit to 20 rows
        html += `<tr style="background: ${idx % 2 === 0 ? '#fff' : '#f9f9f9'};">`;
        columns.forEach(col => {
            const value = item?.[col];
            let displayValue = value ?? '';
            // Format dates
            if (typeof displayValue === 'string' && displayValue.match(/^\d{4}-\d{2}-\d{2}T/)) {
                displayValue = formatDate(displayValue);
            }
            html += `<td style="padding: 8px; border-bottom: 1px solid #eee;">${escapeHtml(String(displayValue))}</td>`;
        });
        html += `</tr>`;
    });
    if (items.length > 20) {
        html += `<tr><td colspan="${columns.length}" style="padding: 8px; text-align: center; color: #666;">... and ${items.length - 20} more items</td></tr>`;
    }
    html += `</tbody></table></div></div>`;

    return html;
}

// Format field name for display (snake_case -> Title Case)
function formatFieldName(name) {
    return name
        .replace(/_/g, ' ')
        .replace(/([a-z])([A-Z])/g, '$1 $2')
        .replace(/\b\w/g, c => c.toUpperCase());
}

// Get priority color
function getPriorityColor(priority) {
    const colors = {
        'Critical': '#d32f2f',
        'High': '#f57c00',
        'Medium': '#fbc02d',
        'Low': '#388e3c'
    };
    return colors[priority] || '#757575';
}

// Get status color
function getStatusColor(status) {
    const colors = {
        'To Do': '#757575',
        'In Progress': '#1976D2',
        'Done': '#388e3c',
        'Blocked': '#d32f2f'
    };
    return colors[status] || '#757575';
}

// Format date
function formatDate(dateString) {
    try {
        const date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
        return dateString;
    }
}

// Add log entry
function addLogEntry(data) {
    const logsContent = document.getElementById('logsContent');

    // Clear placeholder text if this is the first log
    if (logsContent.querySelector('p')) {
        logsContent.innerHTML = '';
    }

    const logEntry = document.createElement('div');
    logEntry.className = `log-entry ${data.success ? 'log-success' : 'log-error'}`;

    const timestamp = new Date().toLocaleTimeString();
    let html = `
        <div class="log-header">
            <span class="log-status">${data.success ? '✓ Success' : '✗ Error'}</span>
            <span class="log-time">${timestamp}</span>
        </div>
    `;

    if (data.execution_time !== undefined && data.execution_time !== null) {
        html += `<div class="log-detail"><strong>Execution Time:</strong> ${Number(data.execution_time).toFixed(2)}s</div>`;
    }

    if (data.trace_id) {
        html += `<div class="log-detail"><strong>Trace ID:</strong> ${data.trace_id}</div>`;
    }

    if (data.plan_id) {
        html += `<div class="log-detail"><strong>Plan ID:</strong> ${data.plan_id}</div>`;
    }

    if (data.error) {
        html += `<div class="log-detail"><strong>Error:</strong> ${escapeHtml(data.error)}</div>`;
    }

    logEntry.innerHTML = html;
    logsContent.appendChild(logEntry);
}

// Clear execution logs
function clearExecutionLogs() {
    const logsContent = document.getElementById('logsContent');
    logsContent.innerHTML = '<div class="execution-logs-header">Execution Logs (Real-time)</div>';
}

// Add execution log entry (real-time SSE logs)
function addExecutionLogEntry(eventData) {
    const logsContent = document.getElementById('logsContent');

    // Create log entry element
    const logEntry = document.createElement('div');
    logEntry.className = 'execution-log-entry';

    // Get event type icon and color
    const eventInfo = getEventTypeInfo(eventData.event_type);

    // Format timestamp
    const timestamp = new Date(eventData.timestamp).toLocaleTimeString();

    // Build log entry HTML
    let html = `
        <div class="execution-log-header" style="color: ${eventInfo.color};">
            <span class="execution-log-icon">${eventInfo.icon}</span>
            <span class="execution-log-type">${eventInfo.label}</span>
            <span class="execution-log-time">${timestamp}</span>
        </div>
    `;

    if (eventData.message) {
        html += `<div class="execution-log-message">${escapeHtml(eventData.message)}</div>`;
    }

    // Add specific data based on event type
    if (eventData.data) {
        if (eventData.event_type === 'plan_created' && eventData.data.steps) {
            html += `<div class="execution-log-details">`;
            html += `<div class="execution-log-detail"><strong>Plan ID:</strong> ${eventData.data.plan_id}</div>`;
            html += `<div class="execution-log-detail"><strong>Steps:</strong></div>`;
            html += `<ul style="margin: 5px 0; padding-left: 20px;">`;
            eventData.data.steps.forEach((step, index) => {
                html += `<li>${step.description} (${step.tool_name})</li>`;
            });
            html += `</ul>`;
            html += `</div>`;
        } else if (eventData.event_type === 'plan_updated') {
            // Show progress in log
            if (eventData.data.progress) {
                html += `<div class="execution-log-details">`;
                html += `<div class="execution-log-detail"><strong>Progress:</strong> ${eventData.data.progress.completed}/${eventData.data.progress.total} tasks completed</div>`;
                html += `</div>`;
            }
        } else if (eventData.event_type === 'step_started') {
            html += `<div class="execution-log-details">`;
            html += `<div class="execution-log-detail"><strong>Tool:</strong> ${eventData.data.tool_name}</div>`;
            if (eventData.data.tool_input && Object.keys(eventData.data.tool_input).length > 0) {
                html += `<div class="execution-log-detail"><strong>Arguments:</strong> <pre style="margin: 5px 0; white-space: pre-wrap; font-size: 11px;">${JSON.stringify(eventData.data.tool_input, null, 2)}</pre></div>`;
            }
            html += `</div>`;
        } else if (eventData.event_type === 'step_completed') {
            html += `<div class="execution-log-details">`;
            if (eventData.data.duration !== undefined && eventData.data.duration !== null) {
                html += `<div class="execution-log-detail"><strong>Duration:</strong> ${Number(eventData.data.duration).toFixed(2)}ms</div>`;
            }
            if (eventData.data.output) {
                html += `<div class="execution-log-detail"><strong>Output:</strong> <pre style="margin: 5px 0; white-space: pre-wrap; font-size: 11px;">${JSON.stringify(eventData.data.output, null, 2).substring(0, 200)}${JSON.stringify(eventData.data.output, null, 2).length > 200 ? '...' : ''}</pre></div>`;
            }
            html += `</div>`;
        } else if (eventData.event_type === 'step_failed') {
            html += `<div class="execution-log-details">`;
            html += `<div class="execution-log-detail" style="color: #f44336;"><strong>Error:</strong> ${escapeHtml(eventData.data.error)}</div>`;
            if (eventData.data.duration !== undefined && eventData.data.duration !== null) {
                html += `<div class="execution-log-detail"><strong>Duration:</strong> ${Number(eventData.data.duration).toFixed(2)}ms</div>`;
            }
            html += `</div>`;
        } else if (eventData.event_type === 'decision_made') {
            html += `<div class="execution-log-details">`;
            html += `<div class="execution-log-detail"><strong>Decision:</strong> ${eventData.data.decision_type}</div>`;
            html += `<div class="execution-log-detail"><strong>Next Action:</strong> ${eventData.data.next_action}</div>`;
            html += `</div>`;
        } else if (eventData.event_type === 'node_entered' || eventData.event_type === 'node_exited') {
            html += `<div class="execution-log-details">`;
            html += `<div class="execution-log-detail"><strong>Node:</strong> ${eventData.data.node_name}</div>`;
            html += `</div>`;
        }
    }

    logEntry.innerHTML = html;
    logsContent.appendChild(logEntry);

    // Auto-scroll to bottom
    logsContent.scrollTop = logsContent.scrollHeight;
}

// Get event type info (icon, color, label)
function getEventTypeInfo(eventType) {
    const eventTypes = {
        'execution_started': { icon: '🚀', color: '#2196F3', label: 'Execution Started' },
        'plan_created': { icon: '📋', color: '#4CAF50', label: 'Plan Created' },
        'plan_updated': { icon: '🔄', color: '#2196F3', label: 'Plan Updated' },
        'step_started': { icon: '▶️', color: '#FF9800', label: 'Step Started' },
        'step_completed': { icon: '✅', color: '#4CAF50', label: 'Step Completed' },
        'step_failed': { icon: '❌', color: '#f44336', label: 'Step Failed' },
        'decision_made': { icon: '🤔', color: '#9C27B0', label: 'Decision Made' },
        'node_entered': { icon: '📥', color: '#00BCD4', label: 'Node Entered' },
        'node_exited': { icon: '📤', color: '#00BCD4', label: 'Node Exited' },
        'execution_completed': { icon: '🎉', color: '#4CAF50', label: 'Execution Completed' },
        'execution_error': { icon: '⚠️', color: '#f44336', label: 'Execution Error' }
    };

    return eventTypes[eventType] || { icon: '📄', color: '#757575', label: eventType };
}

// Toggle logs section - removed (logs now always visible in right panel)

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Load current settings (now shows all configurations as cards)
async function loadCurrentSettings() {
    const container = document.getElementById('configsList');
    container.innerHTML = '<div class="loading">Loading configurations...</div>';

    try {
        const response = await fetch('/api/settings?user_id=test_user&tenant=test_tenant');
        const data = await response.json();

        if (response.ok) {
            if (data.has_settings && data.configs && data.configs.length > 0) {
                let html = '';

                data.configs.forEach(config => {
                    const isActive = config.is_active;
                    const activeClass = isActive ? 'config-active' : '';

                    html += `
                        <div class="config-card ${activeClass}">
                            <div class="config-card-header">
                                <div>
                                    <h4 class="config-card-title">
                                        ${escapeHtml(config.config_name)}
                                        ${isActive ? '<span class="status-badge active">Active</span>' : ''}
                                    </h4>
                                    <div class="config-card-details">
                                        <strong>${config.provider}</strong> · ${config.model}
                                        ${config.base_url ? ` · ${config.base_url}` : ''}
                                    </div>
                                    <div class="config-card-meta">
                                        API Key: ${config.api_key_masked} · Max Retries: ${config.max_retries} · Timeout: ${config.timeout}ms
                                    </div>
                                </div>
                            </div>
                            <div class="config-card-actions">
                                <button onclick="editConfig('${escapeHtml(config.config_name)}')" class="btn btn-sm btn-secondary">
                                    Edit
                                </button>
                                ${!isActive ? `
                                    <button onclick="activateConfig('${escapeHtml(config.config_name)}')" class="btn btn-sm btn-primary">
                                        Activate
                                    </button>
                                ` : ''}
                                <button onclick="deleteConfig('${escapeHtml(config.config_name)}')" class="btn btn-sm btn-danger">
                                    Delete
                                </button>
                            </div>
                        </div>
                    `;
                });

                container.innerHTML = html;
            } else {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-title">No configurations yet</div>
                        <div class="empty-state-description">Click "Add New" to create your first configuration.</div>
                    </div>
                `;
            }
        } else {
            container.innerHTML = '<div class="result-error">Failed to load configurations</div>';
        }
    } catch (error) {
        container.innerHTML = '<div class="result-error">Network error</div>';
    }
}

// Show add configuration form
function showAddConfigForm() {
    const formCard = document.getElementById('configFormCard');
    const formTitle = document.getElementById('formTitle');
    const editingConfigName = document.getElementById('editingConfigName');

    // Clear form
    document.getElementById('configName').value = '';
    document.getElementById('configName').disabled = false;
    document.getElementById('llmProvider').value = 'anthropic';
    document.getElementById('apiKey').value = '';
    document.getElementById('baseUrl').value = '';
    document.getElementById('maxRetries').value = '3';
    document.getElementById('timeout').value = '30000';
    document.getElementById('setAsActive').checked = false;
    updateModelOptions();

    // Clear editing state
    editingConfigName.value = '';
    formTitle.textContent = 'Add New Configuration';

    // Show form
    formCard.style.display = 'block';
    formCard.scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Clear any previous messages
    document.getElementById('settingsResult').innerHTML = '';
}

// Cancel configuration form
function cancelConfigForm() {
    const formCard = document.getElementById('configFormCard');
    formCard.style.display = 'none';
    document.getElementById('settingsResult').innerHTML = '';
}

// Edit existing configuration
async function editConfig(configName) {
    const formCard = document.getElementById('configFormCard');
    const formTitle = document.getElementById('formTitle');
    const editingConfigName = document.getElementById('editingConfigName');

    try {
        // Load all settings
        const response = await fetch('/api/settings?user_id=test_user&tenant=test_tenant');
        const data = await response.json();

        if (response.ok && data.configs) {
            const config = data.configs.find(c => c.config_name === configName);

            if (config) {
                // Populate form with existing values
                document.getElementById('configName').value = config.config_name;
                document.getElementById('configName').disabled = true;  // Don't allow renaming
                document.getElementById('llmProvider').value = config.provider;
                updateModelOptions();
                document.getElementById('llmModel').value = config.model;
                document.getElementById('baseUrl').value = config.base_url || '';
                document.getElementById('maxRetries').value = config.max_retries;
                document.getElementById('timeout').value = config.timeout;
                document.getElementById('setAsActive').checked = config.is_active;

                // Note: API key is not populated (security)
                document.getElementById('apiKey').value = '';
                document.getElementById('apiKey').placeholder = 'Enter new API key (leave empty to keep existing)';

                // Set editing state
                editingConfigName.value = configName;
                formTitle.textContent = `Edit Configuration: ${configName}`;

                // Show form
                formCard.style.display = 'block';
                formCard.scrollIntoView({ behavior: 'smooth', block: 'start' });

                // Clear any previous messages
                document.getElementById('settingsResult').innerHTML = '';
            }
        }
    } catch (error) {
        alert('Failed to load configuration for editing');
    }
}

// Activate a configuration
async function activateConfig(configName) {
    if (!confirm(`Activate configuration "${configName}"?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/settings/${encodeURIComponent(configName)}/activate?user_id=test_user&tenant=test_tenant`, {
            method: 'POST'
        });

        const data = await response.json();

        if (response.ok && data.success) {
            // Reload configurations list
            await loadCurrentSettings();
            alert(data.message || `Configuration "${configName}" activated successfully`);
        } else {
            alert(`Failed to activate: ${data.message || data.detail || 'Unknown error'}`);
        }
    } catch (error) {
        alert(`Network error: ${error.message}`);
    }
}

// Delete a configuration
async function deleteConfig(configName) {
    if (!confirm(`Are you sure you want to delete configuration "${configName}"?\n\nThis action cannot be undone.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/settings/${encodeURIComponent(configName)}?user_id=test_user&tenant=test_tenant`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (response.ok && data.success) {
            // Reload configurations list
            await loadCurrentSettings();
            alert(data.message || `Configuration "${configName}" deleted successfully`);
        } else {
            alert(`Failed to delete: ${data.message || data.detail || 'Unknown error'}`);
        }
    } catch (error) {
        alert(`Network error: ${error.message}`);
    }
}

// Test connection
async function testConnection() {
    const provider = document.getElementById('llmProvider').value;
    const apiKey = document.getElementById('apiKey').value;
    const model = document.getElementById('llmModel').value;
    const baseUrl = document.getElementById('baseUrl').value;
    const testBtn = document.getElementById('testBtn');
    const resultDiv = document.getElementById('settingsResult');

    if (!apiKey) {
        resultDiv.innerHTML = '<div class="result-error">Please enter an API key</div>';
        return;
    }

    testBtn.disabled = true;
    testBtn.textContent = 'Testing...';
    resultDiv.innerHTML = '<div class="loading">Testing connection...</div>';

    try {
        const response = await fetch('/api/settings/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                provider: provider,
                api_key: apiKey,
                model: model,
                base_url: baseUrl || null
            })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            resultDiv.innerHTML = `
                <div class="result-success">
                    <div class="result-label">Connection successful</div>
                    <div class="result-value">${data.message}</div>
                </div>
            `;
        } else {
            resultDiv.innerHTML = `
                <div class="result-error">
                    <div class="result-label">Connection failed</div>
                    <div class="result-value">${data.message || data.detail || 'Unknown error'}</div>
                </div>
            `;
        }
    } catch (error) {
        resultDiv.innerHTML = `
            <div class="result-error">
                <div class="result-label">Network error</div>
                <div class="result-value">${error.message}</div>
            </div>
        `;
    } finally {
        testBtn.disabled = false;
        testBtn.textContent = 'Test Connection';
    }
}

// Save settings
async function saveSettings() {
    const configName = document.getElementById('configName').value.trim();
    const provider = document.getElementById('llmProvider').value;
    const apiKey = document.getElementById('apiKey').value;
    const model = document.getElementById('llmModel').value;
    const baseUrl = document.getElementById('baseUrl').value;
    const maxRetries = parseInt(document.getElementById('maxRetries').value) || 3;
    const timeout = parseInt(document.getElementById('timeout').value) || 30000;
    const isActive = document.getElementById('setAsActive').checked;
    const editingConfigName = document.getElementById('editingConfigName').value;
    const saveBtn = document.getElementById('saveBtn');
    const resultDiv = document.getElementById('settingsResult');

    // Validation
    if (!configName) {
        resultDiv.innerHTML = '<div class="result-error">Please enter a configuration name</div>';
        return;
    }

    // When editing, API key is optional (keep existing if empty)
    // When adding new, API key is required
    if (!editingConfigName && !apiKey) {
        resultDiv.innerHTML = '<div class="result-error">Please enter an API key</div>';
        return;
    }

    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';
    resultDiv.innerHTML = '<div class="loading">Saving configuration...</div>';

    try {
        // When editing and API key is empty, fetch existing settings to get the current API key
        let finalApiKey = apiKey;

        if (editingConfigName && !apiKey) {
            // Fetch existing configuration to get API key
            const existingResponse = await fetch('/api/settings?user_id=test_user&tenant=test_tenant');
            const existingData = await existingResponse.json();

            if (existingResponse.ok && existingData.configs) {
                const existingConfig = existingData.configs.find(c => c.config_name === editingConfigName);
                if (existingConfig) {
                    // Use a placeholder that backend will recognize to keep existing key
                    // Actually, we need to handle this differently - skip API key in request
                    resultDiv.innerHTML = '<div class="result-error">Please re-enter API key when editing (security requirement)</div>';
                    saveBtn.disabled = false;
                    saveBtn.textContent = '💾 Save Configuration';
                    return;
                }
            }
        }

        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                config_name: configName,
                provider: provider,
                api_key: finalApiKey,
                model: model,
                base_url: baseUrl || null,
                max_retries: maxRetries,
                timeout: timeout,
                is_active: isActive,
                user_id: 'test_user',
                tenant: 'test_tenant'
            })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            resultDiv.innerHTML = `
                <div class="result-success">
                    <div class="result-label">Configuration saved successfully</div>
                    <div class="result-value">${data.message}</div>
                </div>
            `;

            // Reload configurations list and hide form
            setTimeout(() => {
                loadCurrentSettings();
                cancelConfigForm();
            }, 1000);
        } else {
            resultDiv.innerHTML = `
                <div class="result-error">
                    <div class="result-label">Failed to save configuration</div>
                    <div class="result-value">${data.message || data.detail || 'Unknown error'}</div>
                </div>
            `;
        }
    } catch (error) {
        resultDiv.innerHTML = `
            <div class="result-error">
                <div class="result-label">Network error</div>
                <div class="result-value">${error.message}</div>
            </div>
        `;
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save';
    }
}

// Update MCP transport fields visibility
function updateMCPTransportFields() {
    const transport = document.getElementById('mcpTransport').value;
    const urlGroup = document.getElementById('mcpUrlGroup');
    const headersGroup = document.getElementById('mcpHeadersGroup');
    const commandGroup = document.getElementById('mcpCommandGroup');
    const argsGroup = document.getElementById('mcpArgsGroup');

    if (transport === 'streamable-http' || transport === 'sse' || transport === 'http') {
        // HTTP-based transports: show URL and headers
        urlGroup.style.display = 'block';
        headersGroup.style.display = 'block';
        commandGroup.style.display = 'none';
        argsGroup.style.display = 'none';
    } else {
        // STDIO transport: show command and args, hide URL and headers
        urlGroup.style.display = 'none';
        headersGroup.style.display = 'none';
        commandGroup.style.display = 'block';
        argsGroup.style.display = 'block';
    }
}

// Show add MCP server form
function showAddMCPServerForm() {
    const formCard = document.getElementById('mcpFormCard');
    const formTitle = document.getElementById('mcpFormTitle');

    // Clear form
    document.getElementById('mcpServerName').value = '';
    document.getElementById('mcpEnabled').value = 'true';
    document.getElementById('mcpTransport').value = 'streamable-http';
    document.getElementById('mcpUrl').value = '';
    document.getElementById('mcpHeaders').value = '';
    document.getElementById('mcpCommand').value = 'fastmcp';
    document.getElementById('mcpArgs').value = '';
    document.getElementById('mcpEnvVars').value = '';

    updateMCPTransportFields();

    formTitle.textContent = 'Add MCP Server';
    formCard.style.display = 'block';
    formCard.scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Clear any previous messages
    document.getElementById('mcpResult').innerHTML = '';
}

// Cancel MCP form
function cancelMCPForm() {
    const formCard = document.getElementById('mcpFormCard');
    formCard.style.display = 'none';
    document.getElementById('mcpResult').innerHTML = '';
}

// Load MCP servers with status
async function loadMCPServers() {
    const container = document.getElementById('currentMCPServers');
    container.innerHTML = '<div class="loading">Loading MCP servers...</div>';

    try {
        // Fetch servers with status information
        const response = await fetch('/api/mcp-servers/status?user_id=test_user&tenant=test_tenant');
        const data = await response.json();

        if (response.ok) {
            let html = '';

            if (data.servers && data.servers.length > 0) {
                // Summary bar - Claude minimal style
                html = `
                    <div class="summary-bar">
                        <span><strong>${data.enabled_servers}/${data.total_servers}</strong> servers active</span>
                        <span>${data.total_tools} tools connected</span>
                    </div>
                `;

                html += '<div class="mcp-servers-list">';
                data.servers.forEach(server => {
                    const transport = server.transport || 'stdio';
                    const isHttpTransport = transport === 'http' || transport === 'streamable-http' || transport === 'sse';
                    const hasHeaders = server.headers && Object.keys(server.headers).length > 0;

                    // Transport display name
                    const transportDisplay = {
                        'streamable-http': 'Streamable HTTP',
                        'sse': 'SSE',
                        'http': 'HTTP',
                        'stdio': 'STDIO'
                    }[transport] || transport.toUpperCase();

                    // Status class based on connection status
                    let statusClass, statusText;
                    if (!server.enabled) {
                        statusClass = 'server-disabled';
                        statusText = 'Disabled';
                    } else if (server.status === 'connected') {
                        statusClass = 'server-connected';
                        statusText = `Connected (${server.tool_count} tools)`;
                    } else {
                        statusClass = 'server-disconnected';
                        statusText = 'Not connected';
                    }

                    html += `
                        <div class="mcp-server-card ${statusClass}">
                            <div class="mcp-server-header">
                                <div>
                                    <span class="mcp-server-name">${escapeHtml(server.server_name)}</span>
                                    <span class="status-badge ${server.enabled && server.status === 'connected' ? 'active' : 'inactive'}">
                                        ${statusText}
                                    </span>
                                </div>
                                <div class="mcp-server-actions">
                                    <button onclick="toggleMCPServer('${escapeHtml(server.server_name)}')" class="btn btn-sm btn-secondary">
                                        ${server.enabled ? 'Disable' : 'Enable'}
                                    </button>
                                    <button onclick="editMCPServer('${escapeHtml(server.server_name)}')" class="btn btn-sm btn-secondary">
                                        Edit
                                    </button>
                                    <button onclick="deleteMCPServer('${escapeHtml(server.server_name)}')" class="btn btn-sm btn-danger">
                                        Delete
                                    </button>
                                </div>
                            </div>
                            <div class="mcp-server-details">
                                <div>
                                    <strong>Transport:</strong> ${transportDisplay}
                                    ${hasHeaders ? '<span class="badge-small">🔑 Headers</span>' : ''}
                                </div>
                                ${isHttpTransport
                                    ? `<div><strong>URL:</strong> <code>${escapeHtml(server.url || 'N/A')}</code></div>`
                                    : `<div><strong>Command:</strong> <code>${escapeHtml(server.command || 'N/A')}</code></div>`
                                }
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
            } else {
                html = `
                    <div class="empty-state">
                        <div class="empty-state-title">No registered servers</div>
                        <div class="empty-state-description">Click "Add Server" to register a new MCP server.</div>
                    </div>
                `;
            }

            container.innerHTML = html;
        } else {
            container.innerHTML = '<div class="result-error">Failed to load MCP servers.</div>';
        }
    } catch (error) {
        container.innerHTML = '<div class="result-error">Network error occurred.</div>';
    }
}

// Toggle MCP server enabled/disabled
async function toggleMCPServer(serverName) {
    try {
        const response = await fetch(`/api/mcp-servers/${encodeURIComponent(serverName)}/toggle?user_id=test_user&tenant=test_tenant`, {
            method: 'POST'
        });

        const data = await response.json();

        if (response.ok && data.success) {
            // Reload servers list
            await loadMCPServers();
        } else {
            alert(`Failed to toggle server: ${data.message || data.detail || 'Unknown error'}`);
        }
    } catch (error) {
        alert(`Network error: ${error.message}`);
    }
}

// Sync MCP servers - re-discover tools
async function syncMCPServers() {
    const syncBtn = document.getElementById('syncMCPBtn');

    if (syncBtn) {
        syncBtn.disabled = true;
        syncBtn.textContent = 'Syncing...';
    }

    try {
        const response = await fetch('/api/mcp-servers/sync?user_id=test_user&tenant=test_tenant', {
            method: 'POST'
        });

        const data = await response.json();

        if (response.ok && data.success) {
            alert(`Sync complete: ${data.tools_count} tools discovered from ${data.servers_synced} servers.`);
            // Reload both servers and tools
            await loadMCPServers();
            await loadMCPTools();
        } else {
            alert(`Sync failed: ${data.message || data.detail || 'Unknown error'}`);
        }
    } catch (error) {
        alert(`Network error: ${error.message}`);
    } finally {
        if (syncBtn) {
            syncBtn.disabled = false;
            syncBtn.textContent = 'Sync Servers';
        }
    }
}

// Edit MCP server
async function editMCPServer(serverName) {
    try {
        const response = await fetch('/api/mcp-servers?user_id=test_user&tenant=test_tenant');
        const data = await response.json();

        if (response.ok && data.servers) {
            const server = data.servers.find(s => s.server_name === serverName);
            if (server) {
                const formCard = document.getElementById('mcpFormCard');
                const formTitle = document.getElementById('mcpFormTitle');

                document.getElementById('mcpServerName').value = server.server_name;
                document.getElementById('mcpEnabled').value = server.enabled ? 'true' : 'false';
                document.getElementById('mcpTransport').value = server.transport || 'streamable-http';
                document.getElementById('mcpUrl').value = server.url || '';
                document.getElementById('mcpHeaders').value = server.headers ? JSON.stringify(server.headers, null, 2) : '';
                document.getElementById('mcpCommand').value = server.command || 'fastmcp';
                document.getElementById('mcpArgs').value = server.args ? JSON.stringify(server.args) : '';
                document.getElementById('mcpEnvVars').value = server.env_vars ? JSON.stringify(server.env_vars) : '';

                updateMCPTransportFields();

                formTitle.textContent = `Edit MCP Server: ${serverName}`;
                formCard.style.display = 'block';
                formCard.scrollIntoView({ behavior: 'smooth', block: 'start' });

                document.getElementById('mcpResult').innerHTML = '';
            }
        }
    } catch (error) {
        alert('Failed to load server info: ' + error.message);
    }
}

// Save MCP server
async function saveMCPServer() {
    const serverName = document.getElementById('mcpServerName').value;
    const enabled = document.getElementById('mcpEnabled').value === 'true';
    const transport = document.getElementById('mcpTransport').value;
    const url = document.getElementById('mcpUrl').value;
    const headersText = document.getElementById('mcpHeaders').value;
    const command = document.getElementById('mcpCommand').value;
    const argsText = document.getElementById('mcpArgs').value;
    const envVarsText = document.getElementById('mcpEnvVars').value;
    const saveBtn = document.getElementById('saveMCPBtn');
    const resultDiv = document.getElementById('mcpResult');

    if (!serverName) {
        resultDiv.innerHTML = '<div class="result-error">Please enter a server name</div>';
        return;
    }

    // Validate based on transport type
    const isHttpTransport = transport === 'http' || transport === 'streamable-http' || transport === 'sse';

    if (isHttpTransport && !url) {
        resultDiv.innerHTML = '<div class="result-error">Please enter a server URL for HTTP/SSE transport</div>';
        return;
    }

    if (transport === 'stdio' && !command) {
        resultDiv.innerHTML = '<div class="result-error">Please enter a command for STDIO transport</div>';
        return;
    }

    // Parse JSON
    let args = [];
    let envVars = null;
    let headers = null;

    try {
        if (argsText) {
            args = JSON.parse(argsText);
        }
        if (envVarsText) {
            envVars = JSON.parse(envVarsText);
        }
        if (headersText) {
            headers = JSON.parse(headersText);
        }
    } catch (e) {
        resultDiv.innerHTML = '<div class="result-error">Invalid JSON in arguments, headers, or environment variables</div>';
        return;
    }

    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';
    resultDiv.innerHTML = '<div class="loading">Saving MCP server...</div>';

    try {
        const requestBody = {
            server_name: serverName,
            enabled: enabled,
            transport: transport,
            user_id: 'test_user',
            tenant: 'test_tenant'
        };

        // Add transport-specific fields
        if (isHttpTransport) {
            requestBody.url = url;
            if (headers) {
                requestBody.headers = headers;
            }
        } else {
            requestBody.command = command;
            requestBody.args = args;
        }

        // Add optional env vars
        if (envVars) {
            requestBody.env_vars = envVars;
        }

        const response = await fetch('/api/mcp-servers', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });

        const data = await response.json();

        if (response.ok && data.success) {
            resultDiv.innerHTML = `
                <div class="result-success">
                    <div class="result-label">MCP server saved successfully</div>
                    <div class="result-value">${data.message}</div>
                </div>
            `;

            // Clear form and hide
            setTimeout(() => {
                cancelMCPForm();
                loadMCPServers();
                loadMCPTools();
            }, 500);
        } else {
            resultDiv.innerHTML = `
                <div class="result-error">
                    <div class="result-label">Failed to save MCP server</div>
                    <div class="result-value">${data.message || data.detail || 'Unknown error'}</div>
                </div>
            `;
        }
    } catch (error) {
        resultDiv.innerHTML = `
            <div class="result-error">
                <div class="result-label">Network error</div>
                <div class="result-value">${error.message}</div>
            </div>
        `;
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save';
    }
}

// Delete MCP server
async function deleteMCPServer(serverName) {
    if (!confirm(`Are you sure you want to delete the MCP server "${serverName}"?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/mcp-servers/${serverName}?user_id=test_user&tenant=test_tenant`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (response.ok && data.success) {
            loadMCPServers();
        } else {
            alert(`Failed to delete MCP server: ${data.message || data.detail || 'Unknown error'}`);
        }
    } catch (error) {
        alert(`Network error: ${error.message}`);
    }
}

// Load MCP tools
async function loadMCPTools() {
    const container = document.getElementById('mcpToolsList');
    const loadBtn = document.getElementById('loadToolsBtn');

    container.innerHTML = '<div class="loading">Loading tools...</div>';
    if (loadBtn) {
        loadBtn.disabled = true;
        loadBtn.textContent = 'Loading...';
    }

    try {
        // Fetch tools and servers in parallel
        const [toolsResponse, serversResponse] = await Promise.all([
            fetch('/api/tools'),
            fetch('/api/mcp-servers?user_id=test_user&tenant=test_tenant')
        ]);
        const data = await toolsResponse.json();
        const serversData = await serversResponse.json();

        // Get actual server count from MCP servers API
        const actualServerCount = (serversData.servers && serversData.servers.length) || 0;

        if (toolsResponse.ok) {
            let html = '';

            if (data.tools && data.tools.length > 0) {
                // Summary bar - Claude minimal style
                html = `
                    <div class="summary-bar">
                        <span><strong>${data.count}</strong> tools registered</span>
                        <span>${actualServerCount} servers</span>
                    </div>
                    <div class="tools-list">
                `;

                data.tools.forEach((tool, index) => {
                    // Format input schema for display
                    let paramsHtml = '';
                    if (tool.input_schema && tool.input_schema.properties) {
                        const properties = tool.input_schema.properties;
                        const required = tool.input_schema.required || [];
                        const paramCount = Object.keys(properties).length;

                        paramsHtml = `<div class="tool-card-params">`;
                        paramsHtml += `<div class="tool-card-params-label">Parameters (${paramCount})</div>`;
                        paramsHtml += `<div class="tool-card-params-list">`;

                        for (const [propName, propDetails] of Object.entries(properties)) {
                            const isRequired = required.includes(propName);
                            paramsHtml += `
                                <span class="param-tag ${isRequired ? 'required' : ''}">
                                    ${propName}${isRequired ? '*' : ''}
                                </span>
                            `;
                        }

                        paramsHtml += `</div></div>`;
                    }

                    html += `
                        <div class="tool-card">
                            <div class="tool-card-header">
                                <span class="tool-card-number">${index + 1}</span>
                                <span class="tool-card-name">${escapeHtml(tool.name)}</span>
                            </div>
                            <div class="tool-card-description">
                                ${escapeHtml(tool.description || 'No description')}
                            </div>
                            ${paramsHtml}
                        </div>
                    `;
                });

                html += '</div>';
            } else {
                html = `
                    <div class="empty-state">
                        <div class="empty-state-title">No tools available</div>
                        <div class="empty-state-description">Register MCP servers to see available tools.</div>
                    </div>
                `;
            }

            container.innerHTML = html;
        } else {
            container.innerHTML = `<div class="result-error">Failed to load tools: ${data.detail || 'Unknown error'}</div>`;
        }
    } catch (error) {
        container.innerHTML = `<div class="result-error">Network error: ${error.message}</div>`;
    } finally {
        if (loadBtn) {
            loadBtn.disabled = false;
            loadBtn.textContent = 'Refresh';
        }
    }
}

// Expose functions to global scope for inline onclick handlers (ES modules)

// Show planning indicator in chat
function showPlanningIndicator() {
    const planMessageId = 'plan-message';
    const chatMessages = document.getElementById('chatMessages');

    // Remove existing plan message if any
    const existingMessage = document.getElementById(planMessageId);
    if (existingMessage) {
        existingMessage.remove();
    }

    const messageDiv = document.createElement('div');
    messageDiv.id = planMessageId;
    messageDiv.className = 'message-bubble assistant-message plan-message planning-indicator';

    messageDiv.innerHTML = `
        <div class="message-icon">📋</div>
        <div class="message-content">
            <div class="planning-indicator-container">
                <div class="planning-spinner"></div>
                <div class="planning-text">
                    <strong>플래닝 중...</strong>
                    <p>실행 계획을 수립하고 있습니다.</p>
                </div>
            </div>
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Update or add plan message in chat
function updatePlanMessageInChat(planData) {
    const planMessageId = 'plan-message';
    const existingMessage = document.getElementById(planMessageId);

    const planHtml = renderPlanMarkdown(planData);
    const messageContent = `
        <div class="plan-message-container">
            ${planHtml}
        </div>
    `;

    if (existingMessage) {
        // Update existing plan message (replace planning indicator or update plan)
        const contentDiv = existingMessage.querySelector('.message-content');
        if (contentDiv) {
            contentDiv.innerHTML = messageContent;
        }
        // Remove planning indicator class if it exists
        existingMessage.classList.remove('planning-indicator');
    } else {
        // Add new plan message
        const chatMessages = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        messageDiv.id = planMessageId;
        messageDiv.className = 'message-bubble assistant-message plan-message';

        messageDiv.innerHTML = `
            <div class="message-icon">📋</div>
            <div class="message-content">${messageContent}</div>
        `;

        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

function renderPlanMarkdown(planData) {
    let html = '';

    // Request section
    if (planData.request) {
        html += `<h2>Request</h2>`;
        html += `<p>${escapeHtml(planData.request)}</p>`;
    }

    // Analysis section
    if (planData.analysis) {
        html += `<h2>Analysis</h2>`;
        html += `<p>${escapeHtml(planData.analysis)}</p>`;
    }

    // Task Breakdown section
    if (planData.tasks && planData.tasks.length > 0) {
        html += `<h2>Task Breakdown</h2>`;

        planData.tasks.forEach((task, index) => {
            const status = task.status || 'pending';
            // Check checkbox for both completed and failed states
            const checked = (status === 'completed' || status === 'failed') ? 'checked' : '';
            const checkboxClass = status === 'completed' ? 'checkbox-completed' :
                                  status === 'failed' ? 'checkbox-failed' : '';

            // Enhanced status icons with dynamic spinner for in_progress
            const statusIcon = {
                'pending': '<span class="status-icon pending">⏳</span>',
                'in_progress': '<span class="status-icon in-progress"><span class="spinner">⟳</span></span>',
                'completed': '<span class="status-icon completed">✅</span>',
                'failed': '<span class="status-icon failed">❌</span>'
            }[status] || '<span class="status-icon">📝</span>';

            // Status text for badge
            const statusText = {
                'pending': '대기 중',
                'in_progress': '진행 중',
                'completed': '완료',
                'failed': '실패'
            }[status] || status;

            html += `<h3 class="task-${status}">`;
            html += `<input type="checkbox" ${checked} disabled class="${checkboxClass}"> `;
            html += `${statusIcon} `;
            html += `Task ${index + 1}: ${escapeHtml(task.name || 'Unnamed Task')} `;
            html += `<span class="status-badge-inline ${status}">${statusText}</span>`;
            html += `</h3>`;

            html += `<ul>`;
            html += `<li><strong>Agent:</strong> ${escapeHtml(task.agent || 'unknown')}</li>`;
            html += `<li><strong>Status:</strong> ${escapeHtml(status)}</li>`;
            html += `<li><strong>Priority:</strong> ${escapeHtml(task.priority || 'medium')}</li>`;
            if (task.description) {
                html += `<li><strong>Description:</strong> ${escapeHtml(task.description)}</li>`;
            }
            html += `</ul>`;
        });
    }

    // Results section
    if (planData.results) {
        html += `<h2>Results Summary</h2>`;
        html += `<p>${escapeHtml(planData.results)}</p>`;
    }

    return html || '<p class="plan-empty">No plan data available</p>';
}

window.switchTab = switchTab;
window.clearChatHistory = clearChatHistory;
window.showAddConfigForm = showAddConfigForm;
window.cancelConfigForm = cancelConfigForm;
window.editConfig = editConfig;
window.activateConfig = activateConfig;
window.deleteConfig = deleteConfig;
window.testConnection = testConnection;
window.saveSettings = saveSettings;
window.updateModelOptions = updateModelOptions;
window.showAddMCPServerForm = showAddMCPServerForm;
window.cancelMCPForm = cancelMCPForm;
window.loadMCPTools = loadMCPTools;
window.syncMCPServers = syncMCPServers;
window.loadMCPServers = loadMCPServers;
window.toggleMCPServer = toggleMCPServer;
window.editMCPServer = editMCPServer;
window.saveMCPServer = saveMCPServer;
window.deleteMCPServer = deleteMCPServer;
window.updateMCPTransportFields = updateMCPTransportFields;

// ==================== Session Management ====================

// Load sessions list
async function loadSessions() {
    const sessionsList = document.getElementById('sessionsList');
    const userId = document.getElementById('userId')?.value || 'test_user';
    const tenant = document.getElementById('tenant')?.value || 'test_tenant';

    try {
        const response = await fetch(`/api/sessions?user_id=${userId}&tenant=${tenant}&limit=50`);
        const data = await response.json();

        if (response.ok && data.sessions && data.sessions.length > 0) {
            const currentSessionId = getSessionId();

            let html = '';
            data.sessions.forEach(session => {
                const isActive = currentSessionId && session.session_id === currentSessionId;
                html += `
                    <div class="session-item ${isActive ? 'active' : ''}"
                            data-session-id="${session.session_id}"
                            onclick="switchSession('${session.session_id}')">
                        <span class="session-title">${escapeHtml(session.title || 'Untitled')}</span>
                        <div class="session-actions">
                            <button class="session-edit"
                                    onclick="event.stopPropagation(); editSessionTitle('${session.session_id}', '${escapeHtml(session.title || 'Untitled').replace(/'/g, "\\'")}')"
                                    title="Edit session title">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                                    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                                </svg>
                            </button>
                            <button class="session-delete"
                                    onclick="event.stopPropagation(); deleteSession('${session.session_id}')"
                                    title="Delete session">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                                </svg>
                            </button>
                        </div>
                    </div>
                `;
            });

            sessionsList.innerHTML = html;
        } else {
            sessionsList.innerHTML = `
                <div style="text-align: center; padding: 20px; color: var(--text-tertiary); font-size: 13px; line-height: 1.5;">
                    <div style="font-size: 24px; margin-bottom: 8px;">💬</div>
                    <div>No chat history yet</div>
                    <div style="font-size: 11px; margin-top: 4px;">Start a conversation below</div>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading sessions:', error);
        sessionsList.innerHTML = `
            <div style="text-align: center; padding: 20px; color: var(--error-color); font-size: 13px;">
                Failed to load sessions
            </div>
        `;
    }
}

// Switch to a different session
async function switchSession(newSessionId) {
    console.log('[switchSession] Switching to session:', newSessionId);

    // Update session ID
    sessionId = newSessionId;
    localStorage.setItem('sessionId', newSessionId);

    // Switch to chat tab
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.getElementById('manual-tab')?.classList.add('active');
    console.log('[switchSession] Switched to chat tab');

    // Update UI - mark active session
    document.querySelectorAll('.session-item').forEach(item => {
        if (item.dataset.sessionId === newSessionId) {
            item.classList.add('active');
            // Update chat header title from session item
            const sessionTitle = item.querySelector('.session-title');
            const chatTitle = document.querySelector('.chat-title');
            if (sessionTitle && chatTitle) {
                chatTitle.textContent = sessionTitle.textContent;
                console.log('[switchSession] Updated title to:', sessionTitle.textContent);
            }
        } else {
            item.classList.remove('active');
        }
    });

    // Clear current chat and load new session's history
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
        chatMessages.innerHTML = '';
        console.log('[switchSession] Cleared chat messages');
    }

    await loadChatHistory();
    console.log('[switchSession] Loaded chat history');

    // Clear execution logs
    clearExecutionLogs();
}

// Start a new chat
async function startNewChat() {
    const userId = document.getElementById('userId')?.value || 'test_user';
    const tenant = document.getElementById('tenant')?.value || 'test_tenant';

    try {
        // Create new session
        const response = await fetch('/api/sessions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: userId,
                tenant: tenant,
                title: 'New conversation'
            })
        });

        const data = await response.json();

        if (response.ok) {
            // Update session ID
            sessionId = data.session_id;
            localStorage.setItem('sessionId', data.session_id);

            // Switch to chat tab
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.getElementById('manual-tab')?.classList.add('active');

            // Update chat header title
            const chatTitle = document.querySelector('.chat-title');
            if (chatTitle) {
                chatTitle.textContent = 'New conversation';
            }

            // Clear chat messages and show welcome message
            const chatMessages = document.getElementById('chatMessages');
            if (chatMessages) {
                chatMessages.innerHTML = `
                    <div class="welcome-message">
                        <h2>What can I help you with?</h2>
                        <p>MCP 서버에 등록된 도구들을 활용하여 다양한 작업을 수행할 수 있습니다.</p>
                    </div>
                `;
            }

            // Clear execution logs
            clearExecutionLogs();

            // Reload sessions list to show the new session
            await loadSessions();

            // Focus on the input field
            const requestText = document.getElementById('requestText');
            if (requestText) {
                requestText.focus();
            }
        } else {
            alert('Failed to create new session: ' + (data.detail || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error creating new session:', error);
        alert('Error creating new session: ' + error.message);
    }
}

// Auto-update session title based on first message
async function autoUpdateSessionTitle(sessionIdToUpdate, userMessage) {
    console.log('[autoUpdateSessionTitle] Starting - sessionId:', sessionIdToUpdate, 'message:', userMessage);

    try {
        // Get session info first to check current title
        const response = await fetch(`/api/sessions?user_id=test_user&tenant=test_tenant&limit=50`);
        const data = await response.json();

        console.log('[autoUpdateSessionTitle] Fetched sessions:', data.sessions?.length || 0);

        if (!response.ok || !data.sessions) {
            console.log('[autoUpdateSessionTitle] Failed to get sessions');
            return; // Failed to get sessions, skip auto-update
        }

        // Find the current session
        const currentSession = data.sessions.find(s => s.session_id === sessionIdToUpdate);

        if (!currentSession) {
            console.log('[autoUpdateSessionTitle] Session not found in list');
            return; // Session not found
        }

        console.log('[autoUpdateSessionTitle] Current session title:', currentSession.title);

        // Only update if title is default
        const defaultTitles = ['New conversation', 'Untitled', 'new conversation', 'untitled'];
        if (!defaultTitles.includes(currentSession.title)) {
            console.log('[autoUpdateSessionTitle] Title already customized, skipping');
            return; // Title already customized, don't auto-update
        }

        // Generate title from first message (max 50 characters)
        const newTitle = userMessage.trim().substring(0, 50) + (userMessage.length > 50 ? '...' : '');
        console.log('[autoUpdateSessionTitle] New title:', newTitle);

        // Update the session title
        const updateResponse = await fetch(`/api/sessions/${sessionIdToUpdate}/title`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title: newTitle
            })
        });

        const updateData = await updateResponse.json();
        console.log('[autoUpdateSessionTitle] Update response:', updateResponse.ok, updateData);

        if (updateResponse.ok) {
            // Update chat header if this is the current session
            const chatTitle = document.querySelector('.chat-title');
            if (chatTitle) {
                chatTitle.textContent = newTitle;
                console.log('[autoUpdateSessionTitle] Updated chat header');
            }
        } else {
            console.error('[autoUpdateSessionTitle] Failed to update:', updateData);
        }
    } catch (error) {
        console.error('[autoUpdateSessionTitle] Error:', error);
        // Don't show error to user, this is a background operation
    }
}

// Edit session title
async function editSessionTitle(sessionIdToEdit, currentTitle) {
    const newTitle = prompt('Enter new title for this conversation:', currentTitle);

    if (newTitle === null || newTitle.trim() === '' || newTitle === currentTitle) {
        return; // User cancelled or didn't change the title
    }

    try {
        const response = await fetch(`/api/sessions/${sessionIdToEdit}/title`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title: newTitle.trim()
            })
        });

        const data = await response.json();

        if (response.ok) {
            // Reload the sessions list to show the updated title
            await loadSessions();

            // Update chat header if this is the current session
            if (sessionIdToEdit === getOrCreateSessionId()) {
                const chatTitle = document.querySelector('.chat-title');
                if (chatTitle) {
                    chatTitle.textContent = newTitle.trim();
                }
            }
        } else {
            alert('Failed to update session title: ' + (data.detail || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error updating session title:', error);
        alert('Error updating session title: ' + error.message);
    }
}

// Delete a session
async function deleteSession(sessionIdToDelete) {
    console.log('[deleteSession] Attempting to delete session:', sessionIdToDelete);

    if (!confirm('Are you sure you want to delete this conversation?')) {
        console.log('[deleteSession] User cancelled deletion');
        return;
    }

    try {
        console.log('[deleteSession] Sending DELETE request to:', `/api/sessions/${sessionIdToDelete}`);
        const response = await fetch(`/api/sessions/${sessionIdToDelete}`, {
            method: 'DELETE'
        });

        console.log('[deleteSession] Response status:', response.status);
        const data = await response.json();
        console.log('[deleteSession] Response data:', data);

        if (response.ok) {
            console.log('[deleteSession] Session deleted successfully');
            // If we deleted the current session, clear it and show empty state
            const currentSessionId = getSessionId();
            if (sessionIdToDelete === currentSessionId) {
                console.log('[deleteSession] Deleted current session, clearing session and showing empty state');
                clearSession();

                // Update chat title
                const chatTitle = document.querySelector('.chat-title');
                if (chatTitle) {
                    chatTitle.textContent = 'Personal Assistant';
                }

                // Show welcome message
                await loadChatHistory();
            }

            // Reload sessions list
            console.log('[deleteSession] Reloading sessions list');
            await loadSessions();
        } else {
            console.error('[deleteSession] Failed to delete:', data);
            alert('Failed to delete session: ' + (data.detail || 'Unknown error'));
        }
    } catch (error) {
        console.error('[deleteSession] Error:', error);
        alert('Error deleting session: ' + error.message);
    }
}

// Export session management functions
window.loadSessions = loadSessions;
window.switchSession = switchSession;
window.startNewChat = startNewChat;
window.editSessionTitle = editSessionTitle;
window.deleteSession = deleteSession;

// Export user profile functions
window.handleLogout = handleLogout;
