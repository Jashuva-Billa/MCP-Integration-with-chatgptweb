@echo off
setlocal
cd /d "%~dp0"
title Standalone MCP Server Status

set "PYTHON_EXE="
if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
) else if exist "C:\Development\chatgpt-mcp-server\venv\Scripts\python.exe" (
    set "PYTHON_EXE=C:\Development\chatgpt-mcp-server\venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" "%~dp0scripts\start.py" status
if exist "%~dp0runtime\tunnel.url" (
    set /p TUNNEL_URL=<"%~dp0runtime\tunnel.url"
    echo Public Tunnel:    !TUNNEL_URL!
    echo Streamable HTTP:  !TUNNEL_URL!/mcp
    echo SSE Endpoint:     !TUNNEL_URL!/sse
) else (
    echo Public Tunnel:    [STOPPED / NOT RUNNING]
)
echo.
pause
