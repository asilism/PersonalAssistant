#!/usr/bin/env python3
"""
RPA Agent MCP Server
Provides RPA automation tools: news search, report writing, attendance collection
"""

import json
import sys
import asyncio
from datetime import datetime
from typing import Any, Dict, List
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

# Mock data stores
news_data = [
    {
        "title": "AI Breakthrough in Natural Language Processing",
        "source": "Tech News Daily",
        "date": "2025-10-21",
        "summary": "Researchers announce major improvements in language model efficiency",
        "url": "https://example.com/news/ai-breakthrough"
    },
    {
        "title": "New Productivity Tools Released",
        "source": "Business Today",
        "date": "2025-10-20",
        "summary": "Leading software companies unveil next-generation productivity suites",
        "url": "https://example.com/news/productivity-tools"
    }
]

reports_db = []
attendance_db = {}

app = Server("rpa-agent")


@app.list_tools()
async def list_tools() -> List[Tool]:
    """List available RPA tools"""
    return [
        Tool(
            name="search_latest_news",
            description="Search for the latest news articles on a topic",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Topic to search for"},
                    "limit": {"type": "number", "description": "Maximum number of articles to return"}
                },
                "required": ["topic"]
            }
        ),
        Tool(
            name="write_report",
            description="Generate a formatted report based on provided data",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Report title"},
                    "sections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "heading": {"type": "string"},
                                "content": {"type": "string"}
                            }
                        },
                        "description": "Report sections"
                    },
                    "author": {"type": "string", "description": "Report author"},
                    "format": {"type": "string", "description": "Output format", "enum": ["markdown", "html", "text"]}
                },
                "required": ["title", "sections"]
            }
        ),
        Tool(
            name="collect_attendance",
            description="Collect and aggregate attendance responses from team members",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_name": {"type": "string", "description": "Name of the event"},
                    "attendee": {"type": "string", "description": "Attendee email"},
                    "status": {"type": "string", "description": "Attendance status", "enum": ["attending", "not_attending", "maybe"]},
                    "action": {"type": "string", "description": "Action to perform", "enum": ["record", "get_summary"]}
                },
                "required": ["event_name", "action"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    """Handle tool calls"""

    if name == "search_latest_news":
        topic = arguments["topic"].lower()
        limit = arguments.get("limit", 5)

        # Search news
        results = []
        for article in news_data:
            if (topic in article["title"].lower() or
                topic in article["summary"].lower()):
                results.append(article)

        # If no specific matches, return latest news
        if not results:
            results = news_data[:int(limit)]
        else:
            results = results[:int(limit)]

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "topic": arguments["topic"],
                "count": len(results),
                "articles": results
            }, indent=2)
        )]

    elif name == "write_report":
        title = arguments["title"]
        sections = arguments["sections"]
        author = arguments.get("author", "System")
        format_type = arguments.get("format", "markdown")

        # Generate report
        report_id = f"report_{len(reports_db) + 1}"
        timestamp = datetime.now().isoformat()

        if format_type == "markdown":
            content = f"# {title}\n\n"
            content += f"**Author:** {author}\n"
            content += f"**Date:** {timestamp}\n\n"
            content += "---\n\n"
            for section in sections:
                content += f"## {section['heading']}\n\n"
                content += f"{section['content']}\n\n"

        elif format_type == "html":
            content = f"<html><head><title>{title}</title></head><body>\n"
            content += f"<h1>{title}</h1>\n"
            content += f"<p><strong>Author:</strong> {author}</p>\n"
            content += f"<p><strong>Date:</strong> {timestamp}</p>\n"
            content += "<hr>\n"
            for section in sections:
                content += f"<h2>{section['heading']}</h2>\n"
                content += f"<p>{section['content']}</p>\n"
            content += "</body></html>"

        else:  # text
            content = f"{title}\n"
            content += f"{'=' * len(title)}\n\n"
            content += f"Author: {author}\n"
            content += f"Date: {timestamp}\n\n"
            for section in sections:
                content += f"{section['heading']}\n"
                content += f"{'-' * len(section['heading'])}\n"
                content += f"{section['content']}\n\n"

        report = {
            "id": report_id,
            "title": title,
            "author": author,
            "format": format_type,
            "content": content,
            "created_at": timestamp
        }
        reports_db.append(report)

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "report_id": report_id,
                "content": content,
                "format": format_type
            }, indent=2)
        )]

    elif name == "collect_attendance":
        event_name = arguments["event_name"]
        action = arguments["action"]

        if action == "record":
            attendee = arguments.get("attendee")
            status = arguments.get("status")

            if not attendee or not status:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": "attendee and status required for record action"
                    }, indent=2)
                )]

            # Record attendance
            if event_name not in attendance_db:
                attendance_db[event_name] = []

            # Update or add attendance
            existing = next((a for a in attendance_db[event_name] if a["attendee"] == attendee), None)
            if existing:
                existing["status"] = status
                existing["updated_at"] = datetime.now().isoformat()
            else:
                attendance_db[event_name].append({
                    "attendee": attendee,
                    "status": status,
                    "recorded_at": datetime.now().isoformat()
                })

            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "event_name": event_name,
                    "attendee": attendee,
                    "status": status,
                    "message": "Attendance recorded"
                }, indent=2)
            )]

        elif action == "get_summary":
            # Get summary
            if event_name not in attendance_db:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": True,
                        "event_name": event_name,
                        "summary": {
                            "attending": 0,
                            "not_attending": 0,
                            "maybe": 0,
                            "total_responses": 0
                        },
                        "responses": []
                    }, indent=2)
                )]

            responses = attendance_db[event_name]
            summary = {
                "attending": sum(1 for r in responses if r["status"] == "attending"),
                "not_attending": sum(1 for r in responses if r["status"] == "not_attending"),
                "maybe": sum(1 for r in responses if r["status"] == "maybe"),
                "total_responses": len(responses)
            }

            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "event_name": event_name,
                    "summary": summary,
                    "responses": responses
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
