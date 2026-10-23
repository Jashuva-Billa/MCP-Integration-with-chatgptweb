import os
import sys
import time
import re
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
RUNTIME_DIR = BASE_DIR / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

TUNNEL_PID_FILE = RUNTIME_DIR / "cloudflared.pid"
TUNNEL_URL_FILE = RUNTIME_DIR / "tunnel.url"
TUNNEL_LOG_FILE = RUNTIME_DIR / "cloudflared.log"

def find_cloudflared() -> str:
    from app.config import settings
    if settings.CLOUDFLARED_PATH and Path(settings.CLOUDFLARED_PATH).exists():
        return str(Path(settings.CLOUDFLARED_PATH).resolve())
    try:
        out = subprocess.check_output("where.exe cloudflared", shell=True, text=True).strip()
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        if lines:
            return lines[0]
    except Exception:
        pass
    return ""

def find_ngrok() -> str:
    try:
        out = subprocess.check_output("where.exe ngrok", shell=True, text=True).strip()
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        if lines:
            return lines[0]
    except Exception:
        pass
    return ""

def public_tunnel_auth_error(auth_enabled: bool, token: str) -> str:
    """Return a safe-to-display error when public tunnel auth is not configured."""
    if not auth_enabled:
        return "Public tunnels require MCP_AUTH_ENABLED=true in your .env file."
    if len((token or "").strip()) < 32:
        return (
            "Public tunnels require MCP_AUTH_TOKEN to contain at least 32 non-whitespace "
            "characters. Generate a token with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    return ""


def start_tunnel():
    from app.config import settings
    from scripts.start import check_health, start as start_server

    host = settings.MCP_HOST
    port = settings.MCP_PORT

    # 1. Always start the local MCP server first (regardless of auth/tunnel config)
    if not check_health(host, port):
        print("[*] Local MCP Server is not running. Launching local server...")
        if not start_server():
            print("[ERROR] Could not start local MCP server. Aborting.")
            return False
    else:
        print(f"[OK] Local MCP Server already healthy on http://{host}:{port}")

    # 2. Check auth before exposing via a public tunnel
    if settings.MCP_AUTH_ENABLED:
        auth_error = public_tunnel_auth_error(settings.MCP_AUTH_ENABLED, settings.MCP_AUTH_TOKEN)
        if auth_error:
            print(f"[WARNING] Public tunnel skipped (auth not configured): {auth_error}")
            print(f"[OK] MCP Server is running locally: http://{host}:{port}/mcp")
            TUNNEL_URL_FILE.write_text(f"http://{host}:{port}", encoding="utf-8")
            return True
    else:
        print("[*] Authentication disabled (MCP_AUTH_ENABLED=false) — compatible with ChatGPT 'No authentication' mode.")

    if TUNNEL_URL_FILE.exists():
        TUNNEL_URL_FILE.unlink()

    detached_flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0
    log_fp = open(TUNNEL_LOG_FILE, "w", encoding="utf-8")
    public_url = ""

    # Mode A: Permanent Cloudflare Named Tunnel via Token
    if settings.TUNNEL_MODE.lower() != "ngrok" and settings.CLOUDFLARE_TUNNEL_TOKEN:
        cf_bin = find_cloudflared()
        if not cf_bin:
            print("[ERROR] cloudflared not found for Cloudflare Named Tunnel.")
            return False
        print(f"[*] Starting Permanent Cloudflare Named Tunnel using token...")
        cmd = [cf_bin, "tunnel", "run", "--token", settings.CLOUDFLARE_TUNNEL_TOKEN]
        proc = subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            stdout=log_fp,
            stderr=subprocess.STDOUT,
            creationflags=detached_flags
        )
        TUNNEL_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
        time.sleep(3)
        if proc.poll() is not None:
            print(f"[ERROR] Named tunnel exited prematurely with code {proc.returncode}.")
            return False
        public_url = settings.STATIC_TUNNEL_URL.rstrip('/') if settings.STATIC_TUNNEL_URL else "https://your-configured-domain.com"
        TUNNEL_URL_FILE.write_text(public_url, encoding="utf-8")
        print("\n" + "=" * 70)
        print("       PERMANENT CLOUDFLARE NAMED TUNNEL ACTIVE")
        print("=" * 70)
        print(f"Public Base URL:  {public_url}")
        print(f"Streamable HTTP:  {public_url}/mcp")
        print(f"SSE Endpoint:     {public_url}/sse")
        print("=" * 70 + "\n")
        return True

    # Mode B: Permanent ngrok Static Domain
    if settings.NGROK_DOMAIN or settings.TUNNEL_MODE.lower() == "ngrok":
        ngrok_bin = find_ngrok()
        if not ngrok_bin:
            print("[ERROR] ngrok executable not found in PATH.")
            return False

        # Clean up any lingering previous ngrok process to prevent ERR_NGROK_334
        if os.name == "nt":
            subprocess.run(["taskkill", "/IM", "ngrok.exe", "/F"], capture_output=True, check=False)
            time.sleep(1)

        clean_domain = settings.NGROK_DOMAIN.replace("https://", "").replace("http://", "").strip("/")
        domain_arg = [f"--url={clean_domain}"] if clean_domain else []
        print(f"[*] Starting Permanent ngrok Tunnel on port {port} (Domain: {clean_domain or 'auto'})...")
        cmd = [ngrok_bin, "http", str(port)] + domain_arg
        proc = subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            stdout=log_fp,
            stderr=subprocess.STDOUT,
            creationflags=detached_flags
        )
        TUNNEL_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
        time.sleep(3)
        if proc.poll() is not None:
            print(f"[ERROR] ngrok tunnel exited prematurely with code {proc.returncode}.")
            return False
        if clean_domain:
            public_url = f"https://{clean_domain}"
            TUNNEL_URL_FILE.write_text(public_url, encoding="utf-8")
        else:
            public_url = "https://127.0.0.1:4040 (Inspect ngrok dashboard for URL)"
        print("\n" + "=" * 70)
        print("       PERMANENT NGROK STATIC TUNNEL ACTIVE")
        print("=" * 70)
        print(f"Public Base URL:  {public_url}")
        print(f"Streamable HTTP:  {public_url}/mcp")
        print(f"SSE Endpoint:     {public_url}/sse")
        print("=" * 70 + "\n")
        return True

    # Mode C: Ephemeral Cloudflare Quick Tunnel (Default fallback)
    cf_bin = find_cloudflared()
    if not cf_bin:
        print("\n" + "=" * 70)
        print("[!] Cloudflare Tunnel (cloudflared) is not detected on your system.")
        print("=" * 70 + "\n")
        return False

    print(f"[*] Starting Cloudflare Quick Tunnel to http://{host}:{port} using {cf_bin}...")
    cmd = [cf_bin, "tunnel", "--url", f"http://{host}:{port}"]
    proc = subprocess.Popen(
        cmd,
        cwd=str(BASE_DIR),
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        creationflags=detached_flags
    )
    TUNNEL_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    print(f"[*] Tunnel process spawned (PID: {proc.pid}). Detecting public HTTPS URL...")

    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
    public_url = ""
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
        if proc.poll() is not None:
            print(f"[ERROR] Tunnel process exited prematurely with code {proc.returncode}.")
            return False

    if not public_url:
        print("[!] Could not automatically capture trycloudflare.com URL within 60s.")
        print(f"Check logs in: {TUNNEL_LOG_FILE}")
        return False

    print("\n" + "=" * 70)
    print("       CLOUDFLARE SECURE HTTPS MCP TUNNEL ACTIVE (QUICK TUNNEL)")
    print("=" * 70)
    print(f"Public Base URL:  {public_url}")
    print(f"Streamable HTTP:  {public_url}/mcp")
    print(f"SSE Endpoint:     {public_url}/sse")
    print(f"Health Check:     {public_url}/health")
    print("=" * 70)
    print("Ready for ChatGPT Web connector registration.")
    print("=" * 70 + "\n")
    return True

def stop_tunnel():
    """Stop only the tunnel process recorded by this project; never kill all tunnel processes."""
    killed = False
    if TUNNEL_PID_FILE.exists():
        try:
            pid = int(TUNNEL_PID_FILE.read_text(encoding="utf-8").strip())
            print(f"[*] Checking recorded tunnel process (PID: {pid})...")
            lookup = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
            )
            process_line = lookup.stdout.lower()
            if "cloudflared.exe" in process_line or "ngrok.exe" in process_line:
                result = subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    killed = True
                    print("[OK] Recorded tunnel process stopped.")
                else:
                    print(f"[!] Could not stop tunnel PID {pid}: {(result.stderr or result.stdout).strip()}")
            elif "no tasks" in process_line or not process_line.strip():
                print("[*] Recorded tunnel process is not running.")
            else:
                print("[!] Recorded PID is not a recognized cloudflared/ngrok process; refusing to terminate it.")
        except (ValueError, OSError) as exc:
            print(f"[!] Invalid or unreadable tunnel PID file: {exc}")
        finally:
            if TUNNEL_PID_FILE.exists():
                TUNNEL_PID_FILE.unlink()
            if TUNNEL_URL_FILE.exists():
                TUNNEL_URL_FILE.unlink()
    else:
        if TUNNEL_URL_FILE.exists():
            TUNNEL_URL_FILE.unlink()
        print("[*] No recorded tunnel PID found; no process was terminated.")

    # Also clean up any lingering ngrok process on Windows
    if os.name == "nt":
        subprocess.run(["taskkill", "/IM", "ngrok.exe", "/F"], capture_output=True, check=False)

    if killed:
        print("[OK] Project tunnel stopped.")
    else:
        print("[*] No project-owned tunnel process was stopped.")

if __name__ == "__main__":
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "start"
    if action == "start":
        sys.exit(0 if start_tunnel() else 1)
    elif action == "stop":
        stop_tunnel()
    else:
        print(f"Unknown action: {action}. Use 'start' or 'stop'.")
        sys.exit(2)
