@echo off
REM Wrapper script to start MCP servers using Python
python start_mcp_servers.py
exit /b %ERRORLEVEL%
