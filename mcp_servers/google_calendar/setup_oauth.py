#!/usr/bin/env python3
"""
Google Calendar OAuth Setup CLI

This script helps set up Google Calendar API authentication.
Run this before using the Google Calendar MCP server.
"""

import argparse
import sys
from pathlib import Path

from auth import (
    get_credentials,
    revoke_credentials,
    check_credentials_status,
    DEFAULT_CLIENT_SECRETS_FILE,
    DEFAULT_TOKEN_FILE,
)


def setup_command(args):
    """Run the OAuth setup flow."""
    print("=" * 50)
    print("Google Calendar OAuth Setup")
    print("=" * 50)
    print()

    client_secrets = Path(args.client_secrets) if args.client_secrets else DEFAULT_CLIENT_SECRETS_FILE

    if not client_secrets.exists():
        print(f"[ERROR] Client secrets file not found: {client_secrets}")
        print()
        print("Please follow these steps to set up Google Calendar API:")
        print()
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a new project or select an existing one")
        print("3. Enable the Google Calendar API:")
        print("   - Go to 'APIs & Services' > 'Library'")
        print("   - Search for 'Google Calendar API'")
        print("   - Click 'Enable'")
        print("4. Create OAuth 2.0 credentials:")
        print("   - Go to 'APIs & Services' > 'Credentials'")
        print("   - Click 'Create Credentials' > 'OAuth client ID'")
        print("   - Application type: 'Desktop app'")
        print("   - Name: 'Personal Assistant'")
        print("   - Click 'Create'")
        print("5. Download the credentials JSON file")
        print(f"6. Save it as: {client_secrets}")
        print()
        return 1

    print(f"Client secrets file found: {client_secrets}")
    print()
    print("Starting OAuth flow...")
    print("A browser window will open for authentication.")
    print()

    token_file = Path(args.token) if args.token else DEFAULT_TOKEN_FILE

    creds = get_credentials(
        token_file=token_file,
        client_secrets_file=client_secrets,
        headless=args.headless,
    )

    if creds and creds.valid:
        print()
        print("[SUCCESS] Authentication completed!")
        print(f"Token saved to: {token_file}")
        print()
        print("You can now use the Google Calendar MCP server.")
        return 0
    else:
        print()
        print("[ERROR] Authentication failed.")
        return 1


def status_command(args):
    """Check authentication status."""
    print("=" * 50)
    print("Google Calendar Authentication Status")
    print("=" * 50)
    print()

    token_file = Path(args.token) if args.token else DEFAULT_TOKEN_FILE
    status = check_credentials_status(token_file)

    print(f"Token file: {status['token_path']}")
    print(f"Token exists: {status['token_exists']}")

    if status['token_exists']:
        print(f"Token valid: {status['valid']}")
        if status.get('expired') is not None:
            print(f"Token expired: {status['expired']}")
        if status.get('scopes'):
            print(f"Scopes: {', '.join(status['scopes'])}")
        if status.get('error'):
            print(f"Error: {status['error']}")
    else:
        print()
        print("No credentials found. Run 'setup' to authenticate.")

    return 0


def revoke_command(args):
    """Revoke authentication."""
    print("=" * 50)
    print("Revoke Google Calendar Authentication")
    print("=" * 50)
    print()

    token_file = Path(args.token) if args.token else DEFAULT_TOKEN_FILE

    if not token_file.exists():
        print("No credentials to revoke.")
        return 0

    confirm = input("Are you sure you want to revoke credentials? (y/N): ")
    if confirm.lower() != 'y':
        print("Cancelled.")
        return 0

    if revoke_credentials(token_file):
        print("Credentials revoked successfully.")
        return 0
    else:
        print("Failed to revoke credentials.")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Google Calendar OAuth Setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s setup                    # Run OAuth setup flow
  %(prog)s status                   # Check authentication status
  %(prog)s revoke                   # Revoke authentication

For first-time setup:
  1. Create OAuth credentials in Google Cloud Console
  2. Download the credentials JSON file
  3. Run: %(prog)s setup --client-secrets /path/to/credentials.json
        """,
    )

    parser.add_argument(
        "--token",
        help="Path to token file (default: ~/.config/personal-assistant/google_calendar_token.json)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Run OAuth setup flow")
    setup_parser.add_argument(
        "--client-secrets",
        help="Path to OAuth client secrets JSON file",
    )
    setup_parser.add_argument(
        "--headless",
        action="store_true",
        help="Use console-based auth flow (for headless environments)",
    )

    # Status command
    subparsers.add_parser("status", help="Check authentication status")

    # Revoke command
    subparsers.add_parser("revoke", help="Revoke authentication")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "setup":
        return setup_command(args)
    elif args.command == "status":
        return status_command(args)
    elif args.command == "revoke":
        return revoke_command(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
