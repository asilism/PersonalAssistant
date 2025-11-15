#!/usr/bin/env python3
"""
Test script to verify MCP server connection using FastMCP Client
"""

import asyncio
import sys
from fastmcp import Client


async def test_mail_agent():
    """Test connection to mail-agent MCP server"""
    print("Testing mail-agent connection...")
    print("-" * 50)

    try:
        # Create client
        client = Client("http://localhost:8001/mcp")

        async with client:
            print("✓ Successfully connected to mail-agent")

            # List available tools
            tools = await client.list_tools()
            print(f"✓ Discovered {len(tools)} tools:")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")

            # Test a simple tool call
            print("\nTesting read_emails tool...")
            result = await client.call_tool("read_emails", {"limit": 2})
            print(f"✓ Tool call successful!")

            if isinstance(result, list) and len(result) > 0:
                first_content = result[0]
                if hasattr(first_content, 'text'):
                    print(f"  Response: {first_content.text[:200]}...")

            return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_all_servers():
    """Test all MCP servers"""
    servers = [
        ("mail-agent", "http://localhost:8001/mcp"),
        ("calendar-agent", "http://localhost:8002/mcp"),
        ("calculator-agent", "http://localhost:8003/mcp"),
        ("jira-agent", "http://localhost:8004/mcp"),
        ("rpa-agent", "http://localhost:8005/mcp"),
    ]

    print("Testing all MCP servers...")
    print("=" * 50)
    print()

    results = {}

    for server_name, url in servers:
        print(f"Testing {server_name}...")
        try:
            client = Client(url)
            async with client:
                tools = await client.list_tools()
                results[server_name] = {
                    "status": "OK",
                    "tools": len(tools)
                }
                print(f"  ✓ {server_name}: {len(tools)} tools")
        except Exception as e:
            results[server_name] = {
                "status": "ERROR",
                "error": str(e)
            }
            print(f"  ✗ {server_name}: {str(e)[:60]}...")
        print()

    # Summary
    print("=" * 50)
    print("Summary:")
    print("-" * 50)
    ok_count = sum(1 for r in results.values() if r["status"] == "OK")
    total_count = len(results)
    print(f"Connected: {ok_count}/{total_count}")
    print(f"Failed: {total_count - ok_count}/{total_count}")

    return ok_count == total_count


async def main():
    """Main test function"""
    if len(sys.argv) > 1 and sys.argv[1] == "all":
        success = await test_all_servers()
    else:
        success = await test_mail_agent()

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
