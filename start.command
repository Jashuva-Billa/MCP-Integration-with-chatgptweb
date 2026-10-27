#!/bin/bash
# macOS double-click launcher for the MCP server.
# This starts the LOCAL server only; it does not start a Cloudflare/ngrok tunnel.
# No virtual environment is required. Dependencies must be installed for python3.

cd "$(dirname "$0")" || exit 1
mkdir -p runtime

PYTHON_BIN="${PYTHON_BIN:-python3}"
PID_FILE="runtime/mcp_server.pid"
LOG_FILE="runtime/mcp_server.log"
HEALTH_URL="http://127.0.0.1:8766/health"

echo "=== MCP Server — macOS launcher ==="
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "[ERROR] python3 was not found. Install Python 3.10+ from python.org or Homebrew."
  read -r -p "Press Return to close..."
  exit 1
fi

if curl --silent --fail --max-time 2 "$HEALTH_URL" >/dev/null; then
  echo "[OK] MCP server is already responding at $HEALTH_URL"
  read -r -p "Press Return to close..."
  exit 0
fi

if ! "$PYTHON_BIN" -c 'import mcp, starlette, uvicorn, pydantic, pydantic_settings' >/dev/null 2>&1; then
  echo "[ERROR] Required Python packages are missing for $PYTHON_BIN."
  echo "Install them from this folder with:"
  echo '  python3 -m pip install -e ".[dev]"'
  read -r -p "Press Return to close..."
  exit 1
fi

nohup "$PYTHON_BIN" app/main.py >>"$LOG_FILE" 2>&1 </dev/null &
SERVER_PID=$!
echo "$SERVER_PID" > "$PID_FILE"

for _ in {1..20}; do
  if curl --silent --fail --max-time 2 "$HEALTH_URL" >/dev/null; then
    echo "[OK] MCP server started (PID: $SERVER_PID)"
    echo "MCP endpoint: $HEALTH_URL"
    echo "Streamable HTTP: http://127.0.0.1:8766/mcp"
    echo "Logs: $LOG_FILE"
    read -r -p "Press Return to close..."
    exit 0
  fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    break
  fi
  sleep 1
done

echo "[ERROR] Server did not become healthy. Check $LOG_FILE"
tail -n 30 "$LOG_FILE"
read -r -p "Press Return to close..."
exit 1
