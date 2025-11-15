@echo off
REM Wrapper script to stop MCP servers using Python
python stop_mcp_servers.py
exit /b %ERRORLEVEL%
