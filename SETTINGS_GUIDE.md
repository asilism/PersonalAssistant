# Settings Management Guide

## Overview

The Personal Assistant Orchestration Service now includes a comprehensive settings management system with:

- **SQLite Database Storage** - Persistent settings storage
- **API Key Encryption** - Secure storage using Fernet encryption
- **Web UI Settings Tab** - Easy configuration through the browser
- **Multiple LLM Support** - Anthropic, OpenAI, and OpenRouter

## Features

### 1. Encrypted Storage

API keys are encrypted using the `cryptography` library:
- Encryption key stored in `data/.encryption_key`
- Database stored in `data/settings.db`
- API keys never stored in plaintext

### 2. Settings Management API

#### Get Current Settings
```bash
GET /api/settings?user_id=test_user&tenant=test_tenant
```

Response:
```json
{
  "provider": "anthropic",
  "api_key_masked": "****key",
  "model": "claude-3-5-sonnet-20241022",
  "has_settings": true
}
```

#### Save Settings
```bash
POST /api/settings
```

Request Body:
```json
{
  "provider": "anthropic",
  "api_key": "sk-ant-xxx",
  "model": "claude-3-5-sonnet-20241022",
  "user_id": "test_user",
  "tenant": "test_tenant"
}
```

#### Test Connection
```bash
POST /api/settings/test
```

Request Body:
```json
{
  "provider": "anthropic",
  "api_key": "sk-ant-xxx",
  "model": "claude-3-5-sonnet-20241022"
}
```

Response:
```json
{
  "success": true,
  "message": "Connection successful"
}
```

### 3. Settings Priority

The system checks settings in this order:
1. **Database Settings** (per user/tenant)
2. **Environment Variables** (fallback)

This allows:
- Different users to have different LLM providers
- Override environment variables per user
- Easy testing with multiple accounts

### 4. Supported LLM Providers

#### Anthropic Claude
```json
{
  "provider": "anthropic",
  "model": "claude-3-5-sonnet-20241022"
}
```

Available models:
- `claude-3-5-sonnet-20241022` (recommended)
- `claude-3-opus-20240229`
- `claude-3-sonnet-20240229`

#### OpenAI GPT
```json
{
  "provider": "openai",
  "model": "gpt-4-turbo-preview"
}
```

Available models:
- `gpt-4-turbo-preview`
- `gpt-4`
- `gpt-3.5-turbo`

#### OpenRouter
```json
{
  "provider": "openrouter",
  "model": "anthropic/claude-3.5-sonnet"
}
```

Available models:
- `anthropic/claude-3.5-sonnet`
- `openai/gpt-4-turbo`
- `google/gemini-pro`
- And many more...

## Usage

### Via Web UI

1. Navigate to http://localhost:8000
2. Click on the **⚙️ Settings** tab
3. Select your LLM Provider
4. Enter your API Key
5. Select a Model
6. Click **🧪 Test Connection** to verify
7. Click **💾 Save Settings** to persist

### Via API

#### Python Example
```python
import requests

# Save settings
response = requests.post('http://localhost:8000/api/settings', json={
    "provider": "anthropic",
    "api_key": "sk-ant-xxx",
    "model": "claude-3-5-sonnet-20241022",
    "user_id": "user_123",
    "tenant": "my_company"
})

print(response.json())
# {"success": True, "message": "Settings saved successfully"}
```

#### cURL Example
```bash
# Get settings
curl "http://localhost:8000/api/settings?user_id=test_user&tenant=test_tenant"

# Save settings
curl -X POST http://localhost:8000/api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "anthropic",
    "api_key": "sk-ant-xxx",
    "model": "claude-3-5-sonnet-20241022"
  }'

# Test connection
curl -X POST http://localhost:8000/api/settings/test \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "anthropic",
    "api_key": "sk-ant-xxx",
    "model": "claude-3-5-sonnet-20241022"
  }'
```

## Database Schema

### llm_settings Table
```sql
CREATE TABLE llm_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    tenant TEXT NOT NULL,
    provider TEXT NOT NULL,
    api_key_encrypted TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, tenant)
);
```

## Security

### Encryption

- Uses Fernet symmetric encryption (AES 128)
- Encryption key generated on first run
- Key stored in `data/.encryption_key` with 600 permissions
- API keys encrypted before storage
- Decrypted only when needed for API calls

### Best Practices

1. **Keep encryption key safe** - Backup `data/.encryption_key`
2. **Use environment-specific databases** - Different DB for dev/prod
3. **Rotate API keys regularly** - Update through settings UI
4. **Monitor API usage** - Track costs through provider dashboards

## File Structure

```
PersonalAssistant/
├── data/                           # Created on first run
│   ├── settings.db                # SQLite database
│   └── .encryption_key           # Encryption key (git-ignored)
├── src/
│   ├── orchestration/
│   │   ├── settings_manager.py   # Settings management
│   │   ├── config.py            # Updated to use DB
│   │   └── ...
│   └── api_server.py            # Settings API endpoints
└── .gitignore                    # Excludes data/ directory
```

## Troubleshooting

### Database locked error
```python
# Solution: Close other connections
# The settings manager handles this automatically
```

### Encryption key lost
```bash
# If encryption key is lost, settings cannot be decrypted
# Solution: Reconfigure settings through UI
rm data/settings.db data/.encryption_key
# Restart server and re-enter API keys
```

### Connection test fails
```json
{
  "success": false,
  "message": "Connection failed: Invalid API key"
}
```

Solutions:
1. Verify API key is correct
2. Check provider matches key type
3. Ensure model is available for your account
4. Check internet connection

## Migration from Environment Variables

If you're migrating from `.env` file:

1. Keep `.env` as fallback
2. Configure settings through UI for each user
3. Settings in database take priority
4. Remove `.env` once all users configured

## Examples

### Multi-tenant Setup

```python
# Company A uses Anthropic
settings_manager.save_llm_settings(
    user_id="user_1",
    tenant="company_a",
    provider="anthropic",
    api_key="sk-ant-xxx",
    model="claude-3-5-sonnet-20241022"
)

# Company B uses OpenAI
settings_manager.save_llm_settings(
    user_id="user_2",
    tenant="company_b",
    provider="openai",
    api_key="sk-xxx",
    model="gpt-4-turbo-preview"
)
```

### Per-user Settings

```python
# Developer uses OpenRouter for testing
settings_manager.save_llm_settings(
    user_id="dev_user",
    tenant="internal",
    provider="openrouter",
    api_key="sk-or-xxx",
    model="anthropic/claude-3.5-sonnet"
)

# Production uses Anthropic
settings_manager.save_llm_settings(
    user_id="prod_user",
    tenant="internal",
    provider="anthropic",
    api_key="sk-ant-xxx",
    model="claude-3-5-sonnet-20241022"
)
```

## API Reference

### SettingsManager Class

```python
from orchestration.settings_manager import SettingsManager

manager = SettingsManager()

# Save settings
manager.save_llm_settings(
    user_id="user_123",
    tenant="tenant_456",
    provider="anthropic",
    api_key="sk-ant-xxx",
    model="claude-3-5-sonnet-20241022"
)

# Get settings
settings = manager.get_llm_settings("user_123", "tenant_456")
print(settings.provider)  # "anthropic"
print(settings.model)      # "claude-3-5-sonnet-20241022"

# Get settings for UI (masked API key)
display_settings = manager.get_all_settings("user_123", "tenant_456")
print(display_settings["api_key_masked"])  # "****xxx"

# Test connection
result = manager.test_connection(
    provider="anthropic",
    api_key="sk-ant-xxx",
    model="claude-3-5-sonnet-20241022"
)
print(result)  # {"success": True, "message": "Connection successful"}

# Delete settings
manager.delete_llm_settings("user_123", "tenant_456")
```

## Dependencies

New dependency added:
```
cryptography>=41.0.0
```

Install with:
```bash
pip install cryptography
```

Or use the updated `requirements.txt`:
```bash
pip install -r requirements.txt
```
