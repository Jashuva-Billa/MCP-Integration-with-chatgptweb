@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Multi-Repo MCP Bridge - ChatGPT Web and VS Code

chcp 65001 >nul 2>&1

echo ==============================================================================
echo       MULTI-REPO MCP BRIDGE (CHATGPT WEB ^<---^> VS CODE ^<---^> LOCAL REPOS)
echo ==============================================================================
echo.

REM 1. Locate Python Interpreter
set "PYTHON_EXE="
if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

if not defined PYTHON_EXE (
    echo [ERROR] Python not found in virtual environment [venv] or system PATH.
    echo Please ensure Python 3.10+ is installed.
    pause
    exit /b 1
)

echo [*] Python Interpreter: %PYTHON_EXE%

REM 2. Pre-flight Environment Diagnostics
echo [*] Checking Environment and Repositories...
"%PYTHON_EXE%" "%~dp0scripts\doctor.py"
if %ERRORLEVEL% NEQ 0 (
    echo [!] Environment Doctor reported warnings. Proceeding with startup...
)

echo.
echo [*] Starting Local MCP Server and Cloudflare HTTPS Tunnel...
"%PYTHON_EXE%" "%~dp0scripts\tunnel.py" start
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to start MCP Server or Cloudflare Tunnel.
    echo Check logs in "%~dp0runtime\"
    pause
    exit /b %ERRORLEVEL%
)

REM 3. Read generated Public Tunnel URL and Copy to Clipboard
set "TUNNEL_URL="
if exist "%~dp0runtime\tunnel.url" (
    set /p TUNNEL_URL=<"%~dp0runtime\tunnel.url"
)

if defined TUNNEL_URL (
    set "MCP_HTTP=!TUNNEL_URL!/mcp"
    set "MCP_SSE=!TUNNEL_URL!/sse"
    echo !MCP_HTTP!| clip
    set "CLIP_STATUS=[COPIED TO CLIPBOARD]"
) else (
    set "MCP_HTTP=http://127.0.0.1:8766/mcp"
    set "MCP_SSE=http://127.0.0.1:8766/sse"
    set "CLIP_STATUS=[LOCAL ONLY]"
)

:MENU
cls
echo ==============================================================================
echo       MULTI-REPO MCP BRIDGE (CHATGPT WEB ^<---^> VS CODE ^<---^> LOCAL REPOS)
echo ==============================================================================
echo.
echo  ONLINE ENDPOINTS:
echo   - Streamable HTTP : !MCP_HTTP!  %CLIP_STATUS%
echo   - SSE Endpoint    : !MCP_SSE!
echo   - Local Server    : http://127.0.0.1:8766
echo   - Health Check    : http://127.0.0.1:8766/health
echo.
echo  CONNECTED LOCAL WORKSPACES:
echo   - interview-copilot : C:\Users\Jashuva\OneDrive\Desktop\interview-copilot
echo   - AI_jobs_apply     : C:\Users\Jashuva\OneDrive\Desktop\AI_jobs_apply
echo   - MCP Server        : C:\Users\Jashuva\OneDrive\Desktop\MCP
echo.
echo ==============================================================================
echo                                QUICK ACTIONS
echo ==============================================================================
echo  [1] Open ChatGPT Web in Browser
echo  [2] Open All Repositories in VS Code (Multi-Root Workspace)
echo  [3] Open Current MCP Project in VS Code
echo  [4] Run Full End-to-End Test Suite
echo  [5] Copy Streamable HTTP Endpoint to Clipboard again
echo  [6] Copy SSE Endpoint to Clipboard
echo  [7] Check Server and Tunnel Status
echo  [8] Stop All Services and Exit
echo  [9] Exit Launcher (Keep services running in background)
echo ==============================================================================
echo.
set /p CHOICE="Select an option [1-9] (Default: 1): "
if not defined CHOICE set "CHOICE=1"

if "%CHOICE%"=="1" (
    echo [*] Opening ChatGPT Web in default browser...
    start https://chatgpt.com
    echo.
    echo [*] Paste the copied URL into ChatGPT Connected Apps: !MCP_HTTP!
    echo.
    pause
    goto MENU
)

if "%CHOICE%"=="2" (
    echo [*] Launching VS Code Multi-Root Workspace...
    if exist "%~dp0multi-repo.code-workspace" (
        start "" code "%~dp0multi-repo.code-workspace"
    ) else (
        start "" code "%~dp0"
    )
    goto MENU
)

if "%CHOICE%"=="3" (
    echo [*] Launching VS Code for MCP project...
    start "" code "%~dp0"
    goto MENU
)

if "%CHOICE%"=="4" (
    echo [*] Running End-to-End Diagnostics...
    echo.
    "%PYTHON_EXE%" "%~dp0scripts\test_connection.py"
    echo.
    pause
    goto MENU
)

if "%CHOICE%"=="5" (
    echo !MCP_HTTP!| clip
    echo [OK] Copied Streamable HTTP to clipboard: !MCP_HTTP!
    timeout /t 2 >nul
    goto MENU
)

if "%CHOICE%"=="6" (
    echo !MCP_SSE!| clip
    echo [OK] Copied SSE to clipboard: !MCP_SSE!
    timeout /t 2 >nul
    goto MENU
)

if "%CHOICE%"=="7" (
    call "%~dp0status_all.bat"
    goto MENU
)

if "%CHOICE%"=="8" (
    call "%~dp0stop_all.bat"
    exit /b 0
)

if "%CHOICE%"=="9" (
    echo [*] Services are running in background.
    echo     Use status_all.bat to check health, or stop_all.bat to terminate.
    timeout /t 3 >nul
    exit /b 0
)

echo [!] Invalid selection.
timeout /t 1 >nul
goto MENU
