@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Connect MCP to ChatGPT Web via VS Code

echo ======================================================================
echo    STARTING STANDALONE MCP BRIDGE (CHATGPT WEB ^<--^> LOCAL REPOS)
echo ======================================================================
echo.

:: 1. Locate Python Interpreter
set "PYTHON_EXE="
if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
) else if exist "C:\Development\chatgpt-mcp-server\venv\Scripts\python.exe" (
    set "PYTHON_EXE=C:\Development\chatgpt-mcp-server\venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

:: 2. Run Pre-flight Environment Doctor
echo [*] Running Environment Diagnostics...
"%PYTHON_EXE%" "%~dp0scripts\doctor.py"
echo.

:: 3. Launch MCP Server & Cloudflare Tunnel
echo [*] Launching MCP Server and Secure HTTPS Tunnel...
"%PYTHON_EXE%" "%~dp0scripts\tunnel.py" start
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to start tunnel or server.
    echo Check logs in "%~dp0runtime\"
    pause
    exit /b %ERRORLEVEL%
)

:: 4. Copy URL to Windows Clipboard if available
if exist "%~dp0runtime\tunnel.url" (
    set /p TUNNEL_URL=<"%~dp0runtime\tunnel.url"
    set "MCP_ENDPOINT=!TUNNEL_URL!/mcp"
    echo !MCP_ENDPOINT!| clip
    echo [COPIED] Streamable HTTP Endpoint copied to Clipboard:
    echo          !MCP_ENDPOINT!
    echo          (SSE Endpoint: !TUNNEL_URL!/sse)
)

echo.
echo ======================================================================
echo                     NEXT STEPS IN CHATGPT WEB
echo ======================================================================
echo 1. Open ChatGPT Web: https://chatgpt.com
echo 2. Go to Settings -^> Connected apps / Custom Actions / MCP Connectors
echo 3. Paste the copied endpoint URL: (Ctrl+V)
echo    - Streamable HTTP: !TUNNEL_URL!/mcp
echo    - SSE Transport:   !TUNNEL_URL!/sse
echo 4. Start chatting: "List my repositories and inspect the active project"
echo 5. View and edit local files in VS Code while ChatGPT works!
echo ======================================================================
echo.
echo (Keep this terminal open or run stop_all.bat when finished)
pause
