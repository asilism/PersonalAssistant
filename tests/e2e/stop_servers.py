#!/usr/bin/env python3
"""
크로스 플랫폼 서버 중지 스크립트
Windows, Linux, macOS 모두 지원
"""

import subprocess
import platform

def is_windows():
    return platform.system() == "Windows"

def stop_server(name, search_pattern):
    """서버 중지"""
    print(f"Stopping {name}...")

    try:
        if is_windows():
            # Windows
            result = subprocess.run(
                f'taskkill /F /FI "COMMANDLINE eq *{search_pattern}*"',
                shell=True,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print(f"  ✓ {name} stopped")
            else:
                print(f"  - {name} not running")
        else:
            # Linux/macOS
            result = subprocess.run(
                f"pkill -f '{search_pattern}'",
                shell=True,
                capture_output=True
            )
            if result.returncode == 0:
                print(f"  ✓ {name} stopped")
            else:
                print(f"  - {name} not running")
    except Exception as e:
        print(f"  - {name} not running (error: {e})")

def main():
    print("=" * 50)
    print("Stopping all servers...")
    print("=" * 50)

    # API 서버 중지
    stop_server("API Server", "api_server.py")

    # Calculator Agent 중지
    stop_server("Calculator Agent", "calculator_agent.*server.py")

    # Mail Agent 중지
    stop_server("Mail Agent", "mail_agent.*server.py")

    # Calendar Agent 중지
    stop_server("Calendar Agent", "calendar_agent.*server.py")

    # Jira Agent 중지
    stop_server("Jira Agent", "jira_agent.*server.py")

    # RPA Agent 중지
    stop_server("RPA Agent", "rpa_agent.*server.py")

    print("\n" + "=" * 50)
    print("All servers stopped!")
    print("=" * 50)

if __name__ == "__main__":
    main()
