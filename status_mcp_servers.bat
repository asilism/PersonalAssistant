@echo off
REM Wrapper script to check MCP server status using Python
python status_mcp_servers.py
exit /b %ERRORLEVEL%
