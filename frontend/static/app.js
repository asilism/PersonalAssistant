// Tab switching
function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });

    // Show selected tab
    document.getElementById(`${tabName}-tab`).classList.add('active');
    event.target.classList.add('active');

    // Load settings if switching to settings tab
    if (tabName === 'settings') {
        loadCurrentSettings();
    } else if (tabName === 'mcp') {
        loadMCPServers();
    }
}

// Set example text
function setExample(text) {
    document.getElementById('requestText').value = text;
    document.getElementById('requestText').focus();
}

// Toggle category visibility
function toggleCategory(categoryId) {
    const category = document.getElementById(categoryId);
    const icon = document.getElementById(categoryId + '-icon');

    if (category.style.display === 'none') {
        category.style.display = 'flex';
        icon.textContent = '▼';
    } else {
        category.style.display = 'none';
        icon.textContent = '▶';
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
        'claude-sonnet-4-5-20250929'
    ],
    openai: [
        'gpt-4-turbo-preview',
        'gpt-4',
        'gpt-3.5-turbo'
    ],
    openrouter: [
        'anthropic/claude-3.5-sonnet',
        'openai/gpt-4-turbo',
        'google/gemini-pro',
        'meta-llama/llama-3-70b-instruct'
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

// Load chat history
async function loadChatHistory() {
    const sessionId = getOrCreateSessionId();
    const chatMessages = document.getElementById('chatMessages');

    try {
        const response = await fetch(`/api/chat-history?session_id=${sessionId}`);
        const data = await response.json();

        if (response.ok && data.messages && data.messages.length > 0) {
            // Clear existing messages
            chatMessages.innerHTML = '';

            // Add each message
            data.messages.forEach(msg => {
                addMessageBubble(msg.role, msg.content, false, false);
            });
        }
    } catch (error) {
        console.error('Failed to load chat history:', error);
    }
}

// Clear chat history
async function clearChatHistory() {
    if (!confirm('정말로 대화 이력을 삭제하시겠습니까?')) {
        return;
    }

    const currentSessionId = getOrCreateSessionId();
    const chatMessages = document.getElementById('chatMessages');

    try {
        const response = await fetch(`/api/chat-history?session_id=${currentSessionId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (response.ok && data.success) {
            // Clear UI
            chatMessages.innerHTML = '<div class="placeholder">메시지를 입력하세요...</div>';

            // Generate new session ID
            sessionId = 'session-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('sessionId', sessionId);

            alert('대화 이력이 삭제되었습니다.');
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

    // Set up form submission
    document.getElementById('requestForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await executeRequest();
    });
});

// Execute orchestration request with SSE streaming
async function executeRequest() {
    const requestText = document.getElementById('requestText').value;
    const userId = document.getElementById('userId').value;
    const tenant = document.getElementById('tenant').value;
    const submitBtn = document.getElementById('submitBtn');
    const chatMessages = document.getElementById('chatMessages');

    if (!requestText.trim()) return;

    // Get session ID
    const currentSessionId = getOrCreateSessionId();

    // Remove placeholder if it exists
    const placeholder = chatMessages.querySelector('.placeholder');
    if (placeholder) {
        placeholder.remove();
    }

    // Add user message bubble
    addMessageBubble('user', requestText);

    // Clear input
    document.getElementById('requestText').value = '';
    document.getElementById('requestText').style.height = 'auto';

    // Disable button and show loading
    submitBtn.disabled = true;

    // Add loading bubble
    const loadingId = addMessageBubble('assistant', '', true);

    // Clear previous logs
    clearExecutionLogs();

    try {
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
                session_id: currentSessionId
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
                            finalMessage = formatExecutionResults(eventData.message, eventData.data.results);
                        }
                    }
                } catch (e) {
                    console.error('Error parsing SSE data:', e);
                }
            }

            if (executionCompleted) break;
        }

        // Remove loading bubble
        removeMessageBubble(loadingId);

        // Add assistant response bubble with final message
        if (finalMessage) {
            addMessageBubble('assistant', finalMessage);
        } else {
            addMessageBubble('assistant', 'Execution completed');
        }

    } catch (error) {
        removeMessageBubble(loadingId);
        addMessageBubble('error', `Network error: ${error.message}`);
        addExecutionLogEntry({
            event_type: 'execution_error',
            message: error.message,
            timestamp: new Date().toISOString()
        });
    } finally {
        submitBtn.disabled = false;
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
            messageDiv.innerHTML = `
                <div class="message-icon">🤖</div>
                <div class="message-content">${content}</div>
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

// Format results for display
function formatResults(results) {
    if (typeof results === 'object') {
        return `<pre style="margin: 0; white-space: pre-wrap;">${JSON.stringify(results, null, 2)}</pre>`;
    }
    return escapeHtml(String(results));
}

// Format execution results (e.g., Jira issues, emails, calendar events, etc.)
function formatExecutionResults(message, data) {
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

    // Generic formatter for other data types
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

// Format generic data
function formatGenericData(message, data) {
    let html = `<div class="message-text">${escapeHtml(message)}</div>`;
    html += `<div style="margin-top: 10px;">`;
    html += `<details style="cursor: pointer;">`;
    html += `<summary style="font-weight: 500; color: #1976D2; padding: 8px; background: #f5f5f5; border-radius: 4px;">📦 View detailed results</summary>`;
    html += `<pre style="margin: 10px 0 0 0; padding: 10px; background: #f5f5f5; border-radius: 4px; overflow-x: auto; font-size: 12px; line-height: 1.5;">${JSON.stringify(data, null, 2)}</pre>`;
    html += `</details>`;
    html += `</div>`;
    return html;
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

    if (data.execution_time) {
        html += `<div class="log-detail"><strong>Execution Time:</strong> ${data.execution_time.toFixed(2)}s</div>`;
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
        } else if (eventData.event_type === 'step_started') {
            html += `<div class="execution-log-details">`;
            html += `<div class="execution-log-detail"><strong>Tool:</strong> ${eventData.data.tool_name}</div>`;
            if (eventData.data.tool_input && Object.keys(eventData.data.tool_input).length > 0) {
                html += `<div class="execution-log-detail"><strong>Arguments:</strong> <pre style="margin: 5px 0; white-space: pre-wrap; font-size: 11px;">${JSON.stringify(eventData.data.tool_input, null, 2)}</pre></div>`;
            }
            html += `</div>`;
        } else if (eventData.event_type === 'step_completed') {
            html += `<div class="execution-log-details">`;
            html += `<div class="execution-log-detail"><strong>Duration:</strong> ${eventData.data.duration.toFixed(2)}ms</div>`;
            if (eventData.data.output) {
                html += `<div class="execution-log-detail"><strong>Output:</strong> <pre style="margin: 5px 0; white-space: pre-wrap; font-size: 11px;">${JSON.stringify(eventData.data.output, null, 2).substring(0, 200)}${JSON.stringify(eventData.data.output, null, 2).length > 200 ? '...' : ''}</pre></div>`;
            }
            html += `</div>`;
        } else if (eventData.event_type === 'step_failed') {
            html += `<div class="execution-log-details">`;
            html += `<div class="execution-log-detail" style="color: #f44336;"><strong>Error:</strong> ${escapeHtml(eventData.data.error)}</div>`;
            html += `<div class="execution-log-detail"><strong>Duration:</strong> ${eventData.data.duration.toFixed(2)}ms</div>`;
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

// Load current settings
async function loadCurrentSettings() {
    const container = document.getElementById('currentSettings');
    container.innerHTML = '<div class="loading">Loading settings</div>';

    try {
        const response = await fetch('/api/settings?user_id=test_user&tenant=test_tenant');
        const data = await response.json();

        if (response.ok) {
            let html = '';

            if (data.provider) {
                html += `
                    <div class="settings-item">
                        <strong>Provider:</strong>
                        <span>${data.provider}</span>
                    </div>
                `;
            }

            if (data.model) {
                html += `
                    <div class="settings-item">
                        <strong>Model:</strong>
                        <span>${data.model}</span>
                    </div>
                `;
            }

            if (data.base_url) {
                html += `
                    <div class="settings-item">
                        <strong>Base URL:</strong>
                        <span>${data.base_url}</span>
                    </div>
                `;
            }

            if (data.api_key_set) {
                html += `
                    <div class="settings-item">
                        <strong>API Key:</strong>
                        <span>••••••••••••</span>
                    </div>
                `;
            }

            if (data.max_retries !== undefined) {
                html += `
                    <div class="settings-item">
                        <strong>Max Retries:</strong>
                        <span>${data.max_retries}</span>
                    </div>
                `;
            }

            if (data.timeout !== undefined) {
                html += `
                    <div class="settings-item">
                        <strong>Timeout:</strong>
                        <span>${data.timeout} ms</span>
                    </div>
                `;
            }

            if (html === '') {
                html = '<p style="color: #999;">No settings configured yet</p>';
            }

            container.innerHTML = html;
        } else {
            container.innerHTML = '<p style="color: #f44336;">Failed to load settings</p>';
        }
    } catch (error) {
        container.innerHTML = '<p style="color: #f44336;">Network error</p>';
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
    testBtn.textContent = '🧪 Testing...';
    resultDiv.innerHTML = '<div class="loading">Testing connection</div>';

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
                    <div class="result-label">✓ Connection successful!</div>
                    <div class="result-value">${data.message}</div>
                </div>
            `;
        } else {
            resultDiv.innerHTML = `
                <div class="result-error">
                    <div class="result-label">✗ Connection failed</div>
                    <div class="result-value">${data.message || data.detail || 'Unknown error'}</div>
                </div>
            `;
        }
    } catch (error) {
        resultDiv.innerHTML = `
            <div class="result-error">
                <div class="result-label">✗ Network error</div>
                <div class="result-value">${error.message}</div>
            </div>
        `;
    } finally {
        testBtn.disabled = false;
        testBtn.textContent = '🧪 Test Connection';
    }
}

// Save settings
async function saveSettings() {
    const provider = document.getElementById('llmProvider').value;
    const apiKey = document.getElementById('apiKey').value;
    const model = document.getElementById('llmModel').value;
    const baseUrl = document.getElementById('baseUrl').value;
    const maxRetries = parseInt(document.getElementById('maxRetries').value) || 3;
    const timeout = parseInt(document.getElementById('timeout').value) || 30000;
    const saveBtn = document.getElementById('saveBtn');
    const resultDiv = document.getElementById('settingsResult');

    if (!apiKey) {
        resultDiv.innerHTML = '<div class="result-error">Please enter an API key</div>';
        return;
    }

    saveBtn.disabled = true;
    saveBtn.textContent = '💾 Saving...';
    resultDiv.innerHTML = '<div class="loading">Saving settings</div>';

    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                provider: provider,
                api_key: apiKey,
                model: model,
                base_url: baseUrl || null,
                max_retries: maxRetries,
                timeout: timeout,
                user_id: 'test_user',
                tenant: 'test_tenant'
            })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            resultDiv.innerHTML = `
                <div class="result-success">
                    <div class="result-label">✓ Settings saved successfully!</div>
                    <div class="result-value">${data.message}</div>
                </div>
            `;

            // Reload current settings
            setTimeout(() => {
                loadCurrentSettings();
            }, 500);
        } else {
            resultDiv.innerHTML = `
                <div class="result-error">
                    <div class="result-label">✗ Failed to save settings</div>
                    <div class="result-value">${data.message || data.detail || 'Unknown error'}</div>
                </div>
            `;
        }
    } catch (error) {
        resultDiv.innerHTML = `
            <div class="result-error">
                <div class="result-label">✗ Network error</div>
                <div class="result-value">${error.message}</div>
            </div>
        `;
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = '💾 Save Settings';
    }
}

// Update MCP transport fields visibility
function updateMCPTransportFields() {
    const transport = document.getElementById('mcpTransport').value;
    const urlGroup = document.getElementById('mcpUrlGroup');
    const commandGroup = document.getElementById('mcpCommandGroup');
    const argsGroup = document.getElementById('mcpArgsGroup');

    if (transport === 'http') {
        urlGroup.style.display = 'block';
        commandGroup.style.display = 'none';
        argsGroup.style.display = 'none';
    } else {
        urlGroup.style.display = 'none';
        commandGroup.style.display = 'block';
        argsGroup.style.display = 'block';
    }
}

// Load MCP servers
async function loadMCPServers() {
    const container = document.getElementById('currentMCPServers');
    container.innerHTML = '<div class="loading">Loading MCP servers</div>';

    try {
        const response = await fetch('/api/mcp-servers?user_id=test_user&tenant=test_tenant');
        const data = await response.json();

        if (response.ok) {
            let html = '';

            if (data.servers && data.servers.length > 0) {
                html = '<div class="mcp-servers-list">';
                data.servers.forEach(server => {
                    const transport = server.transport || 'stdio';
                    html += `
                        <div class="mcp-server-item">
                            <div class="mcp-server-header">
                                <strong>${server.server_name}</strong>
                                <span class="mcp-status ${server.enabled ? 'enabled' : 'disabled'}">
                                    ${server.enabled ? '✓ Enabled' : '✗ Disabled'}
                                </span>
                            </div>
                            <div class="mcp-server-details">
                                <div><strong>Transport:</strong> ${transport.toUpperCase()}</div>
                                ${transport === 'http'
                                    ? `<div><strong>URL:</strong> ${server.url || 'N/A'}</div>`
                                    : `<div><strong>Command:</strong> ${server.command || 'N/A'}</div>
                                       <div><strong>Args:</strong> ${JSON.stringify(server.args || [])}</div>`
                                }
                                ${server.env_vars ? `<div><strong>Env Vars:</strong> ${JSON.stringify(server.env_vars)}</div>` : ''}
                            </div>
                            <button onclick="deleteMCPServer('${server.server_name}')" class="delete-btn">Delete</button>
                        </div>
                    `;
                });
                html += '</div>';
            } else {
                html = '<p style="color: #999;">No MCP servers configured yet</p>';
            }

            container.innerHTML = html;
        } else {
            container.innerHTML = '<p style="color: #f44336;">Failed to load MCP servers</p>';
        }
    } catch (error) {
        container.innerHTML = '<p style="color: #f44336;">Network error</p>';
    }
}

// Save MCP server
async function saveMCPServer() {
    const serverName = document.getElementById('mcpServerName').value;
    const enabled = document.getElementById('mcpEnabled').value === 'true';
    const transport = document.getElementById('mcpTransport').value;
    const url = document.getElementById('mcpUrl').value;
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
    if (transport === 'http' && !url) {
        resultDiv.innerHTML = '<div class="result-error">Please enter a server URL for HTTP transport</div>';
        return;
    }

    if (transport === 'stdio' && !command) {
        resultDiv.innerHTML = '<div class="result-error">Please enter a command for STDIO transport</div>';
        return;
    }

    // Parse JSON
    let args = [];
    let envVars = null;

    try {
        if (argsText) {
            args = JSON.parse(argsText);
        }
        if (envVarsText) {
            envVars = JSON.parse(envVarsText);
        }
    } catch (e) {
        resultDiv.innerHTML = '<div class="result-error">Invalid JSON in arguments or environment variables</div>';
        return;
    }

    saveBtn.disabled = true;
    saveBtn.textContent = '💾 Saving...';
    resultDiv.innerHTML = '<div class="loading">Saving MCP server</div>';

    try {
        const requestBody = {
            server_name: serverName,
            enabled: enabled,
            transport: transport,
            user_id: 'test_user',
            tenant: 'test_tenant'
        };

        // Add transport-specific fields
        if (transport === 'http') {
            requestBody.url = url;
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
                    <div class="result-label">✓ MCP server saved successfully!</div>
                    <div class="result-value">${data.message}</div>
                </div>
            `;

            // Clear form
            document.getElementById('mcpServerName').value = '';
            document.getElementById('mcpUrl').value = '';
            document.getElementById('mcpCommand').value = 'fastmcp';
            document.getElementById('mcpArgs').value = '';
            document.getElementById('mcpEnvVars').value = '';

            // Reload servers list
            setTimeout(() => {
                loadMCPServers();
            }, 500);
        } else {
            resultDiv.innerHTML = `
                <div class="result-error">
                    <div class="result-label">✗ Failed to save MCP server</div>
                    <div class="result-value">${data.message || data.detail || 'Unknown error'}</div>
                </div>
            `;
        }
    } catch (error) {
        resultDiv.innerHTML = `
            <div class="result-error">
                <div class="result-label">✗ Network error</div>
                <div class="result-value">${error.message}</div>
            </div>
        `;
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = '💾 Save MCP Server';
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

    container.innerHTML = '<div class="loading">Loading MCP tools...</div>';
    loadBtn.disabled = true;
    loadBtn.textContent = '🔧 Loading...';

    try {
        const response = await fetch('/api/tools');
        const data = await response.json();

        if (response.ok) {
            let html = '';

            if (data.tools && data.tools.length > 0) {
                html = `
                    <div class="tools-summary" style="margin-bottom: 15px; padding: 10px; background: #f5f5f5; border-radius: 4px;">
                        <strong>Total Tools Discovered:</strong> ${data.count}
                    </div>
                    <div class="tools-list">
                `;

                data.tools.forEach((tool, index) => {
                    // Format input schema for display
                    let schemaHtml = '';
                    if (tool.input_schema && tool.input_schema.properties) {
                        const properties = tool.input_schema.properties;
                        const required = tool.input_schema.required || [];

                        schemaHtml = '<div class="tool-schema"><strong>Parameters:</strong><ul style="margin: 5px 0; padding-left: 20px;">';

                        for (const [propName, propDetails] of Object.entries(properties)) {
                            const isRequired = required.includes(propName);
                            const requiredBadge = isRequired ? '<span style="color: #f44336; font-size: 11px;">[required]</span>' : '<span style="color: #999; font-size: 11px;">[optional]</span>';
                            schemaHtml += `<li><code>${propName}</code> ${requiredBadge} - ${propDetails.description || propDetails.type || 'No description'}</li>`;
                        }

                        schemaHtml += '</ul></div>';
                    }

                    html += `
                        <div class="tool-item" style="margin-bottom: 15px; padding: 15px; border: 1px solid #e0e0e0; border-radius: 4px;">
                            <div class="tool-header" style="margin-bottom: 10px;">
                                <strong style="font-size: 16px; color: #2196F3;">${index + 1}. ${tool.name}</strong>
                            </div>
                            <div class="tool-description" style="margin-bottom: 10px; color: #666;">
                                ${tool.description || 'No description available'}
                            </div>
                            ${schemaHtml}
                        </div>
                    `;
                });

                html += '</div>';
            } else {
                html = '<p style="color: #f44336;">No tools available. Please configure MCP servers first.</p>';
            }

            container.innerHTML = html;
        } else {
            container.innerHTML = `<p style="color: #f44336;">Failed to load tools: ${data.detail || 'Unknown error'}</p>`;
        }
    } catch (error) {
        container.innerHTML = `<p style="color: #f44336;">Network error: ${error.message}</p>`;
    } finally {
        loadBtn.disabled = false;
        loadBtn.textContent = '🔧 Load Available Tools';
    }
}
