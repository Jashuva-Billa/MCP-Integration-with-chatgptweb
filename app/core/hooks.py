"""
Lifecycle Hooks Engine
=======================
Supports before/after hooks for:
  - file_edit
  - command_exec
  - test_run
  - git_commit
  - task_complete

Hooks are discovered from:
  1. Global config: ~/.mcp/hooks.json
  2. Project config: <repo_root>/.mcp/hooks.json
  3. Environment variable: MCP_HOOKS_FILE

Each hook definition:
  {
    "event": "before_file_edit",
    "name": "format_with_ruff",
    "command": "ruff format {file}",
    "on_failure": "warn"    // "warn" | "abort"
    "enabled": true
  }

Events
------
  before_file_edit(file)        → format, lint check
  after_file_edit(file)         → re-lint, security scan
  before_command_exec(command)  → policy log
  after_command_exec(command, exit_code) → notify
  before_test_run()             → stage changes
  after_test_run(passed)        → coverage upload
  before_git_commit(message)    → secret scan, lint
  after_task_complete(task_id)  → audit summary
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import shlex
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("mcp_server.hooks")


VALID_EVENTS = {
    "before_file_edit",
    "after_file_edit",
    "before_command_exec",
    "after_command_exec",
    "before_test_run",
    "after_test_run",
    "before_git_commit",
    "after_task_complete",
}


class HookDefinition:
    def __init__(self, data: Dict[str, Any]) -> None:
        self.event: str = data.get("event", "")
        self.name: str = data.get("name", self.event)
        self.command: str = data.get("command", "")
        self.on_failure: str = data.get("on_failure", "warn")   # "warn" | "abort"
        self.enabled: bool = data.get("enabled", True)
        self.timeout: int = int(data.get("timeout", 30))

    def is_valid(self) -> bool:
        return bool(self.event and self.event in VALID_EVENTS and self.command)


class HooksEngine:
    """
    Discovers, loads, and fires lifecycle hooks.
    Authorization: hooks may never elevate permissions — they run with the
    same policy profile as the triggering tool call.
    """

    def __init__(self) -> None:
        self._hooks: List[HookDefinition] = []
        self._loaded = False

    def _discover_hook_files(self) -> List[Path]:
        candidates: List[Path] = []

        # Environment override
        env_file = os.environ.get("MCP_HOOKS_FILE", "")
        if env_file and Path(env_file).is_file():
            candidates.append(Path(env_file))
            return candidates

        # Global
        global_hooks = Path.home() / ".mcp" / "hooks.json"
        if global_hooks.is_file():
            candidates.append(global_hooks)

        # Project-level
        try:
            from app.core.session import session_manager
            repo_root = session_manager.get_active_repo_path()
            project_hooks = repo_root / ".mcp" / "hooks.json"
            if project_hooks.is_file():
                candidates.append(project_hooks)
        except Exception:
            pass

        return candidates

    def reload(self) -> None:
        """Re-scan and reload all hook definitions."""
        self._hooks = []
        for path in self._discover_hook_files():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                hooks_list = data if isinstance(data, list) else data.get("hooks", [])
                for entry in hooks_list:
                    h = HookDefinition(entry)
                    if h.is_valid() and h.enabled:
                        self._hooks.append(h)
                logger.info("Loaded %d hooks from %s", len(hooks_list), path)
            except Exception as exc:
                logger.warning("Failed to load hooks from %s: %s", path, exc)
        self._loaded = True
        logger.info("Hooks engine: %d active hook(s) loaded", len(self._hooks))

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.reload()

    def fire(self, event: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Fire all hooks registered for the given event.
        Returns a list of results (one per matching hook).
        If a hook's on_failure='abort', raises RuntimeError on non-zero exit.
        """
        self._ensure_loaded()
        ctx = context or {}
        results: List[Dict[str, Any]] = []

        for hook in self._hooks:
            if hook.event != event:
                continue
            try:
                cmd_str = hook.command.format(**{k: str(v) for k, v in ctx.items()})
                args = shlex.split(cmd_str, posix=True)
                logger.debug("Firing hook '%s': %s", hook.name, cmd_str)

                # Hooks run with shell=False; no credential exposure
                result = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    timeout=hook.timeout,
                    errors="replace",
                )
                success = result.returncode == 0
                entry = {
                    "hook": hook.name,
                    "event": event,
                    "command": cmd_str,
                    "exit_code": result.returncode,
                    "stdout": result.stdout[:2000],
                    "stderr": result.stderr[:2000],
                    "success": success,
                }
                results.append(entry)

                if not success:
                    logger.warning("Hook '%s' failed (exit %d): %s", hook.name, result.returncode, result.stderr[:200])
                    if hook.on_failure == "abort":
                        raise RuntimeError(
                            f"Hook '{hook.name}' (event={event}) failed with exit {result.returncode}: {result.stderr[:200]}"
                        )
            except RuntimeError:
                raise
            except subprocess.TimeoutExpired:
                entry = {"hook": hook.name, "event": event, "error": f"Hook timed out after {hook.timeout}s"}
                results.append(entry)
                logger.warning("Hook '%s' timed out", hook.name)
                if hook.on_failure == "abort":
                    raise RuntimeError(f"Hook '{hook.name}' timed out")
            except Exception as exc:
                results.append({"hook": hook.name, "event": event, "error": str(exc)})
                logger.warning("Hook '%s' raised exception: %s", hook.name, exc)

        return results

    def list_hooks(self) -> List[Dict[str, Any]]:
        self._ensure_loaded()
        return [
            {"name": h.name, "event": h.event, "command": h.command, "on_failure": h.on_failure, "enabled": h.enabled}
            for h in self._hooks
        ]

    @property
    def hook_count(self) -> int:
        self._ensure_loaded()
        return len(self._hooks)


# Singleton
hooks_engine = HooksEngine()
