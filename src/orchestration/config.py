"""
ConfigLoader - Loads settings for the orchestration system
"""

import os
from typing import Optional
from dotenv import load_dotenv

from .types import OrchestrationSettings, ToolDefinition

# Load environment variables
load_dotenv()


class ConfigLoader:
    """ConfigLoader - Loads orchestration settings"""

    async def get_settings(self, user_id: str, tenant: str) -> OrchestrationSettings:
        """
        Get orchestration settings for a specific user/tenant
        In production, this would query a database or config service
        """
        llm_api_key = os.getenv("ANTHROPIC_API_KEY", "")

        if not llm_api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        llm_model = os.getenv("LLM_MODEL", "claude-3-5-sonnet-20241022")
        max_retries = int(os.getenv("MAX_RETRIES", "3"))
        timeout = int(os.getenv("TIMEOUT", "30000"))

        return OrchestrationSettings(
            llm_model=llm_model,
            llm_api_key=llm_api_key,
            max_retries=max_retries,
            timeout=timeout,
            available_tools=self._get_default_tools()
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
