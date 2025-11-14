#!/usr/bin/env python3
"""
Calendar Agent MCP Server
Provides calendar event management tools: create, read, update, delete, list
"""

from datetime import datetime
from typing import Optional
from fastmcp import FastMCP
import uvicorn

# Create FastMCP server
mcp = FastMCP("calendar-agent")

# Mock calendar events database
events_db: list[dict] = [
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


@mcp.tool()
def create_event(
    title: str,
    start_time: str,
    end_time: str,
    description: str = "",
    attendees: list[str] = None,
    location: str = ""
) -> dict:
    """Create a new calendar event

    Args:
        title: Event title
        start_time: Start time (ISO format)
        end_time: End time (ISO format)
        description: Event description
        attendees: List of attendee emails
        location: Event location

    Returns:
        The created event
    """
    event_id = f"event_{len(events_db) + 1}"
    new_event = {
        "id": event_id,
        "title": title,
        "description": description,
        "start_time": start_time,
        "end_time": end_time,
        "attendees": attendees or [],
        "location": location,
        "created_at": datetime.now().isoformat()
    }
    events_db.append(new_event)

    return {
        "success": True,
        "event_id": event_id,
        "event": new_event
    }


@mcp.tool()
def read_event(event_id: str) -> dict:
    """Read a specific event by ID

    Args:
        event_id: Event ID

    Returns:
        The event if found
    """
    event = next((e for e in events_db if e["id"] == event_id), None)

    if event:
        return {
            "success": True,
            "event": event
        }
    else:
        return {
            "success": False,
            "error": f"Event {event_id} not found"
        }


@mcp.tool()
def update_event(
    event_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    attendees: Optional[list[str]] = None,
    location: Optional[str] = None
) -> dict:
    """Update an existing event

    Args:
        event_id: Event ID
        title: New event title
        description: New event description
        start_time: New start time
        end_time: New end time
        attendees: New attendee list
        location: New location

    Returns:
        The updated event
    """
    event = next((e for e in events_db if e["id"] == event_id), None)

    if event:
        # Update fields if provided
        if title is not None:
            event["title"] = title
        if description is not None:
            event["description"] = description
        if start_time is not None:
            event["start_time"] = start_time
        if end_time is not None:
            event["end_time"] = end_time
        if attendees is not None:
            event["attendees"] = attendees
        if location is not None:
            event["location"] = location

        event["updated_at"] = datetime.now().isoformat()

        return {
            "success": True,
            "event": event
        }
    else:
        return {
            "success": False,
            "error": f"Event {event_id} not found"
        }


@mcp.tool()
def delete_event(event_id: str) -> dict:
    """Delete an event by ID

    Args:
        event_id: Event ID to delete

    Returns:
        Result of the delete operation
    """
    global events_db
    original_count = len(events_db)
    events_db = [e for e in events_db if e["id"] != event_id]

    if len(events_db) < original_count:
        return {
            "success": True,
            "message": f"Event {event_id} deleted"
        }
    else:
        return {
            "success": False,
            "error": f"Event {event_id} not found"
        }


@mcp.tool()
def list_events(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100
) -> dict:
    """List calendar events with optional date range filter

    Args:
        start_date: Start date for filter (ISO format)
        end_date: End date for filter (ISO format)
        limit: Maximum number of events

    Returns:
        List of events
    """
    filtered_events = events_db

    # Apply date filters if provided
    if start_date:
        filtered_events = [e for e in filtered_events if e["start_time"] >= start_date]
    if end_date:
        filtered_events = [e for e in filtered_events if e["start_time"] <= end_date]

    result_events = filtered_events[:limit]

    return {
        "success": True,
        "count": len(result_events),
        "events": result_events
    }


if __name__ == "__main__":
    # Run as HTTP server on port 8002
    uvicorn.run(mcp.get_asgi_app(), host="0.0.0.0", port=8002)
