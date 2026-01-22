#!/usr/bin/env python3
"""
CLI script to add LLM settings to the database
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestration.settings_manager import SettingsManager


def main():
    """Add LLM settings interactively"""
    print("=" * 60)
    print("LLM Settings Configuration")
    print("=" * 60)
    print()

    sm = SettingsManager()

    # Check existing settings
    existing = sm.get_all_llm_settings("test_user", "test_tenant")
    if existing:
        print(f"Found {len(existing)} existing configuration(s):")
        for s in existing:
            status = "✓ ACTIVE" if s.is_active else "  inactive"
            print(f"  [{status}] {s.config_name}: {s.provider}/{s.model}")
        print()

    # Get configuration name
    config_name = input("Configuration Name (e.g., 'Claude Production'): ").strip()
    if not config_name:
        print("Error: Configuration name is required")
        return

    # Select provider
    print("\nSelect LLM Provider:")
    print("  1. Anthropic Claude")
    print("  2. OpenAI GPT")
    print("  3. OpenRouter")

    provider_choice = input("Enter choice (1-3): ").strip()
    provider_map = {
        "1": "anthropic",
        "2": "openai",
        "3": "openrouter"
    }

    provider = provider_map.get(provider_choice)
    if not provider:
        print("Error: Invalid choice")
        return

    # Get API key (check env first)
    env_key_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY"
    }

    env_key_name = env_key_map.get(provider)
    env_api_key = os.getenv(env_key_name, "")

    if env_api_key:
        use_env = input(f"\nFound {env_key_name} in environment. Use it? (Y/n): ").strip().lower()
        if use_env in ("", "y", "yes"):
            api_key = env_api_key
        else:
            api_key = input("Enter API Key: ").strip()
    else:
        api_key = input("Enter API Key: ").strip()

    if not api_key:
        print("Error: API key is required")
        return

    # Select model
    print("\nSelect Model:")
    if provider == "anthropic":
        models = [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
        ]
    elif provider == "openai":
        models = [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
        ]
    else:  # openrouter
        models = [
            "anthropic/claude-3.5-sonnet",
            "openai/gpt-4o",
            "google/gemini-pro-1.5",
        ]

    for i, model in enumerate(models, 1):
        print(f"  {i}. {model}")
    print(f"  {len(models) + 1}. Custom model")

    model_choice = input(f"Enter choice (1-{len(models) + 1}): ").strip()
    try:
        choice_idx = int(model_choice) - 1
        if choice_idx < len(models):
            model = models[choice_idx]
        else:
            model = input("Enter custom model name: ").strip()
    except (ValueError, IndexError):
        print("Error: Invalid choice")
        return

    # Base URL (optional)
    base_url = input("\nBase URL (optional, press Enter to skip): ").strip() or None

    # Advanced settings
    print("\nAdvanced Settings (press Enter for defaults):")
    max_retries_input = input("Max Retries [3]: ").strip()
    max_retries = int(max_retries_input) if max_retries_input else 3

    timeout_input = input("Timeout in ms [30000]: ").strip()
    timeout = int(timeout_input) if timeout_input else 30000

    # Set as active
    is_active_input = input("\nSet as active configuration? (Y/n): ").strip().lower()
    is_active = is_active_input in ("", "y", "yes")

    # Save settings
    print("\n" + "=" * 60)
    print("Saving configuration...")
    print("=" * 60)
    print(f"  Name:       {config_name}")
    print(f"  Provider:   {provider}")
    print(f"  Model:      {model}")
    print(f"  Base URL:   {base_url or 'default'}")
    print(f"  Max Retries: {max_retries}")
    print(f"  Timeout:    {timeout}ms")
    print(f"  Active:     {is_active}")
    print()

    try:
        success = sm.save_llm_settings(
            user_id="test_user",
            tenant="test_tenant",
            config_name=config_name,
            provider=provider,
            api_key=api_key,
            model=model,
            base_url=base_url,
            max_retries=max_retries,
            timeout=timeout,
            is_active=is_active
        )

        if success:
            print("✓ Configuration saved successfully!")

            # Test connection
            test = input("\nTest connection now? (y/N): ").strip().lower()
            if test == "y":
                print("\nTesting connection...")
                result = sm.test_connection(
                    provider=provider,
                    api_key=api_key,
                    model=model,
                    base_url=base_url
                )

                if result.get("success"):
                    print(f"✓ {result.get('message', 'Connection successful')}")
                else:
                    print(f"✗ {result.get('message', 'Connection failed')}")
        else:
            print("✗ Failed to save configuration")

    except Exception as e:
        print(f"✗ Error: {e}")


if __name__ == "__main__":
    main()
