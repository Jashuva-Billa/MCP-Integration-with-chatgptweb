"""
Structured Audit Logger
========================
Emits a single JSON-line per tool invocation to the audit log.
Never records secret values — all token / credential content is redacted.

Usage
-----
    from app.core.audit import audit
    audit.log_tool("write_file", {"path": "src/app.py"}, success=True)
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_SECRET_RE = re.compile(
    r"(token|password|secret|key|auth|credential|passwd|apikey|api_key)\s*[=:]\s*\S+",
    re.IGNORECASE,
)

logger = logging.getLogger("mcp_server.audit")


def _redact(text: str) -> str:
    """Replace secret-looking values with [REDACTED]."""
    return _SECRET_RE.sub(lambda m: m.group(0).split("=")[0].split(":")[0] + "=[REDACTED]", text)


def _safe_serialize(obj: Any) -> Any:
    """JSON-safe representation with secret redaction."""
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items() if k.lower() not in
                {"token", "password", "secret", "key", "auth", "credential", "api_key", "apikey"}}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(i) for i in obj]
    if isinstance(obj, str):
        return _redact(obj)
    return obj


class AuditLogger:
    """
    Thread-safe, append-only structured audit log.

    Each entry is a JSON line written to runtime/audit.jsonl.
    The log is also emitted at DEBUG level to the standard logging system.
    """

    def __init__(self) -> None:
        from pathlib import Path as _Path
        base_dir = _Path(__file__).resolve().parent.parent.parent
        runtime_dir = base_dir / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = runtime_dir / "audit.jsonl"
        self._lock = threading.Lock()
        self._enabled = os.environ.get("MCP_AUDIT_LOG", "true").lower() != "false"

    def _write(self, entry: dict) -> None:
        if not self._enabled:
            return
        line = json.dumps(entry, ensure_ascii=False, default=str)
        with self._lock:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        logger.debug("AUDIT %s", line)

    def log_tool(
        self,
        tool_name: str,
        arguments: Optional[dict] = None,
        *,
        success: bool = True,
        error: Optional[str] = None,
        repository: Optional[str] = None,
        profile: Optional[str] = None,
        duration_ms: Optional[float] = None,
        extra: Optional[dict] = None,
    ) -> None:
        entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "tool_call",
            "tool": tool_name,
            "success": success,
            "profile": profile,
            "repository": repository,
        }
        if arguments:
            entry["args"] = _safe_serialize(arguments)
        if error:
            entry["error"] = _redact(error)
        if duration_ms is not None:
            entry["duration_ms"] = round(duration_ms, 1)
        if extra:
            entry["extra"] = _safe_serialize(extra)
        self._write(entry)

    def log_permission_denied(self, tool: str, capability: str, profile: str) -> None:
        self._write({
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "permission_denied",
            "tool": tool,
            "capability": capability,
            "profile": profile,
        })

    def log_file_change(
        self, operation: str, path: str, repository: str, *, bytes_written: Optional[int] = None
    ) -> None:
        entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "file_change",
            "operation": operation,
            "path": path,
            "repository": repository,
        }
        if bytes_written is not None:
            entry["bytes_written"] = bytes_written
        self._write(entry)

    def log_command(
        self, command: str, exit_code: int, duration_s: float, repository: str
    ) -> None:
        self._write({
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "command_exec",
            "command": _redact(command),
            "exit_code": exit_code,
            "duration_s": round(duration_s, 3),
            "repository": repository,
        })

    def log_git_op(self, operation: str, repository: str, *, detail: Optional[str] = None) -> None:
        entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "git_op",
            "operation": operation,
            "repository": repository,
        }
        if detail:
            entry["detail"] = detail
        self._write(entry)

    def log_task_event(self, task_id: str, event: str, *, detail: Optional[str] = None) -> None:
        entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "task_event",
            "task_id": task_id,
            "sub_event": event,
        }
        if detail:
            entry["detail"] = detail
        self._write(entry)


# Singleton
audit = AuditLogger()
