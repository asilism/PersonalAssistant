#!/usr/bin/env python3
"""
Jira Agent MCP Server
Provides Jira issue management tools: create, read, update, delete, search
"""

from datetime import datetime
from typing import Optional
from fastmcp import FastMCP

# Create FastMCP server
mcp = FastMCP("jira-agent")

# Mock Jira issues database
issues_db: list[dict] = [
    # In Progress issues
    {
        "id": "PROJ-1",
        "key": "PROJ-1",
        "summary": "Implement user authentication",
        "description": "Add OAuth2 authentication to the application",
        "status": "In Progress",
        "priority": "High",
        "assignee": "minho.park@samsung.com",
        "reporter": "sungjun87.lee@samsung.com",
        "created_at": "2025-10-15T09:00:00Z",
        "updated_at": "2025-11-12T14:30:00Z"
    },
    {
        "id": "PROJ-2",
        "key": "PROJ-2",
        "summary": "Fix login page responsive design",
        "description": "Login page doesn't work well on mobile devices",
        "status": "To Do",
        "priority": "Medium",
        "assignee": "soyeon.choi@samsung.com",
        "reporter": "jaehyun.kim@samsung.com",
        "created_at": "2025-10-18T11:00:00Z",
        "updated_at": "2025-11-13T10:00:00Z"
    },
    {
        "id": "PROJ-3",
        "key": "PROJ-3",
        "summary": "Update API documentation",
        "description": "Document all REST API endpoints",
        "status": "In Progress",
        "priority": "Medium",
        "assignee": "jaehyun.kim@samsung.com",
        "reporter": "sungjun87.lee@samsung.com",
        "created_at": "2025-11-01T09:00:00Z",
        "updated_at": "2025-11-14T16:00:00Z"
    },
    {
        "id": "PROJ-4",
        "key": "PROJ-4",
        "summary": "Refactor database connection pooling",
        "description": "Improve database performance with better connection pooling",
        "status": "To Do",
        "priority": "High",
        "assignee": "minho.park@samsung.com",
        "reporter": "sungjun87.lee@samsung.com",
        "created_at": "2025-11-05T10:00:00Z",
        "updated_at": "2025-11-12T14:00:00Z"
    },
    # Completed issues from last week (2025-11-03 ~ 2025-11-09)
    {
        "id": "PROJ-5",
        "key": "PROJ-5",
        "summary": "Add user profile page",
        "description": "Create user profile page with edit functionality",
        "status": "Done",
        "priority": "High",
        "assignee": "soyeon.choi@samsung.com",
        "reporter": "jaehyun.kim@samsung.com",
        "created_at": "2025-10-28T09:00:00Z",
        "updated_at": "2025-11-06T15:30:00Z",
        "resolved_at": "2025-11-06T15:30:00Z"
    },
    {
        "id": "PROJ-6",
        "key": "PROJ-6",
        "summary": "Fix memory leak in background worker",
        "description": "Background worker process was consuming excessive memory",
        "status": "Done",
        "priority": "Critical",
        "assignee": "minho.park@samsung.com",
        "reporter": "sungjun87.lee@samsung.com",
        "created_at": "2025-10-30T11:00:00Z",
        "updated_at": "2025-11-07T17:00:00Z",
        "resolved_at": "2025-11-07T17:00:00Z"
    },
    {
        "id": "PROJ-7",
        "key": "PROJ-7",
        "summary": "Implement email notification system",
        "description": "Send email notifications for important events",
        "status": "Done",
        "priority": "Medium",
        "assignee": "jaehyun.kim@samsung.com",
        "reporter": "sungjun87.lee@samsung.com",
        "created_at": "2025-10-25T10:00:00Z",
        "updated_at": "2025-11-08T14:20:00Z",
        "resolved_at": "2025-11-08T14:20:00Z"
    },
    {
        "id": "PROJ-8",
        "key": "PROJ-8",
        "summary": "Upgrade dependencies to latest versions",
        "description": "Update all npm packages to latest stable versions",
        "status": "Done",
        "priority": "Low",
        "assignee": "minho.park@samsung.com",
        "reporter": "jaehyun.kim@samsung.com",
        "created_at": "2025-11-01T09:00:00Z",
        "updated_at": "2025-11-09T11:00:00Z",
        "resolved_at": "2025-11-09T11:00:00Z"
    }
]


@mcp.tool()
def create_issue(
    summary: str,
    description: str,
    priority: str = "Medium",
    assignee: str = "unassigned",
    issue_type: str = "Task"
) -> dict:
    """Create a new Jira issue

    Args:
        summary: Issue summary/title
        description: Issue description
        priority: Priority (Low, Medium, High, Critical)
        assignee: Assignee email
        issue_type: Issue type (Bug, Task, Story)

    Returns:
        The created issue
    """
    issue_num = len(issues_db) + 1
    issue_key = f"PROJ-{issue_num}"

    new_issue = {
        "id": issue_key,
        "key": issue_key,
        "summary": summary,
        "description": description,
        "status": "To Do",
        "priority": priority,
        "assignee": assignee,
        "reporter": "jaehyun.kim@samsung.com",
        "issue_type": issue_type,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    issues_db.append(new_issue)

    return {
        "success": True,
        "issue_key": issue_key,
        "issue": new_issue
    }


@mcp.tool()
def read_issue(issue_key: str) -> dict:
    """Read a specific Jira issue by key

    Args:
        issue_key: Issue key (e.g., PROJ-123)

    Returns:
        The issue if found
    """
    issue = next((i for i in issues_db if i["key"] == issue_key), None)

    if issue:
        return {
            "success": True,
            "issue": issue
        }
    else:
        return {
            "success": False,
            "error": f"Issue {issue_key} not found"
        }


@mcp.tool()
def update_issue(
    issue_key: str,
    summary: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assignee: Optional[str] = None
) -> dict:
    """Update an existing Jira issue

    Args:
        issue_key: Issue key
        summary: New summary
        description: New description
        status: New status (To Do, In Progress, Done, Blocked)
        priority: New priority
        assignee: New assignee

    Returns:
        The updated issue
    """
    issue = next((i for i in issues_db if i["key"] == issue_key), None)

    if issue:
        # Update fields if provided
        if summary is not None:
            issue["summary"] = summary
        if description is not None:
            issue["description"] = description
        if status is not None:
            issue["status"] = status
        if priority is not None:
            issue["priority"] = priority
        if assignee is not None:
            issue["assignee"] = assignee

        issue["updated_at"] = datetime.now().isoformat()

        return {
            "success": True,
            "issue": issue
        }
    else:
        return {
            "success": False,
            "error": f"Issue {issue_key} not found"
        }


@mcp.tool()
def delete_issue(issue_key: str) -> dict:
    """Delete a Jira issue

    Args:
        issue_key: Issue key to delete

    Returns:
        Result of the delete operation
    """
    global issues_db
    original_count = len(issues_db)
    issues_db = [i for i in issues_db if i["key"] != issue_key]

    if len(issues_db) < original_count:
        return {
            "success": True,
            "message": f"Issue {issue_key} deleted"
        }
    else:
        return {
            "success": False,
            "error": f"Issue {issue_key} not found"
        }


@mcp.tool()
def search_issues(
    query: str = "",
    status: Optional[str] = None,
    assignee: Optional[str] = None,
    priority: Optional[str] = None
) -> dict:
    """Search Jira issues by JQL-like query

    Args:
        query: Search query text
        status: Filter by status
        assignee: Filter by assignee
        priority: Filter by priority

    Returns:
        List of matching issues
    """
    query_lower = query.lower()
    results = []

    for issue in issues_db:
        # Text search
        if query and query_lower not in issue["summary"].lower() and query_lower not in issue["description"].lower():
            continue

        # Status filter
        if status and issue["status"] != status:
            continue

        # Assignee filter
        if assignee and issue["assignee"] != assignee:
            continue

        # Priority filter
        if priority and issue["priority"] != priority:
            continue

        results.append(issue)

    return {
        "success": True,
        "count": len(results),
        "issues": results
    }


if __name__ == "__main__":
    # Run as streamable-HTTP server on port 8004
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8004)
