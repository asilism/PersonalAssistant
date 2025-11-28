"""
Google Calendar OAuth Authentication Module

This module handles OAuth 2.0 authentication for Google Calendar API.
It supports both interactive (browser-based) and headless authentication flows.
"""

import os
import json
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# OAuth 2.0 scopes for Google Calendar
SCOPES = [
    "https://www.googleapis.com/auth/calendar",  # Full access to calendars
    "https://www.googleapis.com/auth/calendar.events",  # Access to events
]

# Default paths for credentials
DEFAULT_CREDENTIALS_DIR = Path.home() / ".config" / "personal-assistant"
DEFAULT_TOKEN_FILE = DEFAULT_CREDENTIALS_DIR / "google_calendar_token.json"
DEFAULT_CLIENT_SECRETS_FILE = DEFAULT_CREDENTIALS_DIR / "google_calendar_credentials.json"


def get_credentials(
    token_file: Optional[Path] = None,
    client_secrets_file: Optional[Path] = None,
    headless: bool = False,
) -> Optional[Credentials]:
    """
    Get valid Google Calendar API credentials.

    This function handles the OAuth 2.0 flow:
    1. Check for existing valid token
    2. Refresh expired token if possible
    3. Run OAuth flow if no valid token exists

    Args:
        token_file: Path to store the user's access token
        client_secrets_file: Path to the OAuth 2.0 client secrets file
        headless: If True, use console-based auth flow (for servers)

    Returns:
        Valid Credentials object, or None if authentication fails
    """
    token_file = token_file or DEFAULT_TOKEN_FILE
    client_secrets_file = client_secrets_file or DEFAULT_CLIENT_SECRETS_FILE

    # Ensure credentials directory exists
    token_file.parent.mkdir(parents=True, exist_ok=True)

    creds = None

    # Load existing token if available
    if token_file.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        except Exception as e:
            print(f"[WARNING] Failed to load existing token: {e}")
            creds = None

    # If no valid credentials, need to authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh expired token
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"[WARNING] Failed to refresh token: {e}")
                creds = None

        if not creds:
            # Need to run OAuth flow
            if not client_secrets_file.exists():
                print(f"[ERROR] Client secrets file not found: {client_secrets_file}")
                print("\nTo set up Google Calendar authentication:")
                print("1. Go to https://console.cloud.google.com/")
                print("2. Create or select a project")
                print("3. Enable the Google Calendar API")
                print("4. Create OAuth 2.0 credentials (Desktop app)")
                print(f"5. Download and save as: {client_secrets_file}")
                return None

            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(client_secrets_file), SCOPES
                )

                if headless:
                    # Console-based auth for headless environments
                    creds = flow.run_console()
                else:
                    # Browser-based auth
                    creds = flow.run_local_server(port=0)

            except Exception as e:
                print(f"[ERROR] OAuth flow failed: {e}")
                return None

        # Save the credentials for next time
        if creds:
            try:
                with open(token_file, "w") as f:
                    f.write(creds.to_json())
            except Exception as e:
                print(f"[WARNING] Failed to save token: {e}")

    return creds


def revoke_credentials(token_file: Optional[Path] = None) -> bool:
    """
    Revoke and delete stored credentials.

    Args:
        token_file: Path to the token file to revoke

    Returns:
        True if successfully revoked, False otherwise
    """
    token_file = token_file or DEFAULT_TOKEN_FILE

    if not token_file.exists():
        print("[INFO] No credentials to revoke")
        return True

    try:
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

        # Revoke the token with Google
        import requests
        requests.post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": creds.token},
            headers={"content-type": "application/x-www-form-urlencoded"}
        )

        # Delete the local token file
        token_file.unlink()
        print("[INFO] Credentials revoked successfully")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to revoke credentials: {e}")
        # Still try to delete the local file
        try:
            token_file.unlink()
        except:
            pass
        return False


def check_credentials_status(token_file: Optional[Path] = None) -> dict:
    """
    Check the status of stored credentials.

    Args:
        token_file: Path to the token file to check

    Returns:
        Dictionary with credential status information
    """
    token_file = token_file or DEFAULT_TOKEN_FILE

    status = {
        "token_exists": token_file.exists(),
        "token_path": str(token_file),
        "valid": False,
        "expired": None,
        "scopes": None,
    }

    if status["token_exists"]:
        try:
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
            status["valid"] = creds.valid
            status["expired"] = creds.expired if hasattr(creds, "expired") else None
            status["scopes"] = creds.scopes
        except Exception as e:
            status["error"] = str(e)

    return status
