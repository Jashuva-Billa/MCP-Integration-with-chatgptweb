#!/bin/bash
# macOS double-click stop command for the MCP server.
# Stops only the process recorded by this project; it does not kill arbitrary Python processes.

cd "$(dirname "$0")" || exit 1
PID_FILE="runtime/mcp_server.pid"

echo "=== Stop MCP Server — macOS ==="
if [ ! -f "$PID_FILE" ]; then
  echo "[INFO] No MCP PID file found. The server may already be stopped."
  read -r -p "Press Return to close..."
  exit 0
fi

SERVER_PID="$(cat "$PID_FILE" 2>/dev/null)"
case "$SERVER_PID" in
  ''|*[!0-9]*)
    echo "[WARNING] Invalid PID file. Removing it."
    rm -f "$PID_FILE"
    read -r -p "Press Return to close..."
    exit 1
    ;;
esac

if kill -0 "$SERVER_PID" 2>/dev/null; then
  kill "$SERVER_PID"
  for _ in {1..10}; do
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
      break
    fi
    sleep 1
  done
  if kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "[WARNING] Process did not stop gracefully; sending SIGKILL to recorded PID."
    kill -9 "$SERVER_PID" 2>/dev/null
  fi
  echo "[OK] Stop signal sent to MCP server PID $SERVER_PID."
else
  echo "[INFO] MCP server PID $SERVER_PID is not running."
fi

rm -f "$PID_FILE"
echo "If health still responds, inspect the process and logs before stopping anything else."
read -r -p "Press Return to close..."
