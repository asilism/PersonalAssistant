#!/usr/bin/env python3
"""
Stop all MCP servers
"""

import sys
import time
import psutil
from pathlib import Path

# Configuration
PID_DIR = Path("logs/pids")


def is_process_running(pid):
    """Check if a process with given PID is running"""
    try:
        process = psutil.Process(pid)
        return process.is_running() and process.name() in ["python.exe", "python", "python3"]
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def stop_process(pid, timeout=5):
    """Stop a process gracefully, force kill if necessary"""
    try:
        process = psutil.Process(pid)

        # Try graceful termination first
        process.terminate()

        # Wait for process to terminate
        try:
            process.wait(timeout=timeout)
            return True
        except psutil.TimeoutExpired:
            # Force kill if graceful termination failed
            process.kill()
            process.wait(timeout=2)
            return True

    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        # Process already dead or no access
        return False


def stop_server(pid_file):
    """Stop a single MCP server"""
    server_name = pid_file.stem

    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
    except (ValueError, IOError) as e:
        print(f"[WARNING] {server_name}: Invalid PID file: {e}")
        pid_file.unlink()
        return False

    # Check if process is running
    if not is_process_running(pid):
        print(f"[WARNING] {server_name} is not running")
        pid_file.unlink()
        return False

    # Stop the process
    print(f"Stopping {server_name} (PID: {pid})...")

    try:
        if stop_process(pid):
            # Verify it's stopped
            time.sleep(0.5)
            if not is_process_running(pid):
                print(f"[OK] Stopped {server_name}")
                pid_file.unlink()
                return True
            else:
                print(f"[WARNING] Failed to stop {server_name}")
                return False
        else:
            print(f"[WARNING] {server_name} is not running")
            pid_file.unlink()
            return False

    except Exception as e:
        print(f"[ERROR] Failed to stop {server_name}: {e}")
        return False


def main():
    """Main function to stop all MCP servers"""
    print("=" * 40)
    print("Stopping MCP Servers")
    print("=" * 40)
    print()

    if not PID_DIR.exists():
        print("No MCP servers are running")
        return 0

    # Get all PID files
    pid_files = list(PID_DIR.glob("*.pid"))

    if not pid_files:
        print("No MCP servers are running")
        return 0

    success_count = 0
    fail_count = 0

    for pid_file in pid_files:
        if stop_server(pid_file):
            success_count += 1
        else:
            fail_count += 1

    print()
    print("=" * 40)
    print("All MCP Servers Stopped")
    print("=" * 40)
    print()
    print(f"Stopped: {success_count}/{len(pid_files)}")
    print(f"Failed: {fail_count}/{len(pid_files)}")
    print()

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
