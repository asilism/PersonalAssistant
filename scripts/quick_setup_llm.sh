#!/bin/bash
# Quick setup script to add LLM settings from environment variables

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Load .env if exists
if [ -f .env ]; then
    source .env
fi

echo "============================================"
echo "Quick LLM Settings Setup"
echo "============================================"
echo ""

# Detect available provider from environment
PROVIDER=""
MODEL=""
API_KEY=""

if [ -n "$ANTHROPIC_API_KEY" ]; then
    PROVIDER="anthropic"
    MODEL="${LLM_MODEL:-claude-3-5-sonnet-20241022}"
    API_KEY="$ANTHROPIC_API_KEY"
    echo "✓ Found ANTHROPIC_API_KEY"
elif [ -n "$OPENAI_API_KEY" ]; then
    PROVIDER="openai"
    MODEL="${LLM_MODEL:-gpt-4o}"
    API_KEY="$OPENAI_API_KEY"
    echo "✓ Found OPENAI_API_KEY"
elif [ -n "$OPENROUTER_API_KEY" ]; then
    PROVIDER="openrouter"
    MODEL="${LLM_MODEL:-anthropic/claude-3.5-sonnet}"
    API_KEY="$OPENROUTER_API_KEY"
    echo "✓ Found OPENROUTER_API_KEY"
else
    echo "✗ No API key found in environment"
    echo ""
    echo "Please set one of the following in your .env file:"
    echo "  - ANTHROPIC_API_KEY"
    echo "  - OPENAI_API_KEY"
    echo "  - OPENROUTER_API_KEY"
    echo ""
    exit 1
fi

echo ""
echo "Creating default LLM configuration:"
echo "  Provider: $PROVIDER"
echo "  Model:    $MODEL"
echo ""

# Create Python script to add settings
python3 << EOF
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from src.orchestration.settings_manager import SettingsManager

sm = SettingsManager()

# Check if default config already exists
existing = sm.get_llm_settings_by_name("test_user", "test_tenant", "Default")

if existing:
    print("✓ Default configuration already exists")
    if not existing.is_active:
        print("  Setting as active...")
        sm.set_active_llm_settings("test_user", "test_tenant", "Default")
        print("  ✓ Activated")
else:
    print("Creating new configuration...")
    success = sm.save_llm_settings(
        user_id="test_user",
        tenant="test_tenant",
        config_name="Default",
        provider="$PROVIDER",
        api_key="$API_KEY",
        model="$MODEL",
        base_url=os.getenv("LLM_BASE_URL"),
        max_retries=3,
        timeout=30000,
        is_active=True
    )

    if success:
        print("✓ Configuration created successfully")
    else:
        print("✗ Failed to create configuration")
        sys.exit(1)

# Test connection
print("")
print("Testing connection...")
result = sm.test_connection(
    provider="$PROVIDER",
    api_key="$API_KEY",
    model="$MODEL",
    base_url=os.getenv("LLM_BASE_URL")
)

if result.get("success"):
    print(f"✓ {result.get('message', 'Connection successful')}")
else:
    print(f"⚠ {result.get('message', 'Connection test failed')}")
    print("  (Settings saved anyway - you can test later)")

print("")
print("============================================")
print("Setup complete!")
print("============================================")
print("")
print("Browser-use tool is now configured with:")
print(f"  Provider: $PROVIDER")
print(f"  Model:    $MODEL")
print("")

EOF
