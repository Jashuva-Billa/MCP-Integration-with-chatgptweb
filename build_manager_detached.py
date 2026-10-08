import os
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

# Windows process flags for detached background execution
DETACHED_PROCESS_FLAGS = 0x00000008 | 0x00000200 if os.name == "nt" else 0

def log_msg(msg: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    try:
        with open(STARTUP_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
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
                    config[k.strip()] = v.strip().strip("'\"")
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

def get_pid_listening_on_port(port: int) -> int:
    try:
        cmd = f'netstat -ano | findstr /R /C:":{port} .*LISTENING"'
        out = subprocess.check_output(cmd, shell=True, text=True).strip()
        for line in out.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and parts[3].upper() == "LISTENING":
                pid_str = parts[4]
                if pid_str.isdigit():
                    return int(pid_str)
    except Exception:
        pass
    return 0

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

def kill_pid_safely(pid: int, name: str):
    if is_pid_running(pid):
        log_msg(f"Stopping {name} (PID: {pid})...")
        subprocess.run(f"taskkill /PID {pid} /T /F", shell=True, capture_output=True)
        time.sleep(0.5)

def stop_process(pid_file: Path, name: str):
    if not pid_file.exists():
        return
    try:
        pid_str = pid_file.read_text(encoding="utf-8").strip()
        if pid_str.isdigit():
            pid = int(pid_str)
            kill_pid_safely(pid, name)
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
    current_pid = None

    if MCP_PID_FILE.exists():
        try:
            pid = int(MCP_PID_FILE.read_text(encoding="utf-8").strip())
            if is_pid_running(pid) and check_mcp_health(host, port):
                log_msg(f"[OK] MCP Server is already running (PID: {pid}) and healthy. Reusing instance.")
                server_running = True
                current_pid = pid
        except Exception:
            pass

    if not server_running:
        listening_pid = get_pid_listening_on_port(port)
        if listening_pid > 0 and check_mcp_health(host, port):
            log_msg(f"[WARNING] Port {port} is responding by PID {listening_pid}. Registering as MCP instance.")
            MCP_PID_FILE.write_text(str(listening_pid), encoding="utf-8")
            server_running = True
            current_pid = listening_pid
        else:
            log_msg(f"Launching MCP Server on http://{host}:{port}...")
            server_script = BASE_DIR / "run_server.py"
            
            mcp_log = open(MCP_LOG_FILE, "a", encoding="utf-8")
            proc = subprocess.Popen(
                [str(PYTHON_EXE), str(server_script)],
                cwd=str(BASE_DIR),
                stdout=mcp_log,
                stderr=subprocess.STDOUT,
                creationflags=DETACHED_PROCESS_FLAGS
            )
            current_pid = proc.pid
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
    tunnel_pid = None
    
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
                    tunnel_pid = tpid
            except Exception:
                pass

        if not tunnel_running:
            log_msg(f"Starting Cloudflare Tunnel to http://{host}:{port} using {cf_bin}...")
            try:
                with open(TUNNEL_LOG_FILE, "w", encoding="utf-8") as f:
                    f.write(f"--- Cloudflare Tunnel Started at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            except Exception:
                pass

            t_log = open(TUNNEL_LOG_FILE, "a", encoding="utf-8")
            tunnel_cmd = [cf_bin, "tunnel", "--url", f"http://{host}:{port}"]
            t_proc = subprocess.Popen(
                tunnel_cmd,
                cwd=str(BASE_DIR),
                stdout=t_log,
                stderr=subprocess.STDOUT,
                creationflags=DETACHED_PROCESS_FLAGS
            )
            tunnel_pid = t_proc.pid
            TUNNEL_PID_FILE.write_text(str(t_proc.pid), encoding="utf-8")
            log_msg(f"Cloudflare Tunnel process spawned (PID: {t_proc.pid}). Detecting public HTTPS URL...")

            url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
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

    print("\n" + "=" * 70)
    print("           STANDALONE MCP SERVER STATUS DASHBOARD")
    print("=" * 70)
    print(f"Project Root:    {BASE_DIR}")
    print(f"MCP Server:      [RUNNING] (PID: {current_pid or 'Active'})")
    print(f"Local URL:       http://{host}:{port}")
    print(f"Health Status:   [OK] http://{host}:{port}/health")
    if public_url:
        print(f"Tunnel Status:   [RUNNING] (PID: {tunnel_pid})")
        print(f"Public HTTPS:    {public_url}")
        print(f"MCP Endpoint:    {mcp_endpoint_url}")
    else:
        print(f"Tunnel Status:   [DISABLED / NOT INSTALLED]")
        print(f"Local Endpoint:  http://{host}:{port}{mcp_endpoint_suffix}")
    print("=" * 70)
    print("       READY FOR CHATGPT WEB / IDE CONNECTION")
    print("=" * 70 + "\n")
    return True

def stop_all():
    log_msg("Stopping all MCP services...")
    cfg = get_env_config()
    port = int(cfg["MCP_PORT"])

    # Stop tunnel
    stop_process(TUNNEL_PID_FILE, "Cloudflare Tunnel")
    
    # Stop MCP server from PID file
    stop_process(MCP_PID_FILE, "MCP Server")
    
    # Check if port 8000 still has listening process
    port_pid = get_pid_listening_on_port(port)
    if port_pid > 0:
        log_msg(f"Cleaning up listening process on port {port} (PID: {port_pid})...")
        kill_pid_safely(port_pid, "Port 8000 Listener")

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

    if not server_running:
        listening_pid = get_pid_listening_on_port(port)
        if listening_pid > 0 and check_mcp_health(host, port):
            server_running = True
            server_pid = str(listening_pid)

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

    print("\n" + "=" * 60)
    print("          MCP SERVER STATUS OVERVIEW")
    print("=" * 60)
    print(f"MCP Server:     {'[RUNNING]' if server_running else '[STOPPED]'} (PID: {server_pid})")
    print(f"Local Health:   {'[OK]' if healthy else '[FAILED / UNREACHABLE]'}")
    print(f"Local Port:     {port}")
    print(f"Tunnel:         {'[RUNNING]' if tunnel_running else '[STOPPED]'} (PID: {tunnel_pid})")
    print(f"Public URL:     {public_url}")
    if public_url != "None":
        print(f"MCP Endpoint:   {public_url}/sse")
    print("=" * 60 + "\n")

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
