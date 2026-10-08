import os
import sys
import subprocess
import socket
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def check_python():
    v = sys.version_info
    print(f"[*] Python Version: {v.major}.{v.minor}.{v.micro} (Executable: {sys.executable})")
    if v.major < 3 or (v.major == 3 and v.minor < 10):
        print("    [!] ERROR: Python 3.10+ is required.")
        return False
    print("    [OK] Python version meets requirements.")
    return True

def check_dependencies():
    required = ["mcp", "starlette", "uvicorn", "pydantic", "pydantic_settings", "yaml", "pytest"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"    [!] Missing packages: {', '.join(missing)}")
        print("    Run: pip install -r requirements.txt")
        return False
    print("    [OK] All core Python dependencies are installed.")
    return True

def check_port(host="127.0.0.1", port=8766):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, port))
        s.close()
        print(f"    [OK] Port {port} is available.")
        return True
    except OSError:
        print(f"    [!] Port {port} is currently in use (an MCP server or other app might be running).")
        return False

def check_repositories_config():
    config_json = BASE_DIR / "config" / "repositories.json"
    config_yaml = BASE_DIR / "config" / "repositories.yaml"
    if config_json.exists():
        print(f"    [OK] Found repository registry: {config_json}")
        return True
    elif config_yaml.exists():
        print(f"    [OK] Found repository registry (YAML): {config_yaml}")
        return True
    else:
        print("    [!] Repositories configuration not found in config/. Creating from example...")
        example = BASE_DIR / "config" / "repositories.example.json"
        if example.exists():
            import shutil
            shutil.copy(example, config_json)
            print(f"    [OK] Created {config_json} from example.")
            return True
        return False

def check_cloudflared():
    try:
        out = subprocess.check_output("where.exe cloudflared", shell=True, text=True).strip()
        print(f"    [OK] Cloudflare Tunnel (cloudflared) detected at: {out.splitlines()[0]}")
        return True
    except Exception:
        print("    [NOTICE] Cloudflare Tunnel (cloudflared) not detected in PATH.")
        print("    To expose MCP to ChatGPT Web: winget install Cloudflare.cloudflared")
        return False

def run_doctor():
    print("=" * 65)
    print("        STANDALONE MCP SERVER ENVIRONMENT DOCTOR")
    print("=" * 65)
    p_ok = check_python()
    d_ok = check_dependencies()
    pt_ok = check_port(port=8766)
    r_ok = check_repositories_config()
    cf_ok = check_cloudflared()
    print("=" * 65)
    all_ok = p_ok and d_ok and r_ok
    if all_ok:
        print("  SYSTEM READY: Standalone MCP Server is ready to start.")
    else:
        print("  ATTENTION REQUIRED: Fix the warnings above before starting.")
    print("=" * 65)
    return all_ok

if __name__ == "__main__":
    run_doctor()
