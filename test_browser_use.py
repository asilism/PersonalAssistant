#!/usr/bin/env python3
"""
Test script for browser-use MCP server using FastMCP Client
"""

import asyncio
import json
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


async def test_mcp_server():
    """Test browser-use MCP server"""
    server_url = "http://localhost:8016/mcp"

    print("=" * 60)
    print("Testing Browser-Use MCP Server")
    print("=" * 60)
    print()

    # Test 1: Connect to server
    print("1. Connecting to server...")
    try:
        transport = StreamableHttpTransport(server_url)
        client = Client(transport)
        print(f"   ✓ Transport created")
    except Exception as e:
        print(f"   ✗ Failed to create transport: {e}")
        return

    print()

    # Test 2: List available tools
    print("2. Listing available tools...")
    try:
        async with client:
            tools = await client.list_tools()
            print(f"   ✓ Found {len(tools)} tools:")
            print()
            for tool in tools:
                print(f"   • {tool.name}")
                if tool.description:
                    desc = tool.description.split('\n')[0]  # First line only
                    print(f"     {desc[:80]}...")
            print()
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test 3: Test check_browser_use_status tool (no API key needed)
    print("3. Testing check_browser_use_status tool...")
    try:
        async with client:
            result = await client.call_tool("check_browser_use_status", {})
            print("   ✓ Status check successful:")
            print()
            if hasattr(result, 'content'):
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        status_data = json.loads(content_item.text)
                        print(json.dumps(status_data, indent=4))
            else:
                print(f"     Result: {result}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 60)
    print("Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_mcp_server())
