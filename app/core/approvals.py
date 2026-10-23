"""Persistent, auditable approval queue for privileged coding operations."""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.core.audit import audit


class ApprovalManager:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(__file__).resolve().parents[2] / "runtime" / "approvals.json"
        self._lock = threading.RLock()

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _write(self, rows: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.path)

    def request(self, operation: str, target: str, details: str = "", ttl_minutes: int = 60,
                task_id: str | None = None) -> dict[str, Any]:
        operation, target = operation.strip(), target.strip()
        if not operation or not target:
            raise ValueError("operation and target are required")
        if ttl_minutes < 1 or ttl_minutes > 1440:
            raise ValueError("ttl_minutes must be between 1 and 1440")
        now = datetime.now(timezone.utc)
        row = {
            "id": uuid.uuid4().hex[:12], "operation": operation[:100], "target": target[:500],
            "details": details[:2000], "task_id": task_id[:100] if task_id else None,
            "status": "pending", "created_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=ttl_minutes)).isoformat(),
            "resolved_at": None, "resolved_by": None,
        }
        with self._lock:
            rows = self._read()
            rows.append(row)
            self._write(rows)
        audit.log_tool("request_approval", {"operation": operation, "target": target, "approval_id": row["id"]})
        return row

    def list(self, status: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._read()
            now = datetime.now(timezone.utc)
            changed = False
            for row in rows:
                if row.get("status") == "pending" and datetime.fromisoformat(row["expires_at"]) <= now:
                    row["status"] = "expired"
                    changed = True
            if changed:
                self._write(rows)
            return [row for row in reversed(rows) if status is None or row.get("status") == status]

    def resolve(self, approval_id: str, decision: str, resolved_by: str = "user") -> dict[str, Any]:
        if decision not in {"approved", "denied"}:
            raise ValueError("decision must be approved or denied")
        with self._lock:
            rows = self._read()
            row = next((item for item in rows if item.get("id") == approval_id), None)
            if row is None:
                raise ValueError("approval request not found")
            if row.get("status") != "pending":
                raise ValueError(f"approval request is already {row.get('status')}")
            if datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
                row["status"] = "expired"
                self._write(rows)
                raise ValueError("approval request expired")
            row["status"] = decision
            row["resolved_at"] = datetime.now(timezone.utc).isoformat()
            row["resolved_by"] = resolved_by[:100]
            self._write(rows)
        audit.log_tool("resolve_approval", {"approval_id": approval_id, "decision": decision, "resolved_by": resolved_by})
        return row

    def consume_approved(self, approval_id: str | None, operation: str, target: str,
                         task_id: str | None = None) -> bool:
        """Atomically consume a matching approval so it cannot be replayed."""
        if not approval_id:
            return False
        with self._lock:
            rows = self._read()
            row = next((item for item in rows if item.get("id") == approval_id), None)
            if (not row or row.get("status") != "approved" or row.get("operation") != operation
                    or row.get("target") != target or (task_id and row.get("task_id") and row.get("task_id") != task_id)):
                return False
            if datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
                row["status"] = "expired"
                self._write(rows)
                return False
            row["status"] = "consumed"
            row["consumed_at"] = datetime.now(timezone.utc).isoformat()
            self._write(rows)
        audit.log_tool("consume_approval", {"approval_id": approval_id, "operation": operation, "target": target})
        return True

    def is_approved(self, approval_id: str | None, operation: str, target: str) -> bool:
        if not approval_id:
            return False
        for row in self.list(status="approved"):
            if row.get("id") == approval_id and row.get("operation") == operation and row.get("target") == target:
                return True
        return False


approval_manager = ApprovalManager()
