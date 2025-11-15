#!/usr/bin/env python3
"""
Mail Agent MCP Server
Provides email management tools: send, read, delete, search
"""

import re
from datetime import datetime
from typing import Optional
from fastmcp import FastMCP

# Create FastMCP server
mcp = FastMCP("mail-agent")

# Mock email database
emails_db: list[dict] = [
    {
        "id": "email_1",
        "from": "sungjun87.lee@samsung.com",
        "to": "jaehyun.kim@samsung.com",
        "subject": "Weekly Report Required",
        "body": "Please send me the weekly report by Friday.",
        "timestamp": "2025-10-20T10:00:00Z",
        "read": True
    },
    {
        "id": "email_2",
        "from": "dev-team@samsung.com",
        "to": "jaehyun.kim@samsung.com",
        "subject": "Team Meeting Tomorrow",
        "body": "Don't forget about the team meeting at 2 PM tomorrow.",
        "timestamp": "2025-10-20T14:30:00Z",
        "read": False
    }
]


@mcp.tool()
def send_email(to: str, subject: str, body: str) -> dict:
    """Send an email to a recipient

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body content

    Returns:
        Result of the send operation
    """
    # Validate email address
    if not to:
        return {
            "success": False,
            "error": "Email validation failed: Email address is required"
        }

    # Check for template variables
    template_pattern = r'\{\{.*?\}\}'
    if re.search(template_pattern, to):
        return {
            "success": False,
            "error": f"Email validation failed: Email address contains unresolved template variable: {to}"
        }

    # Check email format
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, to.strip()):
        return {
            "success": False,
            "error": f"Email validation failed: Invalid email address format: {to}"
        }

    # Block common placeholder/fake domains
    blocked_domains = [
        'example.com', 'example.org', 'example.net',
        'test.com', 'test.org', 'test.net',
        'sample.com', 'sample.org', 'sample.net',
        'placeholder.com', 'dummy.com', 'fake.com'
    ]
    email_domain = to.strip().split('@')[-1].lower()
    if email_domain in blocked_domains:
        return {
            "success": False,
            "error": f"Email validation failed: '{email_domain}' is a placeholder domain. Please provide a valid email address for the recipient."
        }

    # Create new email
    email_id = f"email_{len(emails_db) + 1}"
    new_email = {
        "id": email_id,
        "from": "jaehyun.kim@samsung.com",
        "to": to,
        "subject": subject,
        "body": body,
        "timestamp": datetime.now().isoformat(),
        "read": True,
        "sent": True
    }
    emails_db.append(new_email)

    return {
        "success": True,
        "email_id": email_id,
        "message": f"Email sent to {to}",
        "subject": subject
    }


@mcp.tool()
def read_emails(unread_only: bool = False, limit: int = 10) -> dict:
    """Read emails from inbox with optional filters

    Args:
        unread_only: Only show unread emails
        limit: Maximum number of emails to return

    Returns:
        List of emails
    """
    filtered_emails = emails_db
    if unread_only:
        filtered_emails = [e for e in emails_db if not e.get("read", True)]

    result_emails = filtered_emails[:limit]

    return {
        "success": True,
        "count": len(result_emails),
        "emails": result_emails
    }


@mcp.tool()
def get_email(email_id: str) -> dict:
    """Get a specific email by ID

    Args:
        email_id: Email ID

    Returns:
        The email if found
    """
    email = next((e for e in emails_db if e["id"] == email_id), None)

    if email:
        # Mark as read
        email["read"] = True
        return {
            "success": True,
            "email": email
        }
    else:
        return {
            "success": False,
            "error": f"Email {email_id} not found"
        }


@mcp.tool()
def delete_email(email_id: str) -> dict:
    """Delete an email by ID

    Args:
        email_id: Email ID to delete

    Returns:
        Result of the delete operation
    """
    global emails_db
    original_count = len(emails_db)
    emails_db = [e for e in emails_db if e["id"] != email_id]

    if len(emails_db) < original_count:
        return {
            "success": True,
            "message": f"Email {email_id} deleted"
        }
    else:
        return {
            "success": False,
            "error": f"Email {email_id} not found"
        }


@mcp.tool()
def search_emails(query: str, field: str = "all") -> dict:
    """Search emails by query string

    Args:
        query: Search query
        field: Field to search in (subject, body, from, all)

    Returns:
        List of matching emails
    """
    query_lower = query.lower()
    results = []

    for email in emails_db:
        if field == "all":
            if (query_lower in email.get("subject", "").lower() or
                query_lower in email.get("body", "").lower() or
                query_lower in email.get("from", "").lower()):
                results.append(email)
        elif field in email and query_lower in email[field].lower():
            results.append(email)

    return {
        "success": True,
        "count": len(results),
        "results": results
    }


if __name__ == "__main__":
    # Run as streamable-HTTP server on port 8001
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8001)
