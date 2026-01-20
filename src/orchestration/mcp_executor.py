"""
MCP Executor - Connects to and executes MCP tools via Streamable-HTTP or SSE
"""

import asyncio
import subprocess
import json
import os
from datetime import datetime
from typing import Any, Optional, Dict, List

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport, SSETransport

from .types import Step, StepResult, ToolDefinition
from .validators import validate_email
from .settings_manager import SettingsManager


class MCPExecutor:
    """MCPExecutor - Executes MCP tools via Streamable-HTTP or SSE using FastMCP 2.0"""

    def __init__(self, user_id: str = "test_user", tenant: str = "test_tenant", session_id: Optional[str] = None, workspace_path: Optional[str] = None):
        self._execution_count = 0
        self._servers: Dict[str, Dict[str, Any]] = {}
        self._clients: Dict[str, Client] = {}
        self._available_tools: Dict[str, ToolDefinition] = {}
        self._tool_server_map: Dict[str, str] = {}  # Dynamic tool-to-server mapping
        self._user_id = user_id
        self._tenant = tenant
        self._session_id = session_id
        self._workspace_path = workspace_path
        self._settings_manager = SettingsManager()

    def set_workspace(self, session_id: str, workspace_path: str):
        """Set workspace path for file operations"""
        self._session_id = session_id
        self._workspace_path = workspace_path
        print(f"[MCPExecutor] Workspace set to: {workspace_path}")

    async def initialize_servers(self):
        """Initialize connections to all MCP servers from database settings"""
        print(f"[MCPExecutor] Initializing MCP servers for {self._user_id}@{self._tenant}...")

        # Get MCP servers from database
        db_servers = self._settings_manager.get_all_mcp_servers(self._user_id, self._tenant)

        if db_servers:
            print(f"[MCPExecutor] Found {len(db_servers)} servers in database")
            for server in db_servers:
                if not server.enabled:
                    print(f"[MCPExecutor] Skipping disabled server: {server.server_name}")
                    continue

                try:
                    # Build server config from DB settings
                    transport_type = server.transport or "http"
                    config = {
                        "transport": transport_type,
                        "enabled": server.enabled
                    }

                    if transport_type in ("http", "streamable-http"):
                        config["url"] = server.url
                        config["transport"] = "streamable-http"
                        config["headers"] = server.headers or {}
                    elif transport_type == "sse":
                        config["url"] = server.url
                        config["transport"] = "sse"
                        config["headers"] = server.headers or {}
                    else:
                        # STDIO transport
                        config["command"] = server.command
                        config["args"] = server.args or []
                        config["env_vars"] = server.env_vars or {}

                    self._servers[server.server_name] = {
                        "config": config,
                        "status": "ready" if config.get("url") or config.get("command") else "error"
                    }

                    print(f"[MCPExecutor] Configured {server.server_name} from database (transport: {config['transport']})")

                except Exception as e:
                    print(f"[MCPExecutor] Error configuring {server.server_name}: {e}")
                    self._servers[server.server_name] = {
                        "config": {},
                        "status": "error"
                    }
        else:
            # Fallback to default servers if no database config
            print("[MCPExecutor] No servers in database, using default configuration")
            await self._initialize_default_servers()

        print(f"[MCPExecutor] Initialized {len(self._servers)} MCP servers")

    async def _initialize_default_servers(self):
        """Initialize default MCP servers (empty - servers are configured via database)"""
        # No default servers - all MCP servers must be registered manually via Settings
        print("[MCPExecutor] No default servers configured. Please register MCP servers via Settings.")

    async def discover_tools(self) -> List[ToolDefinition]:
        """Discover all available tools from MCP servers (in parallel)"""
        all_tools = []
        self._tool_server_map.clear()  # Reset tool-server mapping

        async def discover_from_server(server_name: str, server_info: dict):
            """Discover tools from a single server"""
            if server_info["status"] != "ready":
                return []

            try:
                config = server_info["config"]
                transport_type = config.get("transport")

                # Only support HTTP/Streamable-HTTP and SSE for now
                if transport_type not in ("streamable-http", "sse"):
                    print(f"[MCPExecutor] Skipping non-HTTP/SSE server: {server_name} (transport: {transport_type})")
                    return []

                # Create transport with headers support
                headers = config.get("headers", {})
                if transport_type == "sse":
                    transport = SSETransport(config["url"], headers=headers) if headers else SSETransport(config["url"])
                else:
                    transport = StreamableHttpTransport(config["url"], headers=headers) if headers else StreamableHttpTransport(config["url"])

                # Create FastMCP client with transport
                client = Client(transport)

                async with client:
                    # List tools
                    tools_result = await client.list_tools()

                    tools = []
                    for tool in tools_result:
                        # Get outputSchema from FastMCP if available
                        output_schema = getattr(tool, 'outputSchema', None)

                        # Debug: Log output schema availability
                        if output_schema:
                            print(f"[MCPExecutor] Tool {tool.name} has output_schema with {len(output_schema.get('properties', {}))} properties")
                        else:
                            print(f"[MCPExecutor] WARNING: Tool {tool.name} has NO output_schema!")

                        tool_def = ToolDefinition(
                            name=tool.name,
                            description=tool.description or "",
                            input_schema=tool.inputSchema,
                            output_schema=output_schema
                        )
                        tools.append(tool_def)
                        self._available_tools[tool.name] = tool_def
                        # Build dynamic tool-server mapping
                        self._tool_server_map[tool.name] = server_name

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

    def get_tool_server_map(self) -> Dict[str, str]:
        """Get the current tool-to-server mapping"""
        return self._tool_server_map.copy()

    def set_tool_server_map(self, tool_server_map: Dict[str, str]):
        """Set the tool-to-server mapping (used for preloaded mappings)"""
        self._tool_server_map = tool_server_map.copy()
        print(f"[MCPExecutor] Tool-server map set with {len(self._tool_server_map)} mappings")

    def get_tool_definition(self, tool_name: str) -> Optional[ToolDefinition]:
        """
        Get the tool definition for a specific tool

        Args:
            tool_name: Name of the tool

        Returns:
            ToolDefinition if found, None otherwise
        """
        return self._available_tools.get(tool_name)

    def get_server_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all configured servers"""
        return {
            name: {
                "status": info["status"],
                "url": info["config"].get("url"),
                "transport": info["config"].get("transport"),
                "tool_count": len([t for t, s in self._tool_server_map.items() if s == name])
            }
            for name, info in self._servers.items()
        }

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
        # Schema-based validation
        schema_error = self._validate_against_schema(tool_name, tool_input)
        if schema_error:
            return schema_error

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

    def _validate_against_schema(self, tool_name: str, tool_input: dict) -> Optional[str]:
        """
        Validate tool input against the tool's input_schema.

        Checks:
        1. Required parameters are present
        2. No unexpected parameters are provided

        Args:
            tool_name: Name of the tool
            tool_input: Input parameters for the tool

        Returns:
            Error message if validation fails, None if valid
        """
        # Get tool definition
        tool_def = self._available_tools.get(tool_name)
        if not tool_def or not tool_def.input_schema:
            # No schema available, skip validation
            return None

        schema = tool_def.input_schema
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        # Check for missing required parameters
        missing_params = []
        for param in required:
            if param not in tool_input:
                missing_params.append(param)

        if missing_params:
            return (
                f"Schema validation failed for '{tool_name}': "
                f"Missing required parameter(s): {missing_params}. "
                f"Required: {required}. Provided: {list(tool_input.keys())}"
            )

        # Check for unexpected parameters (not in schema properties)
        if properties:
            unexpected_params = []
            for param in tool_input.keys():
                if param not in properties:
                    unexpected_params.append(param)

            if unexpected_params:
                return (
                    f"Schema validation failed for '{tool_name}': "
                    f"Unexpected parameter(s): {unexpected_params}. "
                    f"Valid parameters: {list(properties.keys())}"
                )

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
        # Use dynamic mapping from tool discovery only
        # No static fallback - all tools must be discovered from registered MCP servers
        return self._tool_server_map.get(tool_name)

    async def _execute_mcp_tool(self, server_name: str, tool_name: str, tool_input: dict[str, Any]) -> Any:
        """
        Execute MCP tool via Streamable-HTTP or SSE connection using FastMCP 2.0
        """
        if server_name not in self._servers:
            raise ValueError(f"Unknown server: {server_name}")

        server_info = self._servers[server_name]
        if server_info["status"] != "ready":
            raise ValueError(f"Server {server_name} is not ready")

        config = server_info["config"]
        transport_type = config.get("transport", "streamable-http")

        # Create transport with headers support
        headers = config.get("headers", {}).copy()  # Make a copy to avoid modifying the original

        # Add workspace path and session ID as custom headers for MCP servers to use
        if self._workspace_path:
            headers["X-Workspace-Path"] = self._workspace_path
        if self._session_id:
            headers["X-Session-ID"] = self._session_id

        if transport_type == "sse":
            transport = SSETransport(config["url"], headers=headers) if headers else SSETransport(config["url"])
        else:
            transport = StreamableHttpTransport(config["url"], headers=headers) if headers else StreamableHttpTransport(config["url"])

        # Connect and execute via FastMCP Client
        client = Client(transport)

        async with client:
            # Call the tool
            result = await client.call_tool(tool_name, tool_input)

            # Debug logging
            print(f"[MCPExecutor] Raw result type: {type(result)}")
            print(f"[MCPExecutor] Raw result: {result}")

            # Parse result based on type
            # FastMCP can return results in various formats depending on the tool

            # Case 0: FastMCP CallToolResult object (most common in FastMCP 2.0)
            # This has 'data' or 'structured_content' attributes with the actual result
            if hasattr(result, 'data') and result.data is not None:
                print(f"[MCPExecutor] CallToolResult detected, using 'data' field")
                print(f"[MCPExecutor] data: {result.data}")
                return result.data
            if hasattr(result, 'structured_content') and result.structured_content is not None:
                print(f"[MCPExecutor] CallToolResult detected, using 'structured_content' field")
                print(f"[MCPExecutor] structured_content: {result.structured_content}")
                return result.structured_content

            # Case 1: Result is already a dict (direct return from tool)
            if isinstance(result, dict):
                print(f"[MCPExecutor] Result is dict, returning as-is")
                return result

            # Case 2: Result is a list of content items (MCP protocol format)
            if isinstance(result, list):
                # Case 2a: Empty list - tool returned no content
                if len(result) == 0:
                    print(f"[MCPExecutor] Empty result list, returning success with no data")
                    return {"success": True, "result": None, "message": "Tool returned empty result"}

                # Get the first content item
                first_content = result[0]
                print(f"[MCPExecutor] First content type: {type(first_content)}")
                print(f"[MCPExecutor] First content: {first_content}")

                # Case 2b: Content has 'text' attribute (TextContent object)
                if hasattr(first_content, 'text'):
                    print(f"[MCPExecutor] First content.text: {first_content.text}")
                    try:
                        parsed = json.loads(first_content.text)
                        print(f"[MCPExecutor] Successfully parsed JSON: {parsed}")
                        return parsed
                    except json.JSONDecodeError as e:
                        print(f"[MCPExecutor] JSON parsing failed: {e}")
                        return {"success": True, "result": first_content.text}

                # Case 2c: Content is a dict
                elif isinstance(first_content, dict):
                    print(f"[MCPExecutor] First content is dict, returning as-is")
                    return first_content

                # Case 2d: Content has other attributes (handle MCP content types)
                else:
                    # Try to extract useful data from the content object
                    print(f"[MCPExecutor] Unknown content type, attempting extraction")
                    if hasattr(first_content, '__dict__'):
                        content_dict = {k: v for k, v in first_content.__dict__.items() if not k.startswith('_')}
                        print(f"[MCPExecutor] Extracted from __dict__: {content_dict}")
                        if content_dict:
                            return {"success": True, **content_dict}
                    # Last resort: convert to string
                    print(f"[MCPExecutor] Converting content to string")
                    return {"success": True, "result": str(first_content)}

            # Case 3: Result is primitive (str, int, float, bool)
            if isinstance(result, (str, int, float, bool)):
                print(f"[MCPExecutor] Result is primitive type, wrapping in dict")
                return {"success": True, "result": result}

            # Case 4: Result is None
            if result is None:
                print(f"[MCPExecutor] Result is None")
                return {"success": True, "result": None, "message": "Tool returned no result"}

            # Fallback: Unknown format - still try to extract something useful
            print(f"[MCPExecutor] WARNING: Unknown result format")
            print(f"[MCPExecutor] Result type: {type(result)}, value: {result}")
            # Try __dict__ extraction as last resort
            if hasattr(result, '__dict__'):
                result_dict = {k: v for k, v in result.__dict__.items() if not k.startswith('_')}
                if result_dict:
                    print(f"[MCPExecutor] Extracted from __dict__: {result_dict}")
                    return {"success": True, **result_dict}
            return {"success": True, "result": str(result)}

    async def cleanup(self):
        """Cleanup connections"""
        print("[MCPExecutor] Cleaning up connections...")
        self._clients.clear()
        self._servers.clear()
        self._available_tools.clear()
        self._tool_server_map.clear()
