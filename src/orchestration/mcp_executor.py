"""
MCP Executor - Directly executes MCP tools
Instead of sending messages to TaskService, this executes MCP tools directly
"""

import asyncio
import subprocess
import json
from datetime import datetime
from typing import Any, Optional

from .types import Step, StepResult


class MCPExecutor:
    """MCPExecutor - Executes MCP tools directly"""

    def __init__(self):
        self._execution_count = 0

    async def execute_step(self, step: Step) -> StepResult:
        """
        Execute a single step using MCP tools
        This is a simplified implementation - in production, use the official MCP SDK
        """
        start_time = datetime.now()

        try:
            # Simulate MCP tool execution
            # In a real implementation, this would:
            # 1. Connect to MCP server
            # 2. Call the tool with the input
            # 3. Return the result

            output = await self._execute_mcp_tool(step.tool_name, step.input)

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

    async def _execute_mcp_tool(self, tool_name: str, tool_input: dict[str, Any]) -> Any:
        """
        Execute MCP tool (simplified implementation)
        In production, use the MCP SDK to connect to MCP servers
        """
        # Mock implementation for different tools
        if tool_name == "web_search":
            return await self._mock_web_search(tool_input.get("query", ""))

        elif tool_name == "read_file":
            return await self._mock_read_file(tool_input.get("path", ""))

        elif tool_name == "write_file":
            return await self._mock_write_file(
                tool_input.get("path", ""),
                tool_input.get("content", "")
            )

        elif tool_name == "execute_command":
            return await self._mock_execute_command(tool_input.get("command", ""))

        elif tool_name == "send_email":
            return await self._mock_send_email(
                tool_input.get("to", ""),
                tool_input.get("subject", ""),
                tool_input.get("body", "")
            )

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    async def _mock_web_search(self, query: str) -> dict[str, Any]:
        """Mock web search"""
        await asyncio.sleep(0.1)  # Simulate network delay
        return {
            "query": query,
            "results": [
                {"title": f"Result for: {query}", "url": "https://example.com", "snippet": "..."}
            ]
        }

    async def _mock_read_file(self, path: str) -> dict[str, Any]:
        """Mock file read"""
        await asyncio.sleep(0.05)
        return {"path": path, "content": f"[Content of {path}]"}

    async def _mock_write_file(self, path: str, content: str) -> dict[str, Any]:
        """Mock file write"""
        await asyncio.sleep(0.05)
        return {"path": path, "bytes_written": len(content)}

    async def _mock_execute_command(self, command: str) -> dict[str, Any]:
        """Mock command execution"""
        await asyncio.sleep(0.1)
        return {
            "command": command,
            "stdout": f"[Output of: {command}]",
            "stderr": "",
            "exit_code": 0
        }

    async def _mock_send_email(self, to: str, subject: str, body: str) -> dict[str, Any]:
        """Mock email sending"""
        await asyncio.sleep(0.1)
        return {
            "to": to,
            "subject": subject,
            "status": "sent",
            "message_id": f"msg_{self._execution_count}"
        }
