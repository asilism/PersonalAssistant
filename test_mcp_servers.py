#!/usr/bin/env python3
"""
Test script to verify MCP servers are working correctly
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from orchestration.mcp_executor import MCPExecutor


async def main():
    """Test MCP servers"""
    print("=" * 60)
    print("Testing MCP Servers with fastmcp")
    print("=" * 60)

    executor = MCPExecutor()

    # Initialize servers
    print("\n1. Initializing MCP servers...")
    await executor.initialize_servers()

    # Discover tools
    print("\n2. Discovering tools from MCP servers...")
    tools = await executor.discover_tools()

    print(f"\n3. Results:")
    print(f"   Total tools discovered: {len(tools)}")

    if tools:
        print("\n   Available tools:")
        for tool in tools:
            print(f"   - {tool.name}: {tool.description}")
    else:
        print("\n   ❌ No tools discovered! There might be an issue.")

    # Cleanup
    await executor.cleanup()

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
