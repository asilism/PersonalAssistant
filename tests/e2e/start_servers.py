#!/usr/bin/env python3
"""
크로스 플랫폼 서버 시작 스크립트 (헬스체크 포함)
Windows, Linux, macOS 모두 지원
"""

import os
import sys
import time
import subprocess
import platform
import requests
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

def check_server(url, name, max_retries=30, delay=1):
    """서버가 준비될 때까지 헬스체크"""
    print(f"Checking {name}...")

    for i in range(max_retries):
        try:
            response = requests.get(url, timeout=1)
            if response.status_code in [200, 404, 405]:  # 200 OK, 404/405도 서버 응답이므로 OK
                print(f"  ✓ {name} is ready")
                return True
        except requests.exceptions.RequestException:
            pass

        if i > 0 and i % 5 == 0:
            print(f"  Still waiting for {name}... ({i}/{max_retries})")

        time.sleep(delay)

    print(f"  ✗ {name} failed to start (timeout)")

    # 로그 출력
    log_file = LOG_DIR / f"{name.lower().replace(' ', '_')}.log"
    if log_file.exists():
        print(f"\n  Last 20 lines of {log_file}:")
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            for line in lines[-20:]:
                print(f"    {line.rstrip()}")

    return False

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

    # 헬스체크 - 서버가 실제로 준비될 때까지 대기
    print("\n" + "=" * 50)
    print("Health checking servers...")
    print("=" * 50)

    all_ready = True

    # API 서버 체크 (가장 중요)
    if not check_server("http://localhost:8000/api/health", "API Server", max_retries=30):
        all_ready = False

    # MCP 에이전트 체크
    if not check_server("http://localhost:8003/mcp", "Calculator Agent", max_retries=15):
        all_ready = False

    if not check_server("http://localhost:8001/mcp", "Mail Agent", max_retries=15):
        all_ready = False

    if not check_server("http://localhost:8002/mcp", "Calendar Agent", max_retries=15):
        all_ready = False

    if not check_server("http://localhost:8004/mcp", "Jira Agent", max_retries=15):
        all_ready = False

    if not check_server("http://localhost:8005/mcp", "RPA Agent", max_retries=15):
        all_ready = False

    print("\n" + "=" * 50)
    if all_ready:
        print("✓ All servers are ready!")
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
        return 0
    else:
        print("✗ Some servers failed to start!")
        print("=" * 50)
        print("\nPlease check the logs in:")
        print(f"  {LOG_DIR}")
        print("\nCommon issues:")
        print("  - Port already in use (kill existing processes)")
        print("  - Missing dependencies (pip install -r requirements.txt)")
        print("  - Python path issues")
        print()
        return 1

if __name__ == "__main__":
    sys.exit(main())
