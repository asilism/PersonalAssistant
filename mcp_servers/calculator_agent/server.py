#!/usr/bin/env python3
"""
Calculator Agent MCP Server
Provides mathematical calculation tools
"""

import json
import sys
import asyncio
import math
from typing import Any, Dict, List
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

app = Server("calculator-agent")


@app.list_tools()
async def list_tools() -> List[Tool]:
    """List available calculator tools"""
    return [
        Tool(
            name="add",
            description="Add two or more numbers",
            inputSchema={
                "type": "object",
                "properties": {
                    "numbers": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Numbers to add"
                    }
                },
                "required": ["numbers"]
            }
        ),
        Tool(
            name="subtract",
            description="Subtract numbers (first - second - third...)",
            inputSchema={
                "type": "object",
                "properties": {
                    "numbers": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Numbers to subtract"
                    }
                },
                "required": ["numbers"]
            }
        ),
        Tool(
            name="multiply",
            description="Multiply two or more numbers",
            inputSchema={
                "type": "object",
                "properties": {
                    "numbers": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Numbers to multiply"
                    }
                },
                "required": ["numbers"]
            }
        ),
        Tool(
            name="divide",
            description="Divide numbers (first / second / third...)",
            inputSchema={
                "type": "object",
                "properties": {
                    "numbers": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Numbers to divide"
                    }
                },
                "required": ["numbers"]
            }
        ),
        Tool(
            name="power",
            description="Raise a number to a power",
            inputSchema={
                "type": "object",
                "properties": {
                    "base": {"type": "number", "description": "Base number"},
                    "exponent": {"type": "number", "description": "Exponent"}
                },
                "required": ["base", "exponent"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    """Handle tool calls"""

    try:
        if name == "add":
            numbers = arguments["numbers"]
            if not numbers:
                raise ValueError("At least one number required")
            result = sum(numbers)
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "operation": "addition",
                    "numbers": numbers,
                    "result": result
                }, indent=2)
            )]

        elif name == "subtract":
            numbers = arguments["numbers"]
            if not numbers:
                raise ValueError("At least one number required")
            result = numbers[0]
            for num in numbers[1:]:
                result -= num
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "operation": "subtraction",
                    "numbers": numbers,
                    "result": result
                }, indent=2)
            )]

        elif name == "multiply":
            numbers = arguments["numbers"]
            if not numbers:
                raise ValueError("At least one number required")
            result = 1
            for num in numbers:
                result *= num
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "operation": "multiplication",
                    "numbers": numbers,
                    "result": result
                }, indent=2)
            )]

        elif name == "divide":
            numbers = arguments["numbers"]
            if not numbers:
                raise ValueError("At least one number required")
            if any(num == 0 for num in numbers[1:]):
                raise ValueError("Division by zero")
            result = numbers[0]
            for num in numbers[1:]:
                result /= num
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "operation": "division",
                    "numbers": numbers,
                    "result": result
                }, indent=2)
            )]

        elif name == "power":
            base = arguments["base"]
            exponent = arguments["exponent"]
            result = math.pow(base, exponent)
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "operation": "power",
                    "base": base,
                    "exponent": exponent,
                    "result": result
                }, indent=2)
            )]

        raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]


async def main():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
