"""
ConfigLoader - Loads settings for the orchestration system
"""

import os
from typing import Optional, List
from dotenv import load_dotenv

from .types import OrchestrationSettings, ToolDefinition
from .settings_manager import SettingsManager

# Load environment variables
load_dotenv()


class ConfigLoader:
    """ConfigLoader - Loads orchestration settings"""

    def __init__(self):
        self.settings_manager = SettingsManager()

    async def get_settings(
        self,
        user_id: str,
        tenant: str,
        mcp_tools: Optional[List[ToolDefinition]] = None
    ) -> OrchestrationSettings:
        """
        Get orchestration settings for a specific user/tenant
        Checks database first, then falls back to environment variables
        """
        # Try to get settings from database first
        db_settings = self.settings_manager.get_llm_settings(user_id, tenant)

        if db_settings:
            # Use database settings
            llm_provider = db_settings.provider
            llm_api_key = db_settings.api_key
            llm_model = db_settings.model
            print(f"[ConfigLoader] Using database settings for {user_id}@{tenant}")
        else:
            # Fall back to environment variables
            llm_provider = os.getenv("LLM_PROVIDER", "anthropic")

            # Get API keys based on provider
            if llm_provider == "anthropic":
                llm_api_key = os.getenv("ANTHROPIC_API_KEY", "")
                llm_model = os.getenv("LLM_MODEL", "claude-3-5-sonnet-20241022")
            elif llm_provider == "openai":
                llm_api_key = os.getenv("OPENAI_API_KEY", "")
                llm_model = os.getenv("LLM_MODEL", "gpt-4-turbo-preview")
            elif llm_provider == "openrouter":
                llm_api_key = os.getenv("OPENROUTER_API_KEY", "")
                llm_model = os.getenv("LLM_MODEL", "anthropic/claude-3.5-sonnet")
            else:
                llm_api_key = os.getenv("ANTHROPIC_API_KEY", "")
                llm_model = os.getenv("LLM_MODEL", "claude-3-5-sonnet-20241022")

            print(f"[ConfigLoader] Using environment variable settings")

        if not llm_api_key:
            raise ValueError(
                f"No API key configured. Please set up API key in Settings or via "
                f"{llm_provider.upper()}_API_KEY environment variable"
            )

        max_retries = int(os.getenv("MAX_RETRIES", "3"))
        timeout = int(os.getenv("TIMEOUT", "30000"))

        # Use MCP tools if provided, otherwise use defaults
        available_tools = mcp_tools if mcp_tools else self._get_default_tools()

        return OrchestrationSettings(
            llm_model=llm_model,
            llm_api_key=llm_api_key,
            max_retries=max_retries,
            timeout=timeout,
            available_tools=available_tools
        )

    def _get_default_tools(self) -> list[ToolDefinition]:
        """
        Get default MCP tools
        These would typically be discovered from MCP servers
        """
        return [
            ToolDefinition(
                name="web_search",
                description="Search the web for information",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query"
                        }
                    },
                    "required": ["query"]
                }
            ),
            ToolDefinition(
                name="read_file",
                description="Read contents of a file",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file"
                        }
                    },
                    "required": ["path"]
                }
            ),
            ToolDefinition(
                name="write_file",
                description="Write content to a file",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write"
                        }
                    },
                    "required": ["path", "content"]
                }
            ),
            ToolDefinition(
                name="execute_command",
                description="Execute a shell command",
                input_schema={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Command to execute"
                        }
                    },
                    "required": ["command"]
                }
            ),
            ToolDefinition(
                name="send_email",
                description="Send an email",
                input_schema={
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "string",
                            "description": "Recipient email address"
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject"
                        },
                        "body": {
                            "type": "string",
                            "description": "Email body"
                        }
                    },
                    "required": ["to", "subject", "body"]
                }
            )
        ]
