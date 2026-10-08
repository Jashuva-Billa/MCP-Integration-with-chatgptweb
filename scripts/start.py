import os
import sys
import time
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
RUNTIME_DIR = BASE_DIR / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

PID_FILE = RUNTIME_DIR / "mcp_server.pid"
LOG_FILE = RUNTIME_DIR / "mcp_server.log"

PYTHON_EXE = Path(sys.executable)

def is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        cmd = f'tasklist /FI "PID eq {pid}" /NH'
        out = subprocess.check_output(cmd, shell=True, text=True)
        return str(pid) in out and "No tasks" not in out
    except Exception:
        return False

def check_health(host: str = "127.0.0.1", port: int = 8766) -> bool:
    url = f"http://{host}:{port}/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MCP-Doctor/1.0"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return resp.status == 200
    except Exception:
        return False

def start():
    from app.config import settings
    host = settings.MCP_HOST
    port = settings.MCP_PORT

    print(f"[*] Starting MCP Server on http://{host}:{port}...")

    # Check if already running
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text(encoding="utf-8").strip())
            if is_pid_running(pid) and check_health(host, port):
                print(f"[OK] MCP Server is already active and healthy (PID: {pid}).")
                return True
        except Exception:
            pass

    # Launch server
    main_script = BASE_DIR / "app" / "main.py"
    log_fp = open(LOG_FILE, "a", encoding="utf-8")
    
    detached_flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0
    proc = subprocess.Popen(
        [str(PYTHON_EXE), str(main_script)],
        cwd=str(BASE_DIR),
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        creationflags=detached_flags
    )
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    print(f"[*] Server spawned (PID: {proc.pid}). Waiting for health verification...")

    for _ in range(30):
        time.sleep(1)
        if check_health(host, port):
            print(f"[OK] MCP Server is running and healthy on http://{host}:{port}/health")
            print(f"[*] MCP Endpoint: http://{host}:{port}/sse (alias: /mcp)")
            return True
        if proc.poll() is not None:
            print(f"[ERROR] MCP Server exited prematurely with exit code {proc.returncode}.")
            print(f"Check logs in: {LOG_FILE}")
            return False

    print("[ERROR] Health check timed out after 30s.")
    return False

def stop():
    if not PID_FILE.exists():
        print("[*] No running MCP server PID found.")
        return
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        if is_pid_running(pid):
            print(f"[*] Terminating MCP Server (PID: {pid})...")
            subprocess.run(f"taskkill /PID {pid} /T /F", shell=True, capture_output=True)
            time.sleep(0.5)
            print("[OK] MCP Server stopped.")
        else:
            print(f"[*] MCP Server (PID: {pid}) was not active.")
    except Exception as e:
        print(f"[!] Error stopping server: {e}")
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()

def status():
    from app.config import settings
    host = settings.MCP_HOST
    port = settings.MCP_PORT
    running = False
    pid = "None"
    if PID_FILE.exists():
        try:
            p = int(PID_FILE.read_text(encoding="utf-8").strip())
            if is_pid_running(p):
                running = True
                pid = str(p)
        except Exception:
            pass
    healthy = check_health(host, port)
    print("=" * 55)
    print("           MCP SERVER RUNTIME STATUS")
    print("=" * 55)
    print(f"Status:       {'[RUNNING]' if running else '[STOPPED]'} (PID: {pid})")
    print(f"Health:       {'[OK]' if healthy else '[FAILED / UNREACHABLE]'}")
    print(f"Local URL:    http://{host}:{port}")
    print(f"Endpoint:     http://{host}:{port}/sse")
    print("=" * 55)

if __name__ == "__main__":
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "start"
    if action == "start":
        start()
    elif action == "stop":
        stop()
    elif action == "restart":
        stop()
        time.sleep(1)
        start()
    elif action == "status":
        status()
    else:
        print(f"Unknown action: {action}. Use: start, stop, restart, status.")
