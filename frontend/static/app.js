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
}

// Model options for each provider
const modelOptions = {
    anthropic: [
        'claude-3-5-sonnet-20241022',
        'claude-3-opus-20240229',
        'claude-3-sonnet-20240229',
        'claude-3-haiku-20240307'
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

// Initialize model options on page load
document.addEventListener('DOMContentLoaded', () => {
    updateModelOptions();
    loadCurrentSettings();

    // Set up form submission
    document.getElementById('requestForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await executeRequest();
    });
});

// Execute orchestration request
async function executeRequest() {
    const requestText = document.getElementById('requestText').value;
    const userId = document.getElementById('userId').value;
    const tenant = document.getElementById('tenant').value;
    const submitBtn = document.getElementById('submitBtn');
    const resultContainer = document.getElementById('resultContainer');

    // Disable button and show loading
    submitBtn.disabled = true;
    submitBtn.textContent = 'Executing...';
    resultContainer.innerHTML = '<div class="loading">Processing your request</div>';

    try {
        const response = await fetch('/api/orchestrate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                request_text: requestText,
                user_id: userId,
                tenant: tenant
            })
        });

        const data = await response.json();

        if (response.ok) {
            displayResult(data);
        } else {
            displayError(data.detail || 'An error occurred');
        }
    } catch (error) {
        displayError(`Network error: ${error.message}`);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Execute Request';
    }
}

// Display result
function displayResult(data) {
    const resultContainer = document.getElementById('resultContainer');

    const statusClass = data.success ? 'result-success' : 'result-error';

    let html = `
        <div class="${statusClass}">
            <div class="result-label">Status:</div>
            <div class="result-value">${data.success ? '✓ Success' : '✗ Failed'}</div>
        </div>

        <div class="result-info">
            <div class="result-label">Message:</div>
            <div class="result-value">${escapeHtml(data.message)}</div>
        </div>

        <div class="result-info">
            <div class="result-label">Execution Time:</div>
            <div class="result-value">${data.execution_time.toFixed(2)}s</div>
        </div>
    `;

    if (data.trace_id) {
        html += `
            <div class="result-info">
                <div class="result-label">Trace ID:</div>
                <div class="result-value">${data.trace_id}</div>
            </div>
        `;
    }

    if (data.plan_id) {
        html += `
            <div class="result-info">
                <div class="result-label">Plan ID:</div>
                <div class="result-value">${data.plan_id}</div>
            </div>
        `;
    }

    if (data.results) {
        html += `
            <div class="result-info">
                <div class="result-label">Results:</div>
                <div class="result-value"><pre style="margin-top: 10px; white-space: pre-wrap;">${JSON.stringify(data.results, null, 2)}</pre></div>
            </div>
        `;
    }

    resultContainer.innerHTML = html;
}

// Display error
function displayError(message) {
    const resultContainer = document.getElementById('resultContainer');
    resultContainer.innerHTML = `
        <div class="result-error">
            <div class="result-label">Error:</div>
            <div class="result-value">${escapeHtml(message)}</div>
        </div>
    `;
}

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
                    html += `
                        <div class="mcp-server-item">
                            <div class="mcp-server-header">
                                <strong>${server.server_name}</strong>
                                <span class="mcp-status ${server.enabled ? 'enabled' : 'disabled'}">
                                    ${server.enabled ? '✓ Enabled' : '✗ Disabled'}
                                </span>
                            </div>
                            <div class="mcp-server-details">
                                <div><strong>Command:</strong> ${server.command}</div>
                                <div><strong>Args:</strong> ${JSON.stringify(server.args)}</div>
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
    const command = document.getElementById('mcpCommand').value;
    const argsText = document.getElementById('mcpArgs').value;
    const envVarsText = document.getElementById('mcpEnvVars').value;
    const saveBtn = document.getElementById('saveMCPBtn');
    const resultDiv = document.getElementById('mcpResult');

    if (!serverName) {
        resultDiv.innerHTML = '<div class="result-error">Please enter a server name</div>';
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
        const response = await fetch('/api/mcp-servers', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                server_name: serverName,
                enabled: enabled,
                command: command,
                args: args,
                env_vars: envVars,
                user_id: 'test_user',
                tenant: 'test_tenant'
            })
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
