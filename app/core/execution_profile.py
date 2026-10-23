"""Configurable autonomy profile for the coding agent.

This is separate from PermissionProfile: autonomy controls workflow behavior,
while PermissionProfile remains the enforcement layer for allowed operations.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

_DEFAULTS: dict[str, Any] = {
    "autonomy": "maximum",
    "auto_skill_selection": True,
    "self_healing": True,
    "parallel_agents": True,
    "git_delivery": "requested",
    "destructive_policy": "checkpoint",
    "max_repair_attempts": 5,
    "parallel_workstream_limit": 3,
}

_VALID_AUTONOMY = {"standard", "maximum", "sandbox"}
_VALID_GIT_DELIVERY = {"requested", "configured"}
_VALID_DESTRUCTIVE = {"checkpoint", "sandbox-only"}
_BOOL_FIELDS = {"auto_skill_selection", "self_healing", "parallel_agents"}
_INT_FIELDS = {"max_repair_attempts": (1, 10), "parallel_workstream_limit": (1, 8)}


class ExecutionProfileManager:
    """Thread-safe, persistent execution-profile configuration."""

    def __init__(self, path: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[2]
        self.path = path or root / "runtime" / "execution_profile.json"
        self._lock = threading.RLock()
        self._profile = dict(_DEFAULTS)
        self._load()

    def _validate(self, values: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
        allowed = set(_DEFAULTS)
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"Unknown execution profile field(s): {', '.join(sorted(unknown))}")
        candidate = dict(self._profile if partial else _DEFAULTS)
        candidate.update(values)
        if candidate["autonomy"] not in _VALID_AUTONOMY:
            raise ValueError(f"autonomy must be one of {sorted(_VALID_AUTONOMY)}")
        if candidate["git_delivery"] not in _VALID_GIT_DELIVERY:
            raise ValueError(f"git_delivery must be one of {sorted(_VALID_GIT_DELIVERY)}")
        if candidate["destructive_policy"] not in _VALID_DESTRUCTIVE:
            raise ValueError(f"destructive_policy must be one of {sorted(_VALID_DESTRUCTIVE)}")
        for key in _BOOL_FIELDS:
            if not isinstance(candidate[key], bool):
                raise ValueError(f"{key} must be a boolean")
        for key, (minimum, maximum) in _INT_FIELDS.items():
            value = candidate[key]
            if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
                raise ValueError(f"{key} must be an integer between {minimum} and {maximum}")
        return candidate

    def _load(self) -> None:
        env_autonomy = os.environ.get("MCP_AUTONOMY_PROFILE")
        if self.path.is_file():
            try:
                stored = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(stored, dict):
                    self._profile = self._validate(stored)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                # Invalid persisted config must not prevent server startup.
                self._profile = dict(_DEFAULTS)
        if env_autonomy:
            try:
                self._profile = self._validate({"autonomy": env_autonomy}, partial=True)
            except ValueError:
                pass

    def get(self) -> dict[str, Any]:
        with self._lock:
            result = dict(self._profile)
            result["parallel_execution_mode"] = (
                "planned_workstreams"
                if result["parallel_agents"]
                else "sequential"
            )
            result["parallel_agent_runtime_available"] = True
            result["parallel_review_runtime_available"] = True
            result["isolated_worktree_agent_runtime_available"] = False
            result["note"] = (
                "Concurrent independent model review workers are available when the model provider is configured. "
                "Separate worktree-based coding workers that edit branches and merge patches are not implemented."
            )
            return result

    def update(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            candidate = self._validate(updates, partial=True)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8")
            temporary.replace(self.path)
            self._profile = candidate
            return self.get()


execution_profile = ExecutionProfileManager()
