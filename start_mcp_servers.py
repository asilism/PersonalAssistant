#!/usr/bin/env python3
"""
Start all MCP servers for Personal Assistant
This script launches all MCP servers in the background
"""

import os
import sys
import time
import subprocess
import psutil
from pathlib import Path

# Configuration
MCP_DIR = Path("mcp_servers")
LOG_DIR = Path("logs/mcp")
PID_DIR = Path("logs/pids")

# MCP servers configuration
MCP_SERVERS = {
    "mail_agent": {"port": 8001},
    "calendar_agent": {"port": 8002},
    "calculator_agent": {"port": 8003},
    "jira_agent": {"port": 8004},
    "rpa_agent": {"port": 8005},
    "contact_agent": {"port": 8006},
}


def ensure_directories():
    """Create log and PID directories if they don't exist"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PID_DIR.mkdir(parents=True, exist_ok=True)


def is_process_running(pid):
    """Check if a process with given PID is running"""
    try:
        process = psutil.Process(pid)
        return process.is_running() and process.name() in ["python.exe", "python", "python3"]
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def start_server(server_name, config):
    """Start a single MCP server"""
    server_path = MCP_DIR / server_name / "server.py"
    log_file = LOG_DIR / f"{server_name}.log"
    pid_file = PID_DIR / f"{server_name}.pid"

    # Check if server.py exists
    if not server_path.exists():
        print(f"[ERROR] {server_name}: server.py not found at {server_path}")
        return False

    # Check if already running
    if pid_file.exists():
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())

            if is_process_running(pid):
                print(f"[WARNING] {server_name} is already running (PID: {pid})")
                return False
            else:
                # Stale PID file, remove it
                pid_file.unlink()
        except (ValueError, IOError) as e:
            print(f"[WARNING] {server_name}: Invalid PID file, removing: {e}")
            pid_file.unlink()

    # Start the server
    try:
        with open(log_file, 'w') as log:
            # Use CREATE_NEW_PROCESS_GROUP on Windows to properly detach
            if sys.platform == 'win32':
                # Windows
                process = subprocess.Popen(
                    [sys.executable, "server.py"],
                    cwd=server_path.parent,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                    close_fds=False
                )
            else:
                # Unix-like
                process = subprocess.Popen(
                    [sys.executable, "server.py"],
                    cwd=server_path.parent,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True
                )

        pid = process.pid

        # Save PID to file
        with open(pid_file, 'w') as f:
            f.write(str(pid))

        # Wait a moment and check if process is still running
        time.sleep(1.5)

        if is_process_running(pid):
            print(f"[OK] Started {server_name} (PID: {pid}, Port: {config['port']})")
            return True
        else:
            print(f"[ERROR] Failed to start {server_name} - process died immediately")
            print(f"        Check log file: {log_file}")
            if pid_file.exists():
                pid_file.unlink()
            return False

    except Exception as e:
        print(f"[ERROR] Failed to start {server_name}: {e}")
        if pid_file.exists():
            pid_file.unlink()
        return False


def main():
    """Main function to start all MCP servers"""
    print("=" * 40)
    print("Starting MCP Servers")
    print("=" * 40)
    print()

    ensure_directories()

    print("Starting MCP servers...")
    print()

    success_count = 0
    fail_count = 0

    for server_name, config in MCP_SERVERS.items():
        if start_server(server_name, config):
            success_count += 1
        else:
            fail_count += 1

    print()
    print("=" * 40)
    print("MCP Servers Started")
    print("=" * 40)
    print()
    print(f"Started: {success_count}/{len(MCP_SERVERS)}")
    print(f"Failed: {fail_count}/{len(MCP_SERVERS)}")
    print()
    print(f"Log files: {LOG_DIR}/")
    print(f"PID files: {PID_DIR}/")
    print()
    print("To stop all servers, run: python stop_mcp_servers.py")
    print("To check server status, run: python status_mcp_servers.py")
    print()

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
