"""
MCP Executor - Connects to and executes MCP tools via STDIO
"""

import asyncio
import subprocess
import json
import os
from datetime import datetime
from typing import Any, Optional, Dict, List
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .types import Step, StepResult, ToolDefinition


class MCPExecutor:
    """MCPExecutor - Executes MCP tools via real MCP servers"""

    def __init__(self):
        self._execution_count = 0
        self._servers: Dict[str, Dict[str, Any]] = {}
        self._sessions: Dict[str, ClientSession] = {}
        self._available_tools: Dict[str, ToolDefinition] = {}

    async def initialize_servers(self):
        """Initialize connections to all MCP servers"""
        # Define MCP server configurations
        server_configs = {
            "mail-agent": {
                "command": "python3",
                "args": [os.path.join(os.path.dirname(__file__), "../../mcp_servers/mail_agent/server.py")],
                "env": None
            },
            "calendar-agent": {
                "command": "python3",
                "args": [os.path.join(os.path.dirname(__file__), "../../mcp_servers/calendar_agent/server.py")],
                "env": None
            },
            "jira-agent": {
                "command": "python3",
                "args": [os.path.join(os.path.dirname(__file__), "../../mcp_servers/jira_agent/server.py")],
                "env": None
            },
            "calculator-agent": {
                "command": "python3",
                "args": [os.path.join(os.path.dirname(__file__), "../../mcp_servers/calculator_agent/server.py")],
                "env": None
            },
            "rpa-agent": {
                "command": "python3",
                "args": [os.path.join(os.path.dirname(__file__), "../../mcp_servers/rpa_agent/server.py")],
                "env": None
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

                print(f"[MCPExecutor] Configured {server_name}")
                self._servers[server_name]["status"] = "ready"

            except Exception as e:
                print(f"[MCPExecutor] Error configuring {server_name}: {e}")
                self._servers[server_name]["status"] = "error"

        print(f"[MCPExecutor] Initialized {len(self._servers)} MCP servers")

    async def discover_tools(self) -> List[ToolDefinition]:
        """Discover all available tools from MCP servers"""
        all_tools = []

        for server_name, server_info in self._servers.items():
            if server_info["status"] != "ready":
                continue

            try:
                config = server_info["config"]
                server_params = StdioServerParameters(
                    command=config["command"],
                    args=config["args"],
                    env=config.get("env")
                )

                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()

                        # List tools
                        tools_result = await session.list_tools()

                        for tool in tools_result.tools:
                            tool_def = ToolDefinition(
                                name=tool.name,
                                description=tool.description or "",
                                input_schema=tool.inputSchema
                            )
                            all_tools.append(tool_def)
                            self._available_tools[tool.name] = tool_def

                        print(f"[MCPExecutor] Discovered {len(tools_result.tools)} tools from {server_name}")

            except Exception as e:
                print(f"[MCPExecutor] Error discovering tools from {server_name}: {e}")

        return all_tools

    async def execute_step(self, step: Step) -> StepResult:
        """
        Execute a single step using MCP tools
        """
        start_time = datetime.now()

        try:
            # Find which server has this tool
            server_name = await self._find_server_for_tool(step.tool_name)

            if not server_name:
                raise ValueError(f"No MCP server found for tool: {step.tool_name}")

            # Execute the tool
            output = await self._execute_mcp_tool(server_name, step.tool_name, step.input)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds() * 1000

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

            return StepResult(
                step_id=step.step_id,
                status="failure",
                error=str(e),
                executed_at=start_time,
                duration=duration
            )

    async def _find_server_for_tool(self, tool_name: str) -> Optional[str]:
        """Find which server provides a specific tool"""
        # Tool name to server mapping
        tool_server_map = {
            # Mail agent
            "send_email": "mail-agent",
            "read_emails": "mail-agent",
            "get_email": "mail-agent",
            "delete_email": "mail-agent",
            "search_emails": "mail-agent",

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
        Execute MCP tool via STDIO connection
        """
        if server_name not in self._servers:
            raise ValueError(f"Unknown server: {server_name}")

        server_info = self._servers[server_name]
        if server_info["status"] != "ready":
            raise ValueError(f"Server {server_name} is not ready")

        config = server_info["config"]

        # Create server parameters
        server_params = StdioServerParameters(
            command=config["command"],
            args=config["args"],
            env=config.get("env")
        )

        # Connect and execute
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize session
                await session.initialize()

                # Call the tool
                result = await session.call_tool(tool_name, arguments=tool_input)

                # Parse result
                if result.content:
                    # Get the first text content
                    for content in result.content:
                        if hasattr(content, 'text'):
                            return json.loads(content.text)

                return {"success": True, "result": "completed"}

    async def cleanup(self):
        """Cleanup connections"""
        print("[MCPExecutor] Cleaning up connections...")
        self._sessions.clear()
        self._servers.clear()
