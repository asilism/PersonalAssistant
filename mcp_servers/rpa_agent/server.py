#!/usr/bin/env python3
"""
RPA Agent MCP Server
Provides RPA automation tools: news search, report writing, attendance collection
"""

from datetime import datetime
from typing import Optional
from fastmcp import FastMCP

# Create FastMCP server
mcp = FastMCP("rpa-agent")

# Mock data stores
news_data = [
    # Technology News
    {
        "title": "AI Breakthrough in Natural Language Processing",
        "source": "Tech News Daily",
        "date": "2025-11-15",
        "summary": "Researchers announce major improvements in language model efficiency",
        "url": "https://technews.com/news/ai-breakthrough"
    },
    {
        "title": "New Productivity Tools Released",
        "source": "Business Today",
        "date": "2025-11-14",
        "summary": "Leading software companies unveil next-generation productivity suites",
        "url": "https://business.com/news/productivity-tools"
    },
    {
        "title": "Samsung Announces New Galaxy Series",
        "source": "Samsung Newsroom",
        "date": "2025-11-13",
        "summary": "Samsung unveils latest flagship smartphones with advanced AI features and enhanced camera systems",
        "url": "https://samsung.com/news/galaxy-series"
    },
    {
        "title": "Samsung Electronics Reports Strong Q4 Results",
        "source": "Financial Times",
        "date": "2025-11-12",
        "summary": "Samsung Electronics exceeds market expectations with record semiconductor sales",
        "url": "https://ft.com/samsung-q4-results"
    },
    {
        "title": "Quantum Computing Advances at Samsung Research",
        "source": "Science Daily",
        "date": "2025-11-11",
        "summary": "Samsung researchers make breakthrough in quantum chip design",
        "url": "https://sciencedaily.com/quantum-samsung"
    },
    # Business News
    {
        "title": "Global Tech Companies Focus on AI Integration",
        "source": "Bloomberg",
        "date": "2025-11-10",
        "summary": "Major technology firms increase investment in artificial intelligence platforms",
        "url": "https://bloomberg.com/ai-integration"
    },
    {
        "title": "Startup Ecosystem Thrives in South Korea",
        "source": "Korea Herald",
        "date": "2025-11-09",
        "summary": "Korean startups attract record foreign investment in tech sector",
        "url": "https://koreaherald.com/startup-ecosystem"
    },
    {
        "title": "Cloud Computing Market Expands Rapidly",
        "source": "Tech Crunch",
        "date": "2025-11-08",
        "summary": "Cloud service providers report 40% year-over-year growth",
        "url": "https://techcrunch.com/cloud-market"
    },
    # Product & Innovation News
    {
        "title": "Smart Home Devices Gain AI Capabilities",
        "source": "CNET",
        "date": "2025-11-07",
        "summary": "New generation of smart home devices feature advanced AI assistants",
        "url": "https://cnet.com/smart-home-ai"
    },
    {
        "title": "5G Network Coverage Reaches 90% in Major Cities",
        "source": "Telecom Today",
        "date": "2025-11-06",
        "summary": "Telecommunications providers achieve milestone in 5G deployment",
        "url": "https://telecomtoday.com/5g-coverage"
    },
    # Industry News
    {
        "title": "Semiconductor Industry Faces Supply Chain Challenges",
        "source": "Industry Week",
        "date": "2025-11-05",
        "summary": "Global chip manufacturers work to optimize production and distribution",
        "url": "https://industryweek.com/semiconductor-supply"
    },
    {
        "title": "Cybersecurity Threats Evolve with AI",
        "source": "Security Magazine",
        "date": "2025-11-04",
        "summary": "Security experts warn of AI-powered cyber attacks and develop countermeasures",
        "url": "https://securitymag.com/ai-threats"
    },
    {
        "title": "Green Technology Investment Surges",
        "source": "Environmental Tech",
        "date": "2025-11-03",
        "summary": "Companies increase spending on sustainable technology solutions",
        "url": "https://envtech.com/green-investment"
    },
    # Jira & Project Management News
    {
        "title": "Agile Methodology Adoption Increases",
        "source": "Project Management Today",
        "date": "2025-11-02",
        "summary": "More organizations embrace agile frameworks for software development",
        "url": "https://pmtoday.com/agile-adoption"
    },
    {
        "title": "Jira Releases New Automation Features",
        "source": "Atlassian Blog",
        "date": "2025-11-01",
        "summary": "Latest Jira update includes enhanced workflow automation and AI-powered issue tracking",
        "url": "https://atlassian.com/jira-automation"
    }
]

reports_db = []
attendance_db = {}


@mcp.tool()
def search_latest_news(topic: str, limit: int = 5) -> dict:
    """Search for the latest news articles on a topic

    Args:
        topic: Topic to search for
        limit: Maximum number of articles to return

    Returns:
        List of news articles
    """
    topic_lower = topic.lower()

    # Search news
    results = []
    for article in news_data:
        if (topic_lower in article["title"].lower() or
            topic_lower in article["summary"].lower()):
            results.append(article)

    # If no specific matches, return latest news
    if not results:
        results = news_data[:limit]
    else:
        results = results[:limit]

    return {
        "success": True,
        "topic": topic,
        "count": len(results),
        "articles": results
    }


@mcp.tool()
def write_report(
    title: str,
    sections: list[dict],
    author: str = "System",
    format: str = "markdown"
) -> dict:
    """Generate a formatted report based on provided data

    Args:
        title: Report title
        sections: Report sections (list of dicts with 'heading' and 'content')
        author: Report author
        format: Output format (markdown, html, text)

    Returns:
        The generated report
    """
    # Generate report
    report_id = f"report_{len(reports_db) + 1}"
    timestamp = datetime.now().isoformat()

    if format == "markdown":
        content = f"# {title}\n\n"
        content += f"**Author:** {author}\n"
        content += f"**Date:** {timestamp}\n\n"
        content += "---\n\n"
        for section in sections:
            content += f"## {section['heading']}\n\n"
            content += f"{section['content']}\n\n"

    elif format == "html":
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
        "format": format,
        "content": content,
        "created_at": timestamp
    }
    reports_db.append(report)

    return {
        "success": True,
        "report_id": report_id,
        "content": content,
        "format": format
    }


@mcp.tool()
def collect_attendance(
    event_name: str,
    action: str,
    attendee: Optional[str] = None,
    status: Optional[str] = None
) -> dict:
    """Collect and aggregate attendance responses from team members

    Args:
        event_name: Name of the event
        action: Action to perform (record, get_summary)
        attendee: Attendee email (required for 'record' action)
        status: Attendance status - attending, not_attending, maybe (required for 'record' action)

    Returns:
        Result of the attendance operation
    """
    if action == "record":
        if not attendee or not status:
            return {
                "success": False,
                "error": "attendee and status required for record action"
            }

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

        return {
            "success": True,
            "event_name": event_name,
            "attendee": attendee,
            "status": status,
            "message": "Attendance recorded"
        }

    elif action == "get_summary":
        # Get summary
        if event_name not in attendance_db:
            return {
                "success": True,
                "event_name": event_name,
                "summary": {
                    "attending": 0,
                    "not_attending": 0,
                    "maybe": 0,
                    "total_responses": 0
                },
                "responses": []
            }

        responses = attendance_db[event_name]
        summary = {
            "attending": sum(1 for r in responses if r["status"] == "attending"),
            "not_attending": sum(1 for r in responses if r["status"] == "not_attending"),
            "maybe": sum(1 for r in responses if r["status"] == "maybe"),
            "total_responses": len(responses)
        }

        return {
            "success": True,
            "event_name": event_name,
            "summary": summary,
            "responses": responses
        }

    return {
        "success": False,
        "error": f"Unknown action: {action}"
    }


if __name__ == "__main__":
    # Run as streamable-HTTP server on port 8005
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8005)
