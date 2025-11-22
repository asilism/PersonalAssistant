#!/usr/bin/env python3
"""
크로스 플랫폼 서버 시작 스크립트
Windows, Linux, macOS 모두 지원
"""

import os
import sys
import time
import subprocess
import platform
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
LOG_DIR = PROJECT_ROOT / "logs"

def is_windows():
    return platform.system() == "Windows"

def stop_existing_servers():
    """기존 서버 프로세스 종료"""
    print("Stopping existing servers...")

    if is_windows():
        # Windows
        processes = [
            "api_server.py",
            "calculator_agent",
            "mail_agent",
            "calendar_agent",
            "jira_agent",
            "rpa_agent"
        ]
        for proc in processes:
            subprocess.run(
                f'taskkill /F /FI "COMMANDLINE eq *{proc}*"',
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
    else:
        # Linux/macOS
        subprocess.run(
            "pkill -f 'api_server.py' || true",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        subprocess.run(
            "pkill -f 'calculator_agent.*server.py' || true",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        subprocess.run(
            "pkill -f 'mail_agent.*server.py' || true",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        subprocess.run(
            "pkill -f 'calendar_agent.*server.py' || true",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        subprocess.run(
            "pkill -f 'jira_agent.*server.py' || true",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        subprocess.run(
            "pkill -f 'rpa_agent.*server.py' || true",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    time.sleep(2)

def start_server(name, cwd, pythonpath, command, log_file):
    """서버 시작"""
    print(f"Starting {name}...")

    env = os.environ.copy()
    env['PYTHONPATH'] = str(pythonpath)

    log_path = LOG_DIR / log_file

    with open(log_path, 'w') as log:
        if is_windows():
            # Windows: CREATE_NEW_CONSOLE로 새 콘솔 창에서 실행
            subprocess.Popen(
                command,
                cwd=str(cwd),
                env=env,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            # Linux/macOS: nohup으로 백그라운드 실행
            subprocess.Popen(
                command,
                cwd=str(cwd),
                env=env,
                stdout=log,
                stderr=log,
                start_new_session=True
            )

    print(f"  {name} started")

def main():
    print("=" * 50)
    print("Starting all servers...")
    print("=" * 50)

    # 로그 디렉토리 생성
    LOG_DIR.mkdir(exist_ok=True)

    # 기존 서버 중지
    stop_existing_servers()

    # API 서버 시작
    start_server(
        name="API Server",
        cwd=PROJECT_ROOT,
        pythonpath=PROJECT_ROOT / "src",
        command=[sys.executable, "src/api_server.py"],
        log_file="api_server.log"
    )

    # Calculator Agent 시작
    calc_dir = PROJECT_ROOT / "mcp_servers" / "calculator_agent"
    start_server(
        name="Calculator Agent",
        cwd=calc_dir,
        pythonpath=calc_dir,
        command=[sys.executable, "server.py"],
        log_file="calculator_agent.log"
    )

    # Mail Agent 시작
    mail_dir = PROJECT_ROOT / "mcp_servers" / "mail_agent"
    start_server(
        name="Mail Agent",
        cwd=mail_dir,
        pythonpath=mail_dir,
        command=[sys.executable, "server.py"],
        log_file="mail_agent.log"
    )

    # Calendar Agent 시작
    cal_dir = PROJECT_ROOT / "mcp_servers" / "calendar_agent"
    start_server(
        name="Calendar Agent",
        cwd=cal_dir,
        pythonpath=cal_dir,
        command=[sys.executable, "server.py"],
        log_file="calendar_agent.log"
    )

    # Jira Agent 시작
    jira_dir = PROJECT_ROOT / "mcp_servers" / "jira_agent"
    start_server(
        name="Jira Agent",
        cwd=jira_dir,
        pythonpath=jira_dir,
        command=[sys.executable, "server.py"],
        log_file="jira_agent.log"
    )

    # RPA Agent 시작
    rpa_dir = PROJECT_ROOT / "mcp_servers" / "rpa_agent"
    start_server(
        name="RPA Agent",
        cwd=rpa_dir,
        pythonpath=rpa_dir,
        command=[sys.executable, "server.py"],
        log_file="rpa_agent.log"
    )

    # 서버 시작 대기
    print("\nWaiting for servers to start...")
    wait_time = 15 if is_windows() else 10
    print(f"Waiting {wait_time} seconds...")
    time.sleep(wait_time)

    print("\n" + "=" * 50)
    print("All servers started!")
    print("=" * 50)
    print(f"\nLogs are available in: {LOG_DIR}")
    print("\nTo run tests:")
    print(f"  cd {PROJECT_ROOT}")
    print("  python tests/e2e/test_frontend_questions.py")
    print("\nTo stop all servers:")
    if is_windows():
        print("  python tests/e2e/stop_servers.py")
    else:
        print("  ./tests/e2e/stop_all_servers.sh")
    print()

if __name__ == "__main__":
    main()
