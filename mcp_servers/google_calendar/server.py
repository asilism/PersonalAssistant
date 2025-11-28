#!/usr/bin/env python3
"""
Google Calendar MCP Server

Provides real Google Calendar integration via MCP protocol.
Supports listing calendars, managing events (CRUD), and quick event creation.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastmcp import FastMCP
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from auth import get_credentials, check_credentials_status, revoke_credentials

# Create FastMCP server
mcp = FastMCP("google-calendar")

# Default timezone
DEFAULT_TIMEZONE = "Asia/Seoul"


def get_calendar_service():
    """Get authenticated Google Calendar service."""
    creds = get_credentials()
    if not creds:
        raise RuntimeError(
            "Google Calendar authentication required. "
            "Please run the OAuth setup first."
        )
    return build("calendar", "v3", credentials=creds)


def parse_datetime(dt_str: str, timezone: str = DEFAULT_TIMEZONE) -> datetime:
    """Parse datetime string to datetime object."""
    # Try various formats
    formats = [
        "%Y-%m-%dT%H:%M:%S%z",  # ISO with timezone
        "%Y-%m-%dT%H:%M:%S",    # ISO without timezone
        "%Y-%m-%d %H:%M:%S",    # Standard format
        "%Y-%m-%d %H:%M",       # Without seconds
        "%Y-%m-%d",             # Date only
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(dt_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo(timezone))
            return dt
        except ValueError:
            continue

    raise ValueError(f"Cannot parse datetime: {dt_str}")


def format_event(event: dict) -> dict:
    """Format a Google Calendar event for response."""
    start = event.get("start", {})
    end = event.get("end", {})

    return {
        "id": event.get("id"),
        "summary": event.get("summary", "(No title)"),
        "description": event.get("description", ""),
        "location": event.get("location", ""),
        "start": start.get("dateTime") or start.get("date"),
        "end": end.get("dateTime") or end.get("date"),
        "attendees": [
            {
                "email": a.get("email"),
                "name": a.get("displayName", ""),
                "response": a.get("responseStatus", ""),
            }
            for a in event.get("attendees", [])
        ],
        "organizer": event.get("organizer", {}).get("email"),
        "status": event.get("status"),
        "html_link": event.get("htmlLink"),
        "hangout_link": event.get("hangoutLink"),
        "created": event.get("created"),
        "updated": event.get("updated"),
    }


@mcp.tool()
def check_auth_status() -> dict:
    """Check Google Calendar authentication status.

    Returns:
        Authentication status information including whether credentials
        are valid and configured.
    """
    status = check_credentials_status()
    return {
        "authenticated": status["valid"],
        "token_exists": status["token_exists"],
        "token_path": status["token_path"],
        "message": (
            "Authenticated and ready" if status["valid"]
            else "Authentication required. Please set up OAuth credentials."
        ),
    }


@mcp.tool()
def list_calendars() -> dict:
    """List all calendars accessible to the user.

    Returns:
        List of calendars with their IDs, names, and access roles.
    """
    try:
        service = get_calendar_service()
        calendars_result = service.calendarList().list().execute()
        calendars = calendars_result.get("items", [])

        return {
            "success": True,
            "count": len(calendars),
            "calendars": [
                {
                    "id": cal.get("id"),
                    "summary": cal.get("summary"),
                    "description": cal.get("description", ""),
                    "primary": cal.get("primary", False),
                    "access_role": cal.get("accessRole"),
                    "background_color": cal.get("backgroundColor"),
                    "timezone": cal.get("timeZone"),
                }
                for cal in calendars
            ],
        }
    except HttpError as e:
        return {"success": False, "error": f"API error: {e.reason}"}
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def list_events(
    calendar_id: str = "primary",
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    max_results: int = 50,
    query: Optional[str] = None,
    timezone: str = DEFAULT_TIMEZONE,
) -> dict:
    """List calendar events within a time range.

    Args:
        calendar_id: Calendar ID (use 'primary' for the user's primary calendar)
        time_min: Start of time range (ISO format or YYYY-MM-DD). Defaults to now.
        time_max: End of time range (ISO format or YYYY-MM-DD). Defaults to 7 days from now.
        max_results: Maximum number of events to return (1-2500)
        query: Free text search query to filter events
        timezone: Timezone for the events (default: Asia/Seoul)

    Returns:
        List of events matching the criteria.
    """
    try:
        service = get_calendar_service()

        # Set default time range
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)

        if time_min:
            start_time = parse_datetime(time_min, timezone)
        else:
            start_time = now

        if time_max:
            end_time = parse_datetime(time_max, timezone)
        else:
            end_time = now + timedelta(days=7)

        # Build query parameters
        params = {
            "calendarId": calendar_id,
            "timeMin": start_time.isoformat(),
            "timeMax": end_time.isoformat(),
            "maxResults": min(max(1, max_results), 2500),
            "singleEvents": True,
            "orderBy": "startTime",
            "timeZone": timezone,
        }

        if query:
            params["q"] = query

        events_result = service.events().list(**params).execute()
        events = events_result.get("items", [])

        return {
            "success": True,
            "count": len(events),
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            "events": [format_event(e) for e in events],
        }
    except HttpError as e:
        return {"success": False, "error": f"API error: {e.reason}"}
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def get_event(
    event_id: str,
    calendar_id: str = "primary",
) -> dict:
    """Get a specific calendar event by ID.

    Args:
        event_id: The event ID to retrieve
        calendar_id: Calendar ID (default: 'primary')

    Returns:
        The event details if found.
    """
    try:
        service = get_calendar_service()
        event = service.events().get(
            calendarId=calendar_id,
            eventId=event_id,
        ).execute()

        return {
            "success": True,
            "event": format_event(event),
        }
    except HttpError as e:
        if e.resp.status == 404:
            return {"success": False, "error": f"Event not found: {event_id}"}
        return {"success": False, "error": f"API error: {e.reason}"}
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def create_event(
    summary: str,
    start_time: str,
    end_time: str,
    calendar_id: str = "primary",
    description: Optional[str] = None,
    location: Optional[str] = None,
    attendees: Optional[list[str]] = None,
    timezone: str = DEFAULT_TIMEZONE,
    send_notifications: bool = True,
) -> dict:
    """Create a new calendar event.

    Args:
        summary: Event title/summary
        start_time: Start time (ISO format or 'YYYY-MM-DD HH:MM')
        end_time: End time (ISO format or 'YYYY-MM-DD HH:MM')
        calendar_id: Calendar ID (default: 'primary')
        description: Event description
        location: Event location
        attendees: List of attendee email addresses
        timezone: Timezone for the event (default: Asia/Seoul)
        send_notifications: Whether to send notifications to attendees

    Returns:
        The created event details.
    """
    try:
        service = get_calendar_service()

        # Parse times
        start_dt = parse_datetime(start_time, timezone)
        end_dt = parse_datetime(end_time, timezone)

        # Build event body
        event_body = {
            "summary": summary,
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": timezone,
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": timezone,
            },
        }

        if description:
            event_body["description"] = description
        if location:
            event_body["location"] = location
        if attendees:
            event_body["attendees"] = [{"email": email} for email in attendees]

        event = service.events().insert(
            calendarId=calendar_id,
            body=event_body,
            sendNotifications=send_notifications,
        ).execute()

        return {
            "success": True,
            "message": "Event created successfully",
            "event": format_event(event),
        }
    except HttpError as e:
        return {"success": False, "error": f"API error: {e.reason}"}
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def update_event(
    event_id: str,
    calendar_id: str = "primary",
    summary: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    attendees: Optional[list[str]] = None,
    timezone: str = DEFAULT_TIMEZONE,
    send_notifications: bool = True,
) -> dict:
    """Update an existing calendar event.

    Args:
        event_id: The event ID to update
        calendar_id: Calendar ID (default: 'primary')
        summary: New event title/summary
        description: New event description
        location: New event location
        start_time: New start time
        end_time: New end time
        attendees: New list of attendee email addresses (replaces existing)
        timezone: Timezone for the event
        send_notifications: Whether to send notifications to attendees

    Returns:
        The updated event details.
    """
    try:
        service = get_calendar_service()

        # Get existing event
        event = service.events().get(
            calendarId=calendar_id,
            eventId=event_id,
        ).execute()

        # Update fields if provided
        if summary is not None:
            event["summary"] = summary
        if description is not None:
            event["description"] = description
        if location is not None:
            event["location"] = location
        if start_time is not None:
            start_dt = parse_datetime(start_time, timezone)
            event["start"] = {
                "dateTime": start_dt.isoformat(),
                "timeZone": timezone,
            }
        if end_time is not None:
            end_dt = parse_datetime(end_time, timezone)
            event["end"] = {
                "dateTime": end_dt.isoformat(),
                "timeZone": timezone,
            }
        if attendees is not None:
            event["attendees"] = [{"email": email} for email in attendees]

        updated_event = service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event,
            sendNotifications=send_notifications,
        ).execute()

        return {
            "success": True,
            "message": "Event updated successfully",
            "event": format_event(updated_event),
        }
    except HttpError as e:
        if e.resp.status == 404:
            return {"success": False, "error": f"Event not found: {event_id}"}
        return {"success": False, "error": f"API error: {e.reason}"}
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def delete_event(
    event_id: str,
    calendar_id: str = "primary",
    send_notifications: bool = True,
) -> dict:
    """Delete a calendar event.

    Args:
        event_id: The event ID to delete
        calendar_id: Calendar ID (default: 'primary')
        send_notifications: Whether to send cancellation notifications

    Returns:
        Result of the delete operation.
    """
    try:
        service = get_calendar_service()

        service.events().delete(
            calendarId=calendar_id,
            eventId=event_id,
            sendNotifications=send_notifications,
        ).execute()

        return {
            "success": True,
            "message": f"Event {event_id} deleted successfully",
        }
    except HttpError as e:
        if e.resp.status == 404:
            return {"success": False, "error": f"Event not found: {event_id}"}
        return {"success": False, "error": f"API error: {e.reason}"}
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def quick_add_event(
    text: str,
    calendar_id: str = "primary",
    send_notifications: bool = True,
) -> dict:
    """Quickly create an event using natural language.

    Google Calendar will parse the text to extract event details.

    Args:
        text: Natural language text describing the event
              (e.g., "Meeting with John tomorrow at 3pm" or
               "Dinner at 7pm on Friday at Seoul Restaurant")
        calendar_id: Calendar ID (default: 'primary')
        send_notifications: Whether to send notifications

    Returns:
        The created event details.
    """
    try:
        service = get_calendar_service()

        event = service.events().quickAdd(
            calendarId=calendar_id,
            text=text,
            sendNotifications=send_notifications,
        ).execute()

        return {
            "success": True,
            "message": "Event created from quick add",
            "event": format_event(event),
        }
    except HttpError as e:
        return {"success": False, "error": f"API error: {e.reason}"}
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def find_free_time(
    duration_minutes: int = 60,
    calendar_id: str = "primary",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    working_hours_start: int = 9,
    working_hours_end: int = 18,
    timezone: str = DEFAULT_TIMEZONE,
) -> dict:
    """Find available time slots in the calendar.

    Args:
        duration_minutes: Required duration in minutes
        calendar_id: Calendar ID (default: 'primary')
        start_date: Start searching from this date (default: today)
        end_date: Stop searching at this date (default: 7 days from start)
        working_hours_start: Start of working hours (0-23, default: 9)
        working_hours_end: End of working hours (0-23, default: 18)
        timezone: Timezone to use

    Returns:
        List of available time slots.
    """
    try:
        service = get_calendar_service()

        tz = ZoneInfo(timezone)
        now = datetime.now(tz)

        if start_date:
            start = parse_datetime(start_date, timezone)
            # Start from beginning of day
            start = start.replace(hour=working_hours_start, minute=0, second=0, microsecond=0)
        else:
            start = now
            # If current time is before working hours, start at working hours
            if start.hour < working_hours_start:
                start = start.replace(hour=working_hours_start, minute=0, second=0, microsecond=0)

        if end_date:
            end = parse_datetime(end_date, timezone)
        else:
            end = start + timedelta(days=7)

        # Get events in the range
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            timeZone=timezone,
        ).execute()

        events = events_result.get("items", [])

        # Find free slots
        free_slots = []
        current_day = start.date()
        end_day = end.date()

        while current_day <= end_day:
            day_start = datetime(
                current_day.year, current_day.month, current_day.day,
                working_hours_start, 0, 0, tzinfo=tz
            )
            day_end = datetime(
                current_day.year, current_day.month, current_day.day,
                working_hours_end, 0, 0, tzinfo=tz
            )

            # Skip if day_start is in the past
            if day_end < now:
                current_day += timedelta(days=1)
                continue

            if day_start < now:
                day_start = now

            # Get events for this day
            day_events = []
            for event in events:
                event_start = event.get("start", {})
                event_end = event.get("end", {})

                start_str = event_start.get("dateTime") or event_start.get("date")
                end_str = event_end.get("dateTime") or event_end.get("date")

                if not start_str or not end_str:
                    continue

                try:
                    e_start = parse_datetime(start_str, timezone)
                    e_end = parse_datetime(end_str, timezone)

                    if e_start.date() == current_day or e_end.date() == current_day:
                        day_events.append((e_start, e_end))
                except:
                    continue

            # Sort events by start time
            day_events.sort(key=lambda x: x[0])

            # Find gaps
            slot_start = day_start
            for e_start, e_end in day_events:
                if e_start > slot_start:
                    slot_duration = (e_start - slot_start).total_seconds() / 60
                    if slot_duration >= duration_minutes:
                        free_slots.append({
                            "start": slot_start.isoformat(),
                            "end": e_start.isoformat(),
                            "duration_minutes": int(slot_duration),
                        })
                slot_start = max(slot_start, e_end)

            # Check remaining time in day
            if slot_start < day_end:
                slot_duration = (day_end - slot_start).total_seconds() / 60
                if slot_duration >= duration_minutes:
                    free_slots.append({
                        "start": slot_start.isoformat(),
                        "end": day_end.isoformat(),
                        "duration_minutes": int(slot_duration),
                    })

            current_day += timedelta(days=1)

        return {
            "success": True,
            "duration_requested": duration_minutes,
            "search_range": {
                "start": start.isoformat(),
                "end": end.isoformat(),
            },
            "working_hours": f"{working_hours_start}:00 - {working_hours_end}:00",
            "count": len(free_slots),
            "free_slots": free_slots[:20],  # Limit to 20 slots
        }
    except HttpError as e:
        return {"success": False, "error": f"API error: {e.reason}"}
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    # Run as streamable-HTTP server on port 8010
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8010)
