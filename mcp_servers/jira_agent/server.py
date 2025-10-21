#!/usr/bin/env python3
"""
Jira Agent MCP Server
Provides Jira issue management tools: create, read, update, delete, search
"""

import json
import sys
import asyncio
from datetime import datetime
from typing import Any, Dict, List
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

# Mock Jira issues database
issues_db: List[Dict[str, Any]] = [
    {
        "id": "PROJ-1",
        "key": "PROJ-1",
        "summary": "Implement user authentication",
        "description": "Add OAuth2 authentication to the application",
        "status": "In Progress",
        "priority": "High",
        "assignee": "john@example.com",
        "reporter": "boss@example.com",
        "created_at": "2025-10-15T09:00:00Z",
        "updated_at": "2025-10-20T14:30:00Z"
    },
    {
        "id": "PROJ-2",
        "key": "PROJ-2",
        "summary": "Fix login page responsive design",
        "description": "Login page doesn't work well on mobile devices",
        "status": "To Do",
        "priority": "Medium",
        "assignee": "jane@example.com",
        "reporter": "user@example.com",
        "created_at": "2025-10-18T11:00:00Z",
        "updated_at": "2025-10-18T11:00:00Z"
    }
]

app = Server("jira-agent")


@app.list_tools()
async def list_tools() -> List[Tool]:
    """List available Jira tools"""
    return [
        Tool(
            name="create_issue",
            description="Create a new Jira issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Issue summary/title"},
                    "description": {"type": "string", "description": "Issue description"},
                    "priority": {"type": "string", "description": "Priority (Low, Medium, High, Critical)", "enum": ["Low", "Medium", "High", "Critical"]},
                    "assignee": {"type": "string", "description": "Assignee email"},
                    "issue_type": {"type": "string", "description": "Issue type (Bug, Task, Story)", "enum": ["Bug", "Task", "Story"]}
                },
                "required": ["summary", "description"]
            }
        ),
        Tool(
            name="read_issue",
            description="Read a specific Jira issue by key",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {"type": "string", "description": "Issue key (e.g., PROJ-123)"}
                },
                "required": ["issue_key"]
            }
        ),
        Tool(
            name="update_issue",
            description="Update an existing Jira issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {"type": "string", "description": "Issue key"},
                    "summary": {"type": "string", "description": "New summary"},
                    "description": {"type": "string", "description": "New description"},
                    "status": {"type": "string", "description": "New status", "enum": ["To Do", "In Progress", "Done", "Blocked"]},
                    "priority": {"type": "string", "description": "New priority"},
                    "assignee": {"type": "string", "description": "New assignee"}
                },
                "required": ["issue_key"]
            }
        ),
        Tool(
            name="delete_issue",
            description="Delete a Jira issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {"type": "string", "description": "Issue key to delete"}
                },
                "required": ["issue_key"]
            }
        ),
        Tool(
            name="search_issues",
            description="Search Jira issues by JQL-like query",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query text"},
                    "status": {"type": "string", "description": "Filter by status"},
                    "assignee": {"type": "string", "description": "Filter by assignee"},
                    "priority": {"type": "string", "description": "Filter by priority"}
                }
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    """Handle tool calls"""

    if name == "create_issue":
        issue_num = len(issues_db) + 1
        issue_key = f"PROJ-{issue_num}"

        new_issue = {
            "id": issue_key,
            "key": issue_key,
            "summary": arguments["summary"],
            "description": arguments["description"],
            "status": "To Do",
            "priority": arguments.get("priority", "Medium"),
            "assignee": arguments.get("assignee", "unassigned"),
            "reporter": "user@example.com",
            "issue_type": arguments.get("issue_type", "Task"),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        issues_db.append(new_issue)

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "issue_key": issue_key,
                "issue": new_issue
            }, indent=2)
        )]

    elif name == "read_issue":
        issue_key = arguments["issue_key"]
        issue = next((i for i in issues_db if i["key"] == issue_key), None)

        if issue:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "issue": issue
                }, indent=2)
            )]
        else:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": f"Issue {issue_key} not found"
                }, indent=2)
            )]

    elif name == "update_issue":
        issue_key = arguments["issue_key"]
        issue = next((i for i in issues_db if i["key"] == issue_key), None)

        if issue:
            # Update fields if provided
            if "summary" in arguments:
                issue["summary"] = arguments["summary"]
            if "description" in arguments:
                issue["description"] = arguments["description"]
            if "status" in arguments:
                issue["status"] = arguments["status"]
            if "priority" in arguments:
                issue["priority"] = arguments["priority"]
            if "assignee" in arguments:
                issue["assignee"] = arguments["assignee"]

            issue["updated_at"] = datetime.now().isoformat()

            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "issue": issue
                }, indent=2)
            )]
        else:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": f"Issue {issue_key} not found"
                }, indent=2)
            )]

    elif name == "delete_issue":
        issue_key = arguments["issue_key"]
        original_count = len(issues_db)
        global issues_db
        issues_db = [i for i in issues_db if i["key"] != issue_key]

        if len(issues_db) < original_count:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "message": f"Issue {issue_key} deleted"
                }, indent=2)
            )]
        else:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": f"Issue {issue_key} not found"
                }, indent=2)
            )]

    elif name == "search_issues":
        query = arguments.get("query", "").lower()
        status_filter = arguments.get("status")
        assignee_filter = arguments.get("assignee")
        priority_filter = arguments.get("priority")

        results = []
        for issue in issues_db:
            # Text search
            if query and query not in issue["summary"].lower() and query not in issue["description"].lower():
                continue

            # Status filter
            if status_filter and issue["status"] != status_filter:
                continue

            # Assignee filter
            if assignee_filter and issue["assignee"] != assignee_filter:
                continue

            # Priority filter
            if priority_filter and issue["priority"] != priority_filter:
                continue

            results.append(issue)

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "count": len(results),
                "issues": results
            }, indent=2)
        )]

    raise ValueError(f"Unknown tool: {name}")


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
