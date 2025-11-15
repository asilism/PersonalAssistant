#!/usr/bin/env python3
"""
Check status of all MCP servers
"""

import sys
import psutil
from pathlib import Path

# Configuration
PID_DIR = Path("logs/pids")

# MCP servers configuration
MCP_SERVERS = [
    "mail_agent",
    "calendar_agent",
    "calculator_agent",
    "jira_agent",
    "rpa_agent",
]


def is_process_running(pid):
    """Check if a process with given PID is running"""
    try:
        process = psutil.Process(pid)
        return process.is_running() and process.name() in ["python.exe", "python", "python3"]
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def get_process_info(pid):
    """Get process information"""
    try:
        process = psutil.Process(pid)
        info = {
            "cpu_percent": process.cpu_percent(interval=0.1),
            "memory_mb": process.memory_info().rss / 1024 / 1024,
            "create_time": process.create_time()
        }
        return info
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def check_server_status(server_name):
    """Check status of a single MCP server"""
    pid_file = PID_DIR / f"{server_name}.pid"

    if not pid_file.exists():
        return "not_started", None, None

    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
    except (ValueError, IOError):
        return "error", None, "Invalid PID file"

    if is_process_running(pid):
        info = get_process_info(pid)
        return "running", pid, info
    else:
        return "stopped", pid, "Stale PID file"


def format_uptime(create_time):
    """Format process uptime"""
    import time
    uptime_seconds = time.time() - create_time

    if uptime_seconds < 60:
        return f"{int(uptime_seconds)}s"
    elif uptime_seconds < 3600:
        return f"{int(uptime_seconds / 60)}m"
    elif uptime_seconds < 86400:
        hours = int(uptime_seconds / 3600)
        minutes = int((uptime_seconds % 3600) / 60)
        return f"{hours}h {minutes}m"
    else:
        days = int(uptime_seconds / 86400)
        hours = int((uptime_seconds % 86400) / 3600)
        return f"{days}d {hours}h"


def main():
    """Main function to check status of all MCP servers"""
    print("=" * 70)
    print("MCP Servers Status")
    print("=" * 70)
    print()

    if not PID_DIR.exists():
        print("No MCP servers have been started yet")
        return 0

    running = 0
    stopped = 0
    not_started = 0

    for server_name in MCP_SERVERS:
        status, pid, info = check_server_status(server_name)

        if status == "running":
            uptime = format_uptime(info["create_time"])
            cpu = info["cpu_percent"]
            mem = info["memory_mb"]
            print(f"[OK] {server_name:20} Running (PID: {pid:5}, Uptime: {uptime:8}, CPU: {cpu:5.1f}%, Mem: {mem:6.1f}MB)")
            running += 1
        elif status == "stopped":
            print(f"[ERROR] {server_name:20} Stopped ({info})")
            stopped += 1
        elif status == "not_started":
            print(f"[INFO] {server_name:20} Not started")
            not_started += 1
        else:
            print(f"[ERROR] {server_name:20} Error: {info}")
            stopped += 1

    print()
    print("=" * 70)
    print(f"Summary: {running} running, {stopped} stopped, {not_started} not started")
    print("=" * 70)
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
