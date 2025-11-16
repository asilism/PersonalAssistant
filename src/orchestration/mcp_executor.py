"""
MCP Executor - Connects to and executes MCP tools via Streamable-HTTP
"""

import asyncio
import subprocess
import json
import os
from datetime import datetime
from typing import Any, Optional, Dict, List
from contextlib import asynccontextmanager

from fastmcp import Client

from .types import Step, StepResult, ToolDefinition
from .validators import validate_email


class MCPExecutor:
    """MCPExecutor - Executes MCP tools via Streamable-HTTP using FastMCP 2.0"""

    def __init__(self):
        self._execution_count = 0
        self._servers: Dict[str, Dict[str, Any]] = {}
        self._clients: Dict[str, Client] = {}
        self._available_tools: Dict[str, ToolDefinition] = {}

    async def initialize_servers(self):
        """Initialize connections to all MCP servers"""
        # Define MCP server configurations (Streamable-HTTP based)
        server_configs = {
            "mail-agent": {
                "url": "http://localhost:8001/mcp",
                "transport": "streamable-http"
            },
            "calendar-agent": {
                "url": "http://localhost:8002/mcp",
                "transport": "streamable-http"
            },
            "jira-agent": {
                "url": "http://localhost:8004/mcp",
                "transport": "streamable-http"
            },
            "calculator-agent": {
                "url": "http://localhost:8003/mcp",
                "transport": "streamable-http"
            },
            "rpa-agent": {
                "url": "http://localhost:8005/mcp",
                "transport": "streamable-http"
            }
        }

        print("[MCPExecutor] Initializing MCP servers...")

        for server_name, config in server_configs.items():
            try:
                # Store server config
                self._servers[server_name] = {
                    "config": config,
                    "status": "starting"
                }

                print(f"[MCPExecutor] Configured {server_name} at {config['url']}")
                self._servers[server_name]["status"] = "ready"

            except Exception as e:
                print(f"[MCPExecutor] Error configuring {server_name}: {e}")
                self._servers[server_name]["status"] = "error"

        print(f"[MCPExecutor] Initialized {len(self._servers)} MCP servers")

    async def discover_tools(self) -> List[ToolDefinition]:
        """Discover all available tools from MCP servers (in parallel)"""
        all_tools = []

        async def discover_from_server(server_name: str, server_info: dict):
            """Discover tools from a single server"""
            if server_info["status"] != "ready":
                return []

            try:
                config = server_info["config"]

                # Create FastMCP client
                client = Client(config["url"])

                async with client:
                    # List tools
                    tools_result = await client.list_tools()

                    tools = []
                    for tool in tools_result:
                        tool_def = ToolDefinition(
                            name=tool.name,
                            description=tool.description or "",
                            input_schema=tool.inputSchema
                        )
                        tools.append(tool_def)
                        self._available_tools[tool.name] = tool_def

                    print(f"[MCPExecutor] Discovered {len(tools_result)} tools from {server_name}")
                    return tools

            except Exception as e:
                print(f"[MCPExecutor] Error discovering tools from {server_name}: {e}")
                import traceback
                traceback.print_exc()
                return []

        # Discover from all servers in parallel
        tasks = [
            discover_from_server(server_name, server_info)
            for server_name, server_info in self._servers.items()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine results
        for result in results:
            if isinstance(result, list):
                all_tools.extend(result)
            elif isinstance(result, Exception):
                print(f"[MCPExecutor] Exception during parallel discovery: {result}")

        return all_tools

    async def execute_step(self, step: Step) -> StepResult:
        """
        Execute a single step using MCP tools
        """
        start_time = datetime.now()

        try:
            # Pre-execution validation for specific tools
            validation_error = self._validate_tool_input(step.tool_name, step.input)
            if validation_error:
                raise ValueError(validation_error)

            # Find which server has this tool
            server_name = await self._find_server_for_tool(step.tool_name)

            if not server_name:
                raise ValueError(f"No MCP server found for tool: {step.tool_name}")

            # Execute the tool
            output = await self._execute_mcp_tool(server_name, step.tool_name, step.input)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds() * 1000

            # Check if the tool returned success=False in its output
            if isinstance(output, dict) and output.get("success") is False:
                error_msg = output.get("error", "Tool returned success=False")
                print(f"[MCPExecutor] Step {step.step_id} tool returned failure: {error_msg}")
                return StepResult(
                    step_id=step.step_id,
                    status="failure",
                    error=error_msg,
                    executed_at=start_time,
                    duration=duration
                )

            return StepResult(
                step_id=step.step_id,
                status="success",
                output=output,
                executed_at=start_time,
                duration=duration
            )

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds() * 1000

            # Extract meaningful error message from exception
            error_msg = self._extract_error_message(e)
            print(f"[MCPExecutor] Step {step.step_id} failed: {error_msg}")

            return StepResult(
                step_id=step.step_id,
                status="failure",
                error=error_msg,
                executed_at=start_time,
                duration=duration
            )

    def _validate_tool_input(self, tool_name: str, tool_input: dict) -> Optional[str]:
        """
        Validate tool input parameters before execution

        Args:
            tool_name: Name of the tool
            tool_input: Input parameters for the tool

        Returns:
            Error message if validation fails, None if valid
        """
        # Email validation for send_email tool
        if tool_name == "send_email":
            to_field = tool_input.get("to", "")

            # Auto-convert comma-separated string to list (defensive fallback)
            if isinstance(to_field, str) and "," in to_field:
                to_field = [email.strip() for email in to_field.split(",")]
                tool_input["to"] = to_field
                print(f"[MCPExecutor] Auto-converted comma-separated emails to list: {to_field}")

            # Handle both string and list types for 'to' field
            if isinstance(to_field, list):
                # Validate each email in the list
                for email in to_field:
                    is_valid, error_msg = validate_email(email)
                    if not is_valid:
                        print(f"[MCPExecutor] Email validation failed for {tool_name}: {error_msg}")
                        return f"Email validation failed: {error_msg}"
            else:
                # Single email address (string)
                is_valid, error_msg = validate_email(to_field)
                if not is_valid:
                    print(f"[MCPExecutor] Email validation failed for {tool_name}: {error_msg}")
                    return f"Email validation failed: {error_msg}"

        # Add more validations for other tools as needed

        return None

    def _extract_error_message(self, exception: Exception) -> str:
        """
        Extract meaningful error message from exception.
        Handles TaskGroup exceptions and other complex exception types.
        """
        # Check if it's an ExceptionGroup (Python 3.11+)
        if hasattr(exception, '__class__') and 'ExceptionGroup' in exception.__class__.__name__:
            errors = []
            if hasattr(exception, 'exceptions'):
                for sub_exc in exception.exceptions:
                    errors.append(str(sub_exc))
                return f"Multiple errors occurred: {'; '.join(errors)}"

        # Check for TaskGroup-related error messages
        error_str = str(exception)
        if "TaskGroup" in error_str or "unhandled errors" in error_str:
            # Try to extract the actual error from the message
            import traceback
            tb = traceback.format_exception(type(exception), exception, exception.__traceback__)
            # Look for the root cause in the traceback
            for line in tb:
                if "Error:" in line or "Exception:" in line:
                    return line.strip()

        # Default: return the exception string
        return str(exception)

    async def _find_server_for_tool(self, tool_name: str) -> Optional[str]:
        """Find which server provides a specific tool"""
        # Tool name to server mapping
        tool_server_map = {
            # Mail agent (includes contact lookup)
            "send_email": "mail-agent",
            "read_emails": "mail-agent",
            "get_email": "mail-agent",
            "delete_email": "mail-agent",
            "search_emails": "mail-agent",
            "search_contacts": "mail-agent",
            "get_contact_by_name": "mail-agent",
            "get_contact_email": "mail-agent",
            "list_all_contacts": "mail-agent",

            # Calendar agent
            "create_event": "calendar-agent",
            "read_event": "calendar-agent",
            "update_event": "calendar-agent",
            "delete_event": "calendar-agent",
            "list_events": "calendar-agent",

            # Jira agent
            "create_issue": "jira-agent",
            "read_issue": "jira-agent",
            "update_issue": "jira-agent",
            "delete_issue": "jira-agent",
            "search_issues": "jira-agent",

            # Calculator agent
            "add": "calculator-agent",
            "subtract": "calculator-agent",
            "multiply": "calculator-agent",
            "divide": "calculator-agent",
            "power": "calculator-agent",

            # RPA agent
            "search_latest_news": "rpa-agent",
            "write_report": "rpa-agent",
            "collect_attendance": "rpa-agent",
        }

        return tool_server_map.get(tool_name)

    async def _execute_mcp_tool(self, server_name: str, tool_name: str, tool_input: dict[str, Any]) -> Any:
        """
        Execute MCP tool via Streamable-HTTP connection using FastMCP 2.0
        """
        if server_name not in self._servers:
            raise ValueError(f"Unknown server: {server_name}")

        server_info = self._servers[server_name]
        if server_info["status"] != "ready":
            raise ValueError(f"Server {server_name} is not ready")

        config = server_info["config"]

        # Connect and execute via FastMCP Client
        client = Client(config["url"])

        async with client:
            # Call the tool
            result = await client.call_tool(tool_name, tool_input)

            # Parse result
            if isinstance(result, list) and len(result) > 0:
                # Get the first content item
                first_content = result[0]
                if hasattr(first_content, 'text'):
                    try:
                        return json.loads(first_content.text)
                    except json.JSONDecodeError:
                        return {"success": True, "result": first_content.text}
                elif isinstance(first_content, dict):
                    return first_content

            return {"success": True, "result": "completed"}

    async def cleanup(self):
        """Cleanup connections"""
        print("[MCPExecutor] Cleaning up connections...")
        self._clients.clear()
        self._servers.clear()
        self._available_tools.clear()
