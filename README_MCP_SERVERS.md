# MCP Servers 관리 가이드

PersonalAssistant는 여러 MCP (Model Context Protocol) 서버들을 사용합니다. 이 문서는 MCP 서버들을 관리하는 방법을 설명합니다.

## 사용 가능한 MCP 서버

1. **calculator_agent** - 수학 계산 기능
2. **calendar_agent** - 캘린더 관리 기능
3. **jira_agent** - Jira 이슈 관리 기능
4. **mail_agent** - 이메일 관리 기능
5. **rpa_agent** - RPA (Robotic Process Automation) 기능

## MCP 서버 관리 스크립트

### 전체 서버 시작
```bash
./start_mcp_servers.sh
```

모든 MCP 서버를 백그라운드에서 시작합니다.

### 전체 서버 중지
```bash
./stop_mcp_servers.sh
```

실행 중인 모든 MCP 서버를 중지합니다.

### 서버 상태 확인
```bash
./status_mcp_servers.sh
```

각 MCP 서버의 실행 상태를 확인합니다.

## 로그 확인

MCP 서버의 로그는 `logs/mcp/` 디렉토리에 저장됩니다:

```bash
# 특정 서버 로그 보기
tail -f logs/mcp/calculator_agent.log

# 모든 서버 로그 보기
tail -f logs/mcp/*.log
```

## 개별 서버 실행

특정 서버만 실행하고 싶다면:

```bash
cd mcp_servers/calculator_agent
python server.py
```

## 문제 해결

### 서버가 시작되지 않는 경우

1. 로그 파일 확인:
   ```bash
   cat logs/mcp/[server_name].log
   ```

2. PID 파일 정리:
   ```bash
   rm logs/pids/*.pid
   ```

3. 서버 재시작:
   ```bash
   ./stop_mcp_servers.sh
   ./start_mcp_servers.sh
   ```

### 포트 충돌

MCP 서버가 이미 사용 중인 포트에서 실행하려고 하면 실패할 수 있습니다.
로그를 확인하여 포트 충돌을 확인하고, 필요한 경우 서버 설정을 수정하세요.
