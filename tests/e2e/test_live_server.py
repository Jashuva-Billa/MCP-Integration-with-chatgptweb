from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def test_live_server_restart_smoke_and_registered_tools():
    root = Path(__file__).resolve().parents[2]
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = os.environ.copy()
    env.update({
        "MCP_HOST": "127.0.0.1",
        "MCP_PORT": str(port),
        "MCP_DEPLOYMENT_MODE": "local",
        "MCP_AUTH_ENABLED": "false",
        "MCP_AUTH_TOKEN": "",
        "MCP_DASHBOARD_ENABLED": "true",
    })
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:create_app", "--factory",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=str(root), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        deadline = time.monotonic() + 20
        health = None
        last_error = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout else ""
                raise AssertionError(f"Server exited before health check: {output}")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                    health = response.read().decode("utf-8")
                break
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                time.sleep(0.2)
        assert health is not None, f"Server did not become healthy: {last_error}"
        import json
        health_data = json.loads(health)
        assert health_data["status"] == "ok"
        assert health_data["tool_count"] == 90
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/tools", timeout=3) as response:
            tools = json.loads(response.read().decode("utf-8"))
        assert tools["total_tools"] == 90
        assert "worker_runtime" in tools["categories"]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/dashboard", timeout=3) as response:
            dashboard = response.read().decode("utf-8")
        assert "Worker jobs" in dashboard
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/workers", timeout=3) as response:
            workers = json.loads(response.read().decode("utf-8"))
        assert "jobs" in workers
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
