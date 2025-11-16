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

# Mock contacts database
contacts_db = [
    # Team members with Korean names
    {
        "id": "contact_1",
        "name": "김민지",
        "name_en": "Minji Kim",
        "email": "minji@samsung.com",
        "phone": "+82-10-1234-5678",
        "department": "Product Management",
        "position": "Product Manager",
        "company": "Samsung Electronics"
    },
    {
        "id": "contact_2",
        "name": "이하늘",
        "name_en": "Haneul Lee",
        "email": "haneul@samsung.com",
        "phone": "+82-10-2345-6789",
        "department": "Engineering",
        "position": "Senior Software Engineer",
        "company": "Samsung Electronics"
    },
    {
        "id": "contact_3",
        "name": "박지수",
        "name_en": "Jisu Park",
        "email": "jisu@samsung.com",
        "phone": "+82-10-3456-7890",
        "department": "Engineering",
        "position": "Software Engineer",
        "company": "Samsung Electronics"
    },
    {
        "id": "contact_4",
        "name": "최수빈",
        "name_en": "Soobin Choi",
        "email": "soobin@samsung.com",
        "phone": "+82-10-4567-8901",
        "department": "Management",
        "position": "Team Lead",
        "company": "Samsung Electronics"
    },
    {
        "id": "contact_5",
        "name": "정지호",
        "name_en": "Jiho Jung",
        "email": "jiho@samsung.com",
        "phone": "+82-10-5678-9012",
        "department": "Engineering",
        "position": "DevOps Engineer",
        "company": "Samsung Electronics"
    },
    {
        "id": "contact_6",
        "name": "김예은",
        "name_en": "Yeeun Kim",
        "email": "yeeun@samsung.com",
        "phone": "+82-10-6789-0123",
        "department": "Design",
        "position": "UX Designer",
        "company": "Samsung Electronics"
    },
    {
        "id": "contact_7",
        "name": "이서준",
        "name_en": "Seojun Lee",
        "email": "seojun@samsung.com",
        "phone": "+82-10-7890-1234",
        "department": "Marketing",
        "position": "Marketing Manager",
        "company": "Samsung Electronics"
    },
    {
        "id": "contact_8",
        "name": "박다은",
        "name_en": "Daeun Park",
        "email": "daeun@samsung.com",
        "phone": "+82-10-8901-2345",
        "department": "HR",
        "position": "HR Specialist",
        "company": "Samsung Electronics"
    },
    {
        "id": "contact_9",
        "name": "강민서",
        "name_en": "Minseo Kang",
        "email": "minseo@samsung.com",
        "phone": "+82-10-9012-3456",
        "department": "Engineering",
        "position": "QA Engineer",
        "company": "Samsung Electronics"
    },
    {
        "id": "contact_10",
        "name": "윤채원",
        "name_en": "Chaewon Yoon",
        "email": "chaewon@samsung.com",
        "phone": "+82-10-0123-4567",
        "department": "Product Management",
        "position": "Associate Product Manager",
        "company": "Samsung Electronics"
    },
    # Existing contacts from email database
    {
        "id": "contact_11",
        "name": "이성준",
        "name_en": "Sungjun Lee",
        "email": "sungjun87.lee@samsung.com",
        "phone": "+82-10-1111-2222",
        "department": "Engineering",
        "position": "Engineering Manager",
        "company": "Samsung Electronics"
    },
    {
        "id": "contact_12",
        "name": "박민호",
        "name_en": "Minho Park",
        "email": "minho.park@samsung.com",
        "phone": "+82-10-2222-3333",
        "department": "Engineering",
        "position": "Senior Software Engineer",
        "company": "Samsung Electronics"
    },
    {
        "id": "contact_13",
        "name": "최소연",
        "name_en": "Soyeon Choi",
        "email": "soyeon.choi@samsung.com",
        "phone": "+82-10-3333-4444",
        "department": "Design",
        "position": "Senior UX Designer",
        "company": "Samsung Electronics"
    },
    {
        "id": "contact_14",
        "name": "김재현",
        "name_en": "Jaehyun Kim",
        "email": "jaehyun.kim@samsung.com",
        "phone": "+82-10-4444-5555",
        "department": "Engineering",
        "position": "Software Engineer",
        "company": "Samsung Electronics"
    },
    # External contacts
    {
        "id": "contact_15",
        "name": "Client Team",
        "name_en": "Client Team",
        "email": "client@techcorp.com",
        "phone": "+82-2-1234-5678",
        "department": "Sales",
        "position": "Account Manager",
        "company": "TechCorp"
    },
    {
        "id": "contact_16",
        "name": "김영희",
        "name_en": "Younghee Kim",
        "email": "younghee@gkorea.kr",
        "phone": "+82-2-2345-6789",
        "department": "Partnerships",
        "position": "Partnership Manager",
        "company": "G Korea"
    },
    # Additional team members for comprehensive dataset
    {
        "id": "contact_17",
        "name": "송하윤",
        "name_en": "Hayoon Song",
        "email": "hayoon@samsung.com",
        "phone": "+82-10-5555-6666",
        "department": "Engineering",
        "position": "Backend Developer",
        "company": "Samsung Electronics"
    },
    {
        "id": "contact_18",
        "name": "조은우",
        "name_en": "Eunwoo Jo",
        "email": "eunwoo@samsung.com",
        "phone": "+82-10-6666-7777",
        "department": "Engineering",
        "position": "Frontend Developer",
        "company": "Samsung Electronics"
    },
    {
        "id": "contact_19",
        "name": "한지민",
        "name_en": "Jimin Han",
        "email": "jimin@samsung.com",
        "phone": "+82-10-7777-8888",
        "department": "Data Science",
        "position": "Data Scientist",
        "company": "Samsung Electronics"
    },
    {
        "id": "contact_20",
        "name": "안서현",
        "name_en": "Seohyun Ahn",
        "email": "seohyun@samsung.com",
        "phone": "+82-10-8888-9999",
        "department": "Security",
        "position": "Security Engineer",
        "company": "Samsung Electronics"
    }
]

# Mock email database
emails_db: list[dict] = [
    # Project Review related emails
    {
        "id": "email_1",
        "from": "sungjun87.lee@samsung.com",
        "to": "jaehyun.kim@samsung.com",
        "subject": "Project Review Meeting - November 11th",
        "body": "Hi Jaehyun,\n\nJust confirming our Project Review meeting scheduled for November 11th at 10:00 AM. Please prepare the Q4 progress report.\n\nBest regards,\nSungjun",
        "timestamp": "2025-11-08T09:30:00Z",
        "read": True
    },
    {
        "id": "email_2",
        "from": "minho.park@samsung.com",
        "to": "jaehyun.kim@samsung.com",
        "subject": "Re: Project Review Meeting Agenda",
        "body": "I'll be joining the Project Review meeting. Looking forward to discussing PROJ-1 progress.",
        "timestamp": "2025-11-09T14:20:00Z",
        "read": True
    },

    # Weekly meeting preparation emails
    {
        "id": "email_3",
        "from": "dev-team@samsung.com",
        "to": "jaehyun.kim@samsung.com",
        "subject": "Sprint Planning - November 12th",
        "body": "Sprint Planning meeting is scheduled for November 12th at 2:00 PM. Please review PROJ-1 and PROJ-4 status before the meeting.\n\nTopics:\n- User authentication implementation\n- Database connection pooling refactor",
        "timestamp": "2025-11-10T10:00:00Z",
        "read": False
    },
    {
        "id": "email_4",
        "from": "soyeon.choi@samsung.com",
        "to": "jaehyun.kim@samsung.com",
        "subject": "Design Review Materials - PROJ-2",
        "body": "Hi Jaehyun,\n\nI've prepared the UI/UX designs for the responsive login page (PROJ-2). Let's review them in our meeting on November 13th.\n\nAttached:\n- Mobile mockups\n- Tablet layouts\n- Desktop designs\n\nThanks,\nSoyeon",
        "timestamp": "2025-11-11T16:45:00Z",
        "read": False
    },

    # Team Sync and meeting invitation emails
    {
        "id": "email_5",
        "from": "jaehyun.kim@samsung.com",
        "to": "dev-team@samsung.com",
        "subject": "Team Sync - Weekly Standup",
        "body": "Hi team,\n\nOur weekly standup is scheduled for every Monday at 9:00 AM. Please come prepared with your updates.\n\nAgenda:\n- Last week's accomplishments\n- This week's goals\n- Blockers and concerns",
        "timestamp": "2025-11-07T08:00:00Z",
        "read": True,
        "sent": True
    },

    # Schedule conflict and meeting coordination
    {
        "id": "email_6",
        "from": "sungjun87.lee@samsung.com",
        "to": "jaehyun.kim@samsung.com",
        "subject": "Client Meeting Series - November 18th",
        "body": "Hi Jaehyun,\n\nWe have a series of client meetings scheduled for November 18th:\n- 9:00 AM - Initial presentation\n- 10:30 AM - Technical deep dive\n- 1:00 PM - Q&A session\n\nThis is almost 5 hours of continuous meetings. Please block your calendar.\n\nRegards,\nSungjun",
        "timestamp": "2025-11-12T11:30:00Z",
        "read": False
    },
    {
        "id": "email_7",
        "from": "client@techcorp.com",
        "to": "jaehyun.kim@samsung.com",
        "subject": "Looking forward to next week's meetings",
        "body": "Hello,\n\nThank you for scheduling the comprehensive meeting series next week. We have many questions about the authentication system and database architecture.\n\nSee you on the 18th!\n\nBest,\nClient Team",
        "timestamp": "2025-11-13T15:20:00Z",
        "read": False
    },

    # Weekly report and Jira completion emails
    {
        "id": "email_8",
        "from": "sungjun87.lee@samsung.com",
        "to": "jaehyun.kim@samsung.com",
        "subject": "Weekly Report Due - November 15th",
        "body": "Hi Jaehyun,\n\nPlease send me the weekly completion report by end of day Friday (Nov 15th). Include:\n- Completed Jira issues\n- Meeting summaries\n- Next week's priorities\n\nThanks,\nSungjun",
        "timestamp": "2025-11-13T09:00:00Z",
        "read": False
    },
    {
        "id": "email_9",
        "from": "jira-notifications@samsung.com",
        "to": "jaehyun.kim@samsung.com",
        "subject": "PROJ-7 Completed - Email notification system",
        "body": "[JIRA] Issue PROJ-7 has been completed by jaehyun.kim@samsung.com\n\nSummary: Implement email notification system\nStatus: Done\nCompleted: 2025-11-08 14:20\n\nGreat work!",
        "timestamp": "2025-11-08T14:25:00Z",
        "read": True
    },
    {
        "id": "email_10",
        "from": "minho.park@samsung.com",
        "to": "jaehyun.kim@samsung.com",
        "subject": "PROJ-6 Fixed - Memory leak resolved",
        "body": "Hi Jaehyun,\n\nI've successfully fixed the memory leak in the background worker (PROJ-6). The issue was with unclosed database connections. Performance is back to normal.\n\nClosed on: November 7th\nPriority: Critical\n\nLet me know if you need more details for the weekly report.\n\nMinho",
        "timestamp": "2025-11-07T17:30:00Z",
        "read": True
    },

    # Team Retrospective and completion discussions
    {
        "id": "email_11",
        "from": "dev-team@samsung.com",
        "to": "jaehyun.kim@samsung.com",
        "subject": "Team Retrospective - November 14th",
        "body": "Team Retrospective is scheduled for November 14th at 3:00 PM.\n\nWe'll discuss:\n- PROJ-5 (User profile page) - completed by Soyeon\n- PROJ-6 (Memory leak fix) - completed by Minho\n- What went well this sprint\n- What can be improved\n\nSee you there!",
        "timestamp": "2025-11-12T10:15:00Z",
        "read": False
    },
    {
        "id": "email_12",
        "from": "soyeon.choi@samsung.com",
        "to": "jaehyun.kim@samsung.com",
        "subject": "PROJ-5 Delivered - User Profile Page",
        "body": "Hi Jaehyun,\n\nHappy to report that PROJ-5 (User profile page with edit functionality) has been completed and deployed!\n\nCompleted: November 6th, 3:30 PM\nTesting: All tests passing\nDeployment: Production\n\nUsers can now edit their profiles with the new interface.\n\nSoyeon",
        "timestamp": "2025-11-06T15:45:00Z",
        "read": True
    },

    # Additional context emails for testing
    {
        "id": "email_13",
        "from": "hr@samsung.com",
        "to": "jaehyun.kim@samsung.com",
        "subject": "Reminder: Q4 Performance Review",
        "body": "This is a reminder that Q4 performance reviews are due by November 30th. Please complete your self-assessment in the HR portal.\n\nDeadline: November 30th, 2025",
        "timestamp": "2025-11-14T08:00:00Z",
        "read": False
    },
    {
        "id": "email_14",
        "from": "sungjun87.lee@samsung.com",
        "to": "jaehyun.kim@samsung.com",
        "subject": "Great work on PROJ-3",
        "body": "Hi Jaehyun,\n\nI noticed you're making good progress on the API documentation (PROJ-3). The updated docs are really helpful.\n\nKeep up the great work!\n\nSungjun",
        "timestamp": "2025-11-14T16:30:00Z",
        "read": False
    },
    {
        "id": "email_15",
        "from": "minho.park@samsung.com",
        "to": "jaehyun.kim@samsung.com",
        "subject": "Weekend Workshop - November 16th",
        "body": "Hey Jaehyun,\n\nAre you joining the weekend workshop on Saturday (Nov 16th) at 2 PM? We're doing a learning session on advanced TypeScript patterns.\n\nIt's optional but should be interesting!\n\nMinho",
        "timestamp": "2025-11-15T11:00:00Z",
        "read": False
    }
]


@mcp.tool()
def send_email(to: str | list[str], subject: str, body: str) -> dict:
    """Send an email to one or more recipients

    Args:
        to: Recipient email address. Use one of these formats:
            - Single recipient (str): "user@example.com"
            - Multiple recipients (list): ["user1@example.com", "user2@example.com", "user3@example.com"]
            IMPORTANT: For multiple recipients, use a JSON array, NOT a comma-separated string
        subject: Email subject
        body: Email body content

    Returns:
        Result of the send operation
    """
    # Normalize to list for uniform processing
    recipients = [to] if isinstance(to, str) else to

    # Validate that we have at least one recipient
    if not recipients:
        return {
            "success": False,
            "error": "Email validation failed: Email address is required"
        }

    # Validate and send to each recipient
    sent_emails = []
    errors = []

    for recipient in recipients:
        # Validate email address
        if not recipient:
            errors.append("Empty email address in recipient list")
            continue

        # Check for template variables
        template_pattern = r'\{\{.*?\}\}'
        if re.search(template_pattern, recipient):
            errors.append(f"Email address contains unresolved template variable: {recipient}")
            continue

        # Check email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, recipient.strip()):
            errors.append(f"Invalid email address format: {recipient}")
            continue

        # Block common placeholder/fake domains
        blocked_domains = [
            'example.com', 'example.org', 'example.net',
            'test.com', 'test.org', 'test.net',
            'sample.com', 'sample.org', 'sample.net',
            'placeholder.com', 'dummy.com', 'fake.com'
        ]
        email_domain = recipient.strip().split('@')[-1].lower()
        if email_domain in blocked_domains:
            errors.append(f"'{email_domain}' is a placeholder domain. Please provide a valid email address: {recipient}")
            continue

        # Create new email
        email_id = f"email_{len(emails_db) + 1}"
        new_email = {
            "id": email_id,
            "from": "jaehyun.kim@samsung.com",
            "to": recipient,
            "subject": subject,
            "body": body,
            "timestamp": datetime.now().isoformat(),
            "read": True,
            "sent": True
        }
        emails_db.append(new_email)
        sent_emails.append({
            "email_id": email_id,
            "to": recipient
        })

    # Return results
    if not sent_emails and errors:
        return {
            "success": False,
            "error": "Email validation failed: " + "; ".join(errors)
        }
    elif sent_emails and not errors:
        return {
            "success": True,
            "sent_count": len(sent_emails),
            "emails": sent_emails,
            "message": f"Email sent to {len(sent_emails)} recipient(s)",
            "subject": subject
        }
    else:  # Partial success
        return {
            "success": True,
            "sent_count": len(sent_emails),
            "emails": sent_emails,
            "message": f"Email sent to {len(sent_emails)} recipient(s), {len(errors)} failed",
            "subject": subject,
            "errors": errors
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


@mcp.tool()
def lookup_contact(query: str) -> dict:
    """Lookup contact information by name or email address

    This is a universal contact lookup tool that searches by:
    - Name (Korean or English, exact or partial match)
    - Email address

    Args:
        query: Person's name (e.g., "김민지", "Minji Kim") or email address (e.g., "minji@samsung.com")

    Returns:
        Contact details including name, email, phone, department, position if found

    Examples:
        - lookup_contact("김민지") -> Returns Minji Kim's full contact info
        - lookup_contact("Haneul") -> Returns Haneul Lee's contact info
        - lookup_contact("minji@samsung.com") -> Returns contact by email
    """
    query_lower = query.lower().strip()

    # Check if query is an email address
    if "@" in query:
        # Email search
        for contact in contacts_db:
            if query_lower == contact.get("email", "").lower():
                return {
                    "success": True,
                    "contact": contact,
                    "match_type": "email"
                }

        return {
            "success": False,
            "error": f"No contact found for email: {query}"
        }

    # Name search - try exact match first
    for contact in contacts_db:
        if (contact.get("name", "").lower() == query_lower or
            contact.get("name_en", "").lower() == query_lower):
            return {
                "success": True,
                "contact": contact,
                "match_type": "exact_name"
            }

    # Name search - try partial match
    for contact in contacts_db:
        if (query_lower in contact.get("name", "").lower() or
            query_lower in contact.get("name_en", "").lower()):
            return {
                "success": True,
                "contact": contact,
                "match_type": "partial_name"
            }

    return {
        "success": False,
        "error": f"No contact found for: {query}",
        "suggestion": "Please check the spelling or try a different name/email"
    }


if __name__ == "__main__":
    # Run as streamable-HTTP server on port 8001
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8001)
