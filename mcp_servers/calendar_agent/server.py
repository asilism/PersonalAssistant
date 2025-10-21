#!/usr/bin/env python3
"""
Calendar Agent MCP Server
Provides calendar event management tools: create, read, update, delete, list
"""

import json
import sys
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

# Mock calendar events database
events_db: List[Dict[str, Any]] = [
    {
        "id": "event_1",
        "title": "Team Meeting",
        "description": "Weekly team sync",
        "start_time": "2025-10-22T14:00:00Z",
        "end_time": "2025-10-22T15:00:00Z",
        "attendees": ["user@example.com", "team@example.com"],
        "location": "Conference Room A"
    },
    {
        "id": "event_2",
        "title": "Project Review",
        "description": "Q4 project review",
        "start_time": "2025-10-23T10:00:00Z",
        "end_time": "2025-10-23T11:30:00Z",
        "attendees": ["user@example.com", "boss@example.com"],
        "location": "Virtual"
    }
]

app = Server("calendar-agent")


@app.list_tools()
async def list_tools() -> List[Tool]:
    """List available calendar tools"""
    return [
        Tool(
            name="create_event",
            description="Create a new calendar event",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Event title"},
                    "description": {"type": "string", "description": "Event description"},
                    "start_time": {"type": "string", "description": "Start time (ISO format)"},
                    "end_time": {"type": "string", "description": "End time (ISO format)"},
                    "attendees": {"type": "array", "items": {"type": "string"}, "description": "List of attendee emails"},
                    "location": {"type": "string", "description": "Event location"}
                },
                "required": ["title", "start_time", "end_time"]
            }
        ),
        Tool(
            name="read_event",
            description="Read a specific event by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Event ID"}
                },
                "required": ["event_id"]
            }
        ),
        Tool(
            name="update_event",
            description="Update an existing event",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Event ID"},
                    "title": {"type": "string", "description": "New event title"},
                    "description": {"type": "string", "description": "New event description"},
                    "start_time": {"type": "string", "description": "New start time"},
                    "end_time": {"type": "string", "description": "New end time"},
                    "attendees": {"type": "array", "items": {"type": "string"}, "description": "New attendee list"},
                    "location": {"type": "string", "description": "New location"}
                },
                "required": ["event_id"]
            }
        ),
        Tool(
            name="delete_event",
            description="Delete an event by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Event ID to delete"}
                },
                "required": ["event_id"]
            }
        ),
        Tool(
            name="list_events",
            description="List calendar events with optional date range filter",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Start date for filter (ISO format)"},
                    "end_date": {"type": "string", "description": "End date for filter (ISO format)"},
                    "limit": {"type": "number", "description": "Maximum number of events"}
                }
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    """Handle tool calls"""

    if name == "create_event":
        event_id = f"event_{len(events_db) + 1}"
        new_event = {
            "id": event_id,
            "title": arguments["title"],
            "description": arguments.get("description", ""),
            "start_time": arguments["start_time"],
            "end_time": arguments["end_time"],
            "attendees": arguments.get("attendees", []),
            "location": arguments.get("location", ""),
            "created_at": datetime.now().isoformat()
        }
        events_db.append(new_event)

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "event_id": event_id,
                "event": new_event
            }, indent=2)
        )]

    elif name == "read_event":
        event_id = arguments["event_id"]
        event = next((e for e in events_db if e["id"] == event_id), None)

        if event:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "event": event
                }, indent=2)
            )]
        else:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": f"Event {event_id} not found"
                }, indent=2)
            )]

    elif name == "update_event":
        event_id = arguments["event_id"]
        event = next((e for e in events_db if e["id"] == event_id), None)

        if event:
            # Update fields if provided
            if "title" in arguments:
                event["title"] = arguments["title"]
            if "description" in arguments:
                event["description"] = arguments["description"]
            if "start_time" in arguments:
                event["start_time"] = arguments["start_time"]
            if "end_time" in arguments:
                event["end_time"] = arguments["end_time"]
            if "attendees" in arguments:
                event["attendees"] = arguments["attendees"]
            if "location" in arguments:
                event["location"] = arguments["location"]

            event["updated_at"] = datetime.now().isoformat()

            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "event": event
                }, indent=2)
            )]
        else:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": f"Event {event_id} not found"
                }, indent=2)
            )]

    elif name == "delete_event":
        event_id = arguments["event_id"]
        original_count = len(events_db)
        global events_db
        events_db = [e for e in events_db if e["id"] != event_id]

        if len(events_db) < original_count:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "message": f"Event {event_id} deleted"
                }, indent=2)
            )]
        else:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": f"Event {event_id} not found"
                }, indent=2)
            )]

    elif name == "list_events":
        limit = arguments.get("limit", 100)
        start_date = arguments.get("start_date")
        end_date = arguments.get("end_date")

        filtered_events = events_db

        # Apply date filters if provided
        if start_date:
            filtered_events = [e for e in filtered_events if e["start_time"] >= start_date]
        if end_date:
            filtered_events = [e for e in filtered_events if e["start_time"] <= end_date]

        result_events = filtered_events[:int(limit)]

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "count": len(result_events),
                "events": result_events
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
