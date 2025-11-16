#!/usr/bin/env python3
"""
Contact Agent MCP Server
Provides contact lookup tools: search by name, get contact details
"""

from typing import Optional
from fastmcp import FastMCP

# Create FastMCP server
mcp = FastMCP("contact-agent")

# Mock contacts database
# Includes Korean names (both Korean and English) with Samsung email addresses
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


@mcp.tool()
def search_contacts(
    query: str,
    search_field: str = "all"
) -> dict:
    """Search for contacts by name, email, or other fields

    Args:
        query: Search query (supports Korean names, English names, or email)
        search_field: Field to search in (name, email, department, all)

    Returns:
        List of matching contacts
    """
    query_lower = query.lower().strip()
    results = []

    for contact in contacts_db:
        if search_field == "all":
            # Search in all fields
            searchable = [
                contact.get("name", ""),
                contact.get("name_en", ""),
                contact.get("email", ""),
                contact.get("department", ""),
                contact.get("position", "")
            ]
            if any(query_lower in field.lower() for field in searchable if field):
                results.append(contact)
        elif search_field == "name":
            # Search in both Korean and English names
            if (query_lower in contact.get("name", "").lower() or
                query_lower in contact.get("name_en", "").lower()):
                results.append(contact)
        elif search_field == "email":
            if query_lower in contact.get("email", "").lower():
                results.append(contact)
        elif search_field == "department":
            if query_lower in contact.get("department", "").lower():
                results.append(contact)

    return {
        "success": True,
        "query": query,
        "count": len(results),
        "contacts": results
    }


@mcp.tool()
def get_contact_by_name(name: str) -> dict:
    """Get contact details by exact or partial name match (supports Korean and English names)

    Args:
        name: Person's name (Korean or English)

    Returns:
        Contact details if found
    """
    name_lower = name.lower().strip()

    # Try exact match first
    for contact in contacts_db:
        if (contact.get("name", "").lower() == name_lower or
            contact.get("name_en", "").lower() == name_lower):
            return {
                "success": True,
                "contact": contact,
                "match_type": "exact"
            }

    # Try partial match
    for contact in contacts_db:
        if (name_lower in contact.get("name", "").lower() or
            name_lower in contact.get("name_en", "").lower()):
            return {
                "success": True,
                "contact": contact,
                "match_type": "partial"
            }

    return {
        "success": False,
        "error": f"No contact found for name: {name}",
        "suggestion": "Try searching with search_contacts for partial matches"
    }


@mcp.tool()
def get_contact_email(name: str) -> dict:
    """Get email address for a person by name (convenience function)

    Args:
        name: Person's name (Korean or English)

    Returns:
        Email address if contact found
    """
    result = get_contact_by_name(name)

    if result.get("success"):
        contact = result["contact"]
        return {
            "success": True,
            "name": name,
            "email": contact["email"],
            "name_ko": contact.get("name", ""),
            "name_en": contact.get("name_en", "")
        }
    else:
        return {
            "success": False,
            "error": f"No email found for name: {name}",
            "suggestion": "Please verify the name or use search_contacts to find similar names"
        }


@mcp.tool()
def list_all_contacts(department: Optional[str] = None) -> dict:
    """List all contacts, optionally filtered by department

    Args:
        department: Optional department filter

    Returns:
        List of contacts
    """
    if department:
        dept_lower = department.lower()
        filtered = [c for c in contacts_db if dept_lower in c.get("department", "").lower()]
        return {
            "success": True,
            "department": department,
            "count": len(filtered),
            "contacts": filtered
        }
    else:
        return {
            "success": True,
            "count": len(contacts_db),
            "contacts": contacts_db
        }


if __name__ == "__main__":
    # Run as streamable-HTTP server on port 8006
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8006)
