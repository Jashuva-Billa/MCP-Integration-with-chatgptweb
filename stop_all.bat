@echo off
setlocal
cd /d "%~dp0"
title Stop Standalone MCP Servers

echo ======================================================================
echo          STOPPING ALL STANDALONE MCP SERVERS AND TUNNELS
echo ======================================================================

set "PYTHON_EXE="
if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
) else if exist "C:\Development\chatgpt-mcp-server\venv\Scripts\python.exe" (
    set "PYTHON_EXE=C:\Development\chatgpt-mcp-server\venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo [*] Stopping Cloudflare Tunnel...
"%PYTHON_EXE%" "%~dp0scripts\tunnel.py" stop

echo [*] Stopping MCP Server...
"%PYTHON_EXE%" "%~dp0scripts\start.py" stop

echo.
echo [OK] All MCP services have been safely stopped.
pause
