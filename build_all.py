import os
from pathlib import Path

BASE_DIR = Path(r"C:\Development\chatgpt-mcp-server")
BASE_DIR.mkdir(parents=True, exist_ok=True)
(BASE_DIR / "scripts").mkdir(parents=True, exist_ok=True)
(BASE_DIR / "runtime").mkdir(parents=True, exist_ok=True)

files = {}

# 1. server/main.py
files["server/main.py"] = '''import logging
import sys
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

try:
    from mcp.server import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP

from server.config import config
from server.session import session_manager
from tools import workspace, filesystem, search, terminal, git

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("mcp_server")

# FastMCP application instance
mcp = FastMCP(
    name="Multi-Repo-Code-Agent-MCP",
    host=config.MCP_HOST,
    port=config.MCP_PORT
)

# Workspace Management Tools
mcp.tool()(workspace.list_repositories)
mcp.tool()(workspace.select_repository)
mcp.tool()(workspace.get_current_repository)
mcp.tool()(workspace.add_repository)
mcp.tool()(workspace.remove_repository)

# Filesystem Tools
mcp.tool()(filesystem.list_files)
mcp.tool()(filesystem.read_file)
mcp.tool()(filesystem.write_file)
mcp.tool()(filesystem.create_directory)
mcp.tool()(filesystem.delete_file)

# Search Tool
mcp.tool()(search.search_code)

# Terminal Tool
mcp.tool()(terminal.run_command)

# Git Tools
mcp.tool()(git.git_status)
mcp.tool()(git.git_diff)
mcp.tool()(git.git_branch)

# Health check route
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request):
    return JSONResponse({
        "status": "ok",
        "service": "chatgpt-mcp-server",
        "active_repository": session_manager.get_active_repo_name(),
        "host": config.MCP_HOST,
        "port": config.MCP_PORT
    })

class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow health checks without auth
        if request.url.path in ["/health", "/"]:
            return await call_next(request)

        if config.AUTH_TOKEN:
            auth_header = request.headers.get("Authorization", "")
            expected = f"Bearer {config.AUTH_TOKEN}"
            if not auth_header or auth_header.strip() != expected:
                logger.warning(f"Unauthorized request rejected from {request.client.host if request.client else 'unknown'}")
                return JSONResponse({"error": "Unauthorized. Invalid or missing Bearer token."}, status_code=401)

        return await call_next(request)

def start_server():
    logger.info("=" * 70)
    logger.info("Standalone Multi-Repository MCP Server Initializing")
    logger.info(f"Host: {config.MCP_HOST}:{config.MCP_PORT}")
    logger.info(f"Streamable HTTP & SSE Endpoint: http://{config.MCP_HOST}:{config.MCP_PORT}/sse")
    logger.info(f"Health Endpoint: http://{config.MCP_HOST}:{config.MCP_PORT}/health")
    logger.info(f"Authentication: {'ENABLED (Bearer Token required)' if config.AUTH_TOKEN else 'DISABLED (Local Dev Mode)'}")
    logger.info("=" * 70)
    mcp.run(transport="sse")

if __name__ == "__main__":
    start_server()
'''

# 2. .gitignore
files[".gitignore"] = """__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
.env
.venv/
venv/
runtime/
*.log
*.pid
*.url
.pytest_cache/
.coverage
htmlcov/
"""

# 3. .env.example
files[".env.example"] = """MCP_HOST=127.0.0.1
MCP_PORT=8000

# Optional custom path to cloudflared executable (Leave empty if in PATH)
CLOUDFLARED_PATH=

# Optional Bearer Token for remote access authentication (Leave blank for local dev)
AUTH_TOKEN=

# Tunnel operation mode (quick = trycloudflare.com)
TUNNEL_MODE=quick

# Operational & Security Limits
MAX_FILE_SIZE_BYTES=2097152
MAX_COMMAND_OUTPUT_BYTES=102400
COMMAND_TIMEOUT_SECONDS=120
"""

# 4. scripts/manage.py
files["scripts/manage.py"] = '''import os
import sys
import time
import re
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

MCP_PID_FILE = RUNTIME_DIR / "mcp_server.pid"
TUNNEL_PID_FILE = RUNTIME_DIR / "cloudflared.pid"
TUNNEL_URL_FILE = RUNTIME_DIR / "tunnel.url"
MCP_LOG_FILE = RUNTIME_DIR / "mcp_server.log"
TUNNEL_LOG_FILE = RUNTIME_DIR / "cloudflared.log"
STARTUP_LOG_FILE = RUNTIME_DIR / "startup.log"

PYTHON_EXE = BASE_DIR / "venv" / "Scripts" / "python.exe"
if not PYTHON_EXE.exists():
    PYTHON_EXE = Path(sys.executable)

def log_msg(msg: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    try:
        with open(STARTUP_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\\n")
    except Exception:
        pass

def get_env_config():
    env_file = BASE_DIR / ".env"
    config = {
        "MCP_HOST": "127.0.0.1",
        "MCP_PORT": "8000",
        "CLOUDFLARED_PATH": "",
        "AUTH_TOKEN": "",
        "TUNNEL_MODE": "quick"
    }
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    config[k.strip()] = v.strip().strip("\'\\"")
    return config

def is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        cmd = f'tasklist /FI "PID eq {pid}" /NH'
        out = subprocess.check_output(cmd, shell=True, text=True)
        return str(pid) in out and "No tasks" not in out
    except Exception:
        return False

def check_mcp_health(host: str, port: int, timeout: float = 2.0) -> bool:
    urls = [
        f"http://{host}:{port}/health",
        f"http://{host}:{port}/sse",
        f"http://{host}:{port}/mcp"
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MCP-HealthCheck/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status in [200, 307, 400, 405]:
                    return True
        except urllib.error.HTTPError as e:
            if e.code in [200, 307, 400, 401, 405]:
                return True
        except Exception:
            pass
    return False

def find_cloudflared_binary(custom_path: str = "") -> str:
    if custom_path and Path(custom_path).exists():
        return str(Path(custom_path).resolve())
    
    try:
        out = subprocess.check_output("where.exe cloudflared", shell=True, text=True).strip()
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        if lines:
            return lines[0]
    except Exception:
        pass
        
    common = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "cloudflared.exe",
        Path(os.environ.get("ProgramFiles", "")) / "cloudflared" / "cloudflared.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "cloudflared" / "cloudflared.exe",
        BASE_DIR / "cloudflared.exe"
    ]
    for p in common:
        if p.exists():
            return str(p)
            
    return ""

def stop_process(pid_file: Path, name: str):
    if not pid_file.exists():
        return
    try:
        pid_str = pid_file.read_text(encoding="utf-8").strip()
        if pid_str.isdigit():
            pid = int(pid_str)
            if is_pid_running(pid):
                log_msg(f"Stopping {name} (PID: {pid})...")
                subprocess.run(f"taskkill /PID {pid} /T /F", shell=True, capture_output=True)
                time.sleep(0.5)
            else:
                log_msg(f"{name} (PID: {pid}) was not running.")
    except Exception as e:
        log_msg(f"Error stopping {name}: {e}")
    finally:
        if pid_file.exists():
            try:
                pid_file.unlink()
            except Exception:
                pass

def start_server():
    cfg = get_env_config()
    host = cfg["MCP_HOST"]
    port = int(cfg["MCP_PORT"])

    log_msg("=" * 70)
    log_msg("STARTING STANDALONE MCP ENVIRONMENT")
    log_msg(f"Directory: {BASE_DIR}")
    log_msg("=" * 70)

    # 1. Check if MCP server is already running and healthy
    server_running = False
    if MCP_PID_FILE.exists():
        try:
            pid = int(MCP_PID_FILE.read_text(encoding="utf-8").strip())
            if is_pid_running(pid) and check_mcp_health(host, port):
                log_msg(f"[OK] MCP Server is already running (PID: {pid}) and healthy. Reusing instance.")
                server_running = True
        except Exception:
            pass

    if not server_running:
        if check_mcp_health(host, port):
            log_msg(f"[WARNING] Port {port} is already responding. Assuming existing MCP server instance.")
            server_running = True
        else:
            log_msg(f"Launching MCP Server on http://{host}:{port}...")
            server_script = BASE_DIR / "run_server.py"
            
            mcp_log = open(MCP_LOG_FILE, "a", encoding="utf-8")
            proc = subprocess.Popen(
                [str(PYTHON_EXE), str(server_script)],
                cwd=str(BASE_DIR),
                stdout=mcp_log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            )
            MCP_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
            log_msg(f"MCP Server process spawned (PID: {proc.pid}). Waiting for health check...")

            healthy = False
            for i in range(30):
                time.sleep(1)
                if check_mcp_health(host, port):
                    healthy = True
                    break
                if proc.poll() is not None:
                    log_msg(f"[FATAL] MCP Server process exited prematurely with code {proc.returncode}.")
                    log_msg(f"Check logs at: {MCP_LOG_FILE}")
                    return False

            if not healthy:
                log_msg("[FATAL] MCP SERVER FAILED TO START - Health check timed out after 30s.")
                log_msg(f"Check diagnostics in: {MCP_LOG_FILE}")
                stop_process(MCP_PID_FILE, "MCP Server")
                return False

            log_msg(f"[OK] MCP Server is healthy and responding on http://{host}:{port}")

    # 2. Check and start Cloudflare Tunnel
    cf_bin = find_cloudflared_binary(cfg.get("CLOUDFLARED_PATH", ""))
    public_url = ""
    
    if not cf_bin:
        log_msg("-" * 70)
        log_msg("[NOTICE] Cloudflare Tunnel (cloudflared) was not detected on this system.")
        log_msg("The local MCP Server is active and accessible locally.")
        log_msg("To enable secure remote connectivity from ChatGPT Web:")
        log_msg("  1. Install cloudflared via Windows Terminal: winget install Cloudflare.cloudflared")
        log_msg("  2. Or download cloudflared.exe and specify CLOUDFLARED_PATH in .env")
        log_msg("-" * 70)
    else:
        tunnel_running = False
        if TUNNEL_PID_FILE.exists() and TUNNEL_URL_FILE.exists():
            try:
                tpid = int(TUNNEL_PID_FILE.read_text(encoding="utf-8").strip())
                if is_pid_running(tpid):
                    public_url = TUNNEL_URL_FILE.read_text(encoding="utf-8").strip()
                    log_msg(f"[OK] Reusing active Cloudflare Tunnel (PID: {tpid}) -> {public_url}")
                    tunnel_running = True
            except Exception:
                pass

        if not tunnel_running:
            log_msg(f"Starting Cloudflare Tunnel to http://{host}:{port} using {cf_bin}...")
            try:
                with open(TUNNEL_LOG_FILE, "w", encoding="utf-8") as f:
                    f.write(f"--- Cloudflare Tunnel Started at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\\n")
            except Exception:
                pass

            t_log = open(TUNNEL_LOG_FILE, "a", encoding="utf-8")
            tunnel_cmd = [cf_bin, "tunnel", "--url", f"http://{host}:{port}"]
            t_proc = subprocess.Popen(
                tunnel_cmd,
                cwd=str(BASE_DIR),
                stdout=t_log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            )
            TUNNEL_PID_FILE.write_text(str(t_proc.pid), encoding="utf-8")
            log_msg(f"Cloudflare Tunnel process spawned (PID: {t_proc.pid}). Detecting public HTTPS URL...")

            url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\\.trycloudflare\\.com")
            for _ in range(60):
                time.sleep(1)
                if TUNNEL_LOG_FILE.exists():
                    try:
                        content = TUNNEL_LOG_FILE.read_text(encoding="utf-8", errors="ignore")
                        match = url_pattern.search(content)
                        if match:
                            public_url = match.group(0)
                            TUNNEL_URL_FILE.write_text(public_url, encoding="utf-8")
                            break
                    except Exception:
                        pass
                if t_proc.poll() is not None:
                    log_msg(f"[ERROR] Cloudflare tunnel process stopped unexpectedly with code {t_proc.returncode}.")
                    break

            if not public_url:
                log_msg("[WARNING] Could not automatically detect public trycloudflare.com URL within 60s.")
                log_msg(f"Inspect tunnel logs: {TUNNEL_LOG_FILE}")
            else:
                log_msg(f"[OK] Public HTTPS URL detected: {public_url}")

    # 3. Print Final Status Dashboard
    mcp_endpoint_suffix = "/sse"
    mcp_endpoint_url = f"{public_url}{mcp_endpoint_suffix}" if public_url else f"http://{host}:{port}{mcp_endpoint_suffix}"

    print("\\n" + "=" * 70)
    print("           STANDALONE MCP SERVER STATUS DASHBOARD")
    print("=" * 70)
    print(f"Project Root:    {BASE_DIR}")
    print(f"MCP Server:      [RUNNING]")
    print(f"Local URL:       http://{host}:{port}")
    print(f"Health Status:   [OK] http://{host}:{port}/health")
    if public_url:
        print(f"Tunnel Status:   [RUNNING]")
        print(f"Public HTTPS:    {public_url}")
        print(f"MCP Endpoint:    {mcp_endpoint_url}")
    else:
        print(f"Tunnel Status:   [DISABLED / NOT INSTALLED]")
        print(f"Local Endpoint:  http://{host}:{port}{mcp_endpoint_suffix}")
    print("=" * 70)
    print("       READY FOR CHATGPT WEB / IDE CONNECTION")
    print("=" * 70 + "\\n")
    return True

def stop_all():
    log_msg("Stopping all MCP services...")
    stop_process(TUNNEL_PID_FILE, "Cloudflare Tunnel")
    stop_process(MCP_PID_FILE, "MCP Server")
    if TUNNEL_URL_FILE.exists():
        try:
            TUNNEL_URL_FILE.unlink()
        except Exception:
            pass
    log_msg("All services stopped.")

def show_status():
    cfg = get_env_config()
    host = cfg["MCP_HOST"]
    port = int(cfg["MCP_PORT"])

    server_running = False
    server_pid = "None"
    if MCP_PID_FILE.exists():
        try:
            pid = int(MCP_PID_FILE.read_text(encoding="utf-8").strip())
            if is_pid_running(pid):
                server_running = True
                server_pid = str(pid)
        except Exception:
            pass

    healthy = check_mcp_health(host, port)

    tunnel_running = False
    tunnel_pid = "None"
    public_url = "None"
    if TUNNEL_PID_FILE.exists():
        try:
            tpid = int(TUNNEL_PID_FILE.read_text(encoding="utf-8").strip())
            if is_pid_running(tpid):
                tunnel_running = True
                tunnel_pid = str(tpid)
                if TUNNEL_URL_FILE.exists():
                    public_url = TUNNEL_URL_FILE.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    print("\\n" + "=" * 60)
    print("          MCP SERVER STATUS OVERVIEW")
    print("=" * 60)
    print(f"MCP Server:     {'[RUNNING]' if server_running else '[STOPPED]'} (PID: {server_pid})")
    print(f"Local Health:   {'[OK]' if healthy else '[FAILED / UNREACHABLE]'}")
    print(f"Local Port:     {port}")
    print(f"Tunnel:         {'[RUNNING]' if tunnel_running else '[STOPPED]'} (PID: {tunnel_pid})")
    print(f"Public URL:     {public_url}")
    if public_url != "None":
        print(f"MCP Endpoint:   {public_url}/sse")
    print("=" * 60 + "\\n")

if __name__ == "__main__":
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "start"
    if action == "start":
        start_server()
    elif action == "stop":
        stop_all()
    elif action == "restart":
        stop_all()
        time.sleep(1)
        start_server()
    elif action == "status":
        show_status()
    elif action == "test":
        show_status()
    else:
        print(f"Unknown action: {action}. Use start, stop, restart, status, or test.")
'''

# 5. start_mcp.bat
files["start_mcp.bat"] = """@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Standalone MCP Server - Control Center

echo ======================================================================
echo           INITIALIZING STANDALONE MULTI-REPO MCP SERVER
echo ======================================================================

:: 1. Verify Virtual Environment
if not exist "%~dp0venv\\Scripts\\python.exe" (
    echo [ERROR] Python virtual environment was not found at:
    echo "%~dp0venv\\Scripts\\python.exe"
    echo.
    echo Please initialize the environment:
    echo   cd /d "%~dp0"
    echo   python -m venv venv
    echo   .\\venv\\Scripts\\activate
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

:: 2. Launch Startup Manager
"%~dp0venv\\Scripts\\python.exe" "%~dp0scripts\\manage.py" start
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [FATAL] MCP Startup routine encountered an error.
    echo Check logs in "%~dp0runtime\\startup.log"
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Press any key to close this launcher window (Server will remain active in background).
pause >nul
"""

# 6. stop_mcp.bat
files["stop_mcp.bat"] = """@echo off
setlocal
cd /d "%~dp0"
title Standalone MCP Server - Stop

echo Stopping Standalone MCP Server and associated tunnels...
if exist "%~dp0venv\\Scripts\\python.exe" (
    "%~dp0venv\\Scripts\\python.exe" "%~dp0scripts\\manage.py" stop
) else (
    python "%~dp0scripts\\manage.py" stop
)
echo.
pause
"""

# 7. restart_mcp.bat
files["restart_mcp.bat"] = """@echo off
setlocal
cd /d "%~dp0"
title Standalone MCP Server - Restart

echo Restarting Standalone MCP Server...
if exist "%~dp0venv\\Scripts\\python.exe" (
    "%~dp0venv\\Scripts\\python.exe" "%~dp0scripts\\manage.py" restart
) else (
    python "%~dp0scripts\\manage.py" restart
)
echo.
pause
"""

# 8. status_mcp.bat
files["status_mcp.bat"] = """@echo off
setlocal
cd /d "%~dp0"
title Standalone MCP Server - Status

if exist "%~dp0venv\\Scripts\\python.exe" (
    "%~dp0venv\\Scripts\\python.exe" "%~dp0scripts\\manage.py" status
) else (
    python "%~dp0scripts\\manage.py" status
)
echo.
pause
"""

# 9. test_mcp_connection.bat
files["test_mcp_connection.bat"] = """@echo off
setlocal
cd /d "%~dp0"
title Standalone MCP Server - Connection Test

echo Testing MCP Server and Tunnel Status...
if exist "%~dp0venv\\Scripts\\python.exe" (
    "%~dp0venv\\Scripts\\python.exe" "%~dp0scripts\\manage.py" test
) else (
    python "%~dp0scripts\\manage.py" test
)
echo.
pause
"""

# 10. tests/test_launcher.py
files["tests/test_launcher.py"] = '''import pytest
from pathlib import Path
from scripts.manage import (
    get_env_config,
    is_pid_running,
    find_cloudflared_binary,
    check_mcp_health,
    BASE_DIR,
    RUNTIME_DIR
)

def test_launcher_env_config():
    cfg = get_env_config()
    assert "MCP_HOST" in cfg
    assert "MCP_PORT" in cfg
    assert int(cfg["MCP_PORT"]) > 0

def test_launcher_runtime_dir():
    assert RUNTIME_DIR.exists()
    assert RUNTIME_DIR.is_dir()

def test_is_pid_running_invalid():
    assert is_pid_running(-1) is False
    assert is_pid_running(9999999) is False

def test_find_cloudflared_custom_nonexistent():
    res = find_cloudflared_binary("C:\\\\NonExistentPath\\\\cloudflared.exe")
    assert res == ""
'''

# Write all files
for rel_path, content in files.items():
    dest = BASE_DIR / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created: {dest}")

print("All one-click startup and launcher files successfully installed.")
