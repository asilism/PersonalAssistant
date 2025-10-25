#!/usr/bin/env python3
"""
Mail Agent MCP Server
Provides email management tools: send, read, delete, search
"""

import json
import sys
import asyncio
from datetime import datetime
from typing import Any, Dict, List
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

# Mock email database
emails_db: List[Dict[str, Any]] = [
    {
        "id": "email_1",
        "from": "boss@example.com",
        "to": "user@example.com",
        "subject": "Weekly Report Required",
        "body": "Please send me the weekly report by Friday.",
        "timestamp": "2025-10-20T10:00:00Z",
        "read": True
    },
    {
        "id": "email_2",
        "from": "team@example.com",
        "to": "user@example.com",
        "subject": "Team Meeting Tomorrow",
        "body": "Don't forget about the team meeting at 2 PM tomorrow.",
        "timestamp": "2025-10-20T14:30:00Z",
        "read": False
    }
]

app = Server("mail-agent")


@app.list_tools()
async def list_tools() -> List[Tool]:
    """List available email tools"""
    return [
        Tool(
            name="send_email",
            description="Send an email to a recipient",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Email subject"},
                    "body": {"type": "string", "description": "Email body content"}
                },
                "required": ["to", "subject", "body"]
            }
        ),
        Tool(
            name="read_emails",
            description="Read emails from inbox with optional filters",
            inputSchema={
                "type": "object",
                "properties": {
                    "unread_only": {"type": "boolean", "description": "Only show unread emails"},
                    "limit": {"type": "number", "description": "Maximum number of emails to return"}
                }
            }
        ),
        Tool(
            name="get_email",
            description="Get a specific email by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "email_id": {"type": "string", "description": "Email ID"}
                },
                "required": ["email_id"]
            }
        ),
        Tool(
            name="delete_email",
            description="Delete an email by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "email_id": {"type": "string", "description": "Email ID to delete"}
                },
                "required": ["email_id"]
            }
        ),
        Tool(
            name="search_emails",
            description="Search emails by query string",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "field": {"type": "string", "description": "Field to search in (subject, body, from)", "enum": ["subject", "body", "from", "all"]}
                },
                "required": ["query"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    """Handle tool calls"""
    global emails_db

    if name == "send_email":
        to = arguments["to"]
        subject = arguments["subject"]
        body = arguments["body"]

        # Create new email
        email_id = f"email_{len(emails_db) + 1}"
        new_email = {
            "id": email_id,
            "from": "user@example.com",
            "to": to,
            "subject": subject,
            "body": body,
            "timestamp": datetime.now().isoformat(),
            "read": True,
            "sent": True
        }
        emails_db.append(new_email)

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "email_id": email_id,
                "message": f"Email sent to {to}",
                "subject": subject
            }, indent=2)
        )]

    elif name == "read_emails":
        unread_only = arguments.get("unread_only", False)
        limit = arguments.get("limit", 10)

        filtered_emails = emails_db
        if unread_only:
            filtered_emails = [e for e in emails_db if not e.get("read", True)]

        result_emails = filtered_emails[:int(limit)]

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "count": len(result_emails),
                "emails": result_emails
            }, indent=2)
        )]

    elif name == "get_email":
        email_id = arguments["email_id"]
        email = next((e for e in emails_db if e["id"] == email_id), None)

        if email:
            # Mark as read
            email["read"] = True
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "email": email
                }, indent=2)
            )]
        else:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": f"Email {email_id} not found"
                }, indent=2)
            )]

    elif name == "delete_email":
        email_id = arguments["email_id"]
        original_count = len(emails_db)
        emails_db = [e for e in emails_db if e["id"] != email_id]

        if len(emails_db) < original_count:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "message": f"Email {email_id} deleted"
                }, indent=2)
            )]
        else:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": f"Email {email_id} not found"
                }, indent=2)
            )]

    elif name == "search_emails":
        query = arguments["query"].lower()
        field = arguments.get("field", "all")

        results = []
        for email in emails_db:
            if field == "all":
                if (query in email.get("subject", "").lower() or
                    query in email.get("body", "").lower() or
                    query in email.get("from", "").lower()):
                    results.append(email)
            elif field in email and query in email[field].lower():
                results.append(email)

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "count": len(results),
                "results": results
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
