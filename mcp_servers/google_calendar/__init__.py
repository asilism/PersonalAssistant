"""
Google Calendar MCP Server

Provides real Google Calendar integration via the MCP protocol.
"""

from .auth import get_credentials, check_credentials_status, revoke_credentials

__all__ = ["get_credentials", "check_credentials_status", "revoke_credentials"]
