#!/bin/bash
# macOS double-click status checker for the MCP server.
# Uses curl and the project's PID file; no Windows tasklist/taskkill commands are used.

cd "$(dirname "$0")" || exit 1
PID_FILE="runtime/mcp_server.pid"
HEALTH_URL="http://127.0.0.1:8766/health"

echo "=== MCP Server Status — macOS ==="
if [ -f "$PID_FILE" ]; then
  SERVER_PID="$(cat "$PID_FILE" 2>/dev/null)"
  if [[ "$SERVER_PID" =~ ^[0-9]+$ ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "Process: RUNNING (PID: $SERVER_PID)"
  else
    echo "Process: STOPPED or stale PID file"
  fi
else
  echo "Process: No project PID file found"
fi

if curl --silent --show-error --fail --max-time 3 "$HEALTH_URL"; then
  echo
  echo "Health: OK ($HEALTH_URL)"
else
  echo
  echo "Health: UNREACHABLE ($HEALTH_URL)"
fi

if [ -f runtime/mcp_server.log ]; then
  echo
  echo "Recent log output:"
  tail -n 10 runtime/mcp_server.log
fi
read -r -p "Press Return to close..."
