"""Isolated Git workstream lifecycle for independently operated coding workers.

This module provisions and validates worktrees; it does not spawn model sessions.
Each worker/client must be connected to the returned path and maintain its own context.
"""
from __future__ import annotations

import json
import re
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.audit import audit
from app.core.approvals import approval_manager
from app.core.permissions import policy_engine
from app.core.session import session_manager

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")


class WorkstreamManager:
    def __init__(self, metadata_path: Path | None = None) -> None:
        self.metadata_path = metadata_path or Path(__file__).resolve().parents[2] / "runtime" / "workstreams.json"
        self._lock = threading.RLock()

    def _rows(self) -> list[dict[str, Any]]:
        if not self.metadata_path.is_file():
            return []
        try:
            data = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _save(self, rows: list[dict[str, Any]]) -> None:
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.metadata_path.with_suffix(".tmp")
        temp.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        temp.replace(self.metadata_path)

    @staticmethod
    def _git(args: list[str], cwd: Path, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                              timeout=timeout, check=False)

    def create(self, task_id: str, worker_name: str, base_ref: str = "HEAD") -> dict[str, Any]:
        policy_engine.require_git_worktree()
        if not _SAFE_NAME.fullmatch(task_id) or not _SAFE_NAME.fullmatch(worker_name):
            raise ValueError("task_id and worker_name must be 1-40 safe letters, digits, underscores, or hyphens")
        if base_ref != "HEAD":
            raise ValueError("Only base_ref='HEAD' is supported; arbitrary refs are not accepted")
        root = Path(session_manager.get_active_repo_path()).resolve()
        branch = f"mcp-work/{task_id}/{worker_name}"
        worktree_path = (root / ".mcp-worktrees" / f"{task_id}-{worker_name}").resolve()
        if root not in worktree_path.parents:
            raise ValueError("Worktree path escapes the active repository")
        if worktree_path.exists():
            raise ValueError("Worktree destination already exists")
        branch_check = self._git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], root)
        if branch_check.returncode == 0:
            raise ValueError(f"Branch '{branch}' already exists")
        base = self._git(["rev-parse", "HEAD"], root)
        if base.returncode != 0:
            raise ValueError("Could not resolve the repository HEAD")
        status = self._git(["status", "--porcelain"], root)
        result = self._git(["worktree", "add", "-b", branch, str(worktree_path), "HEAD"], root, timeout=60)
        if result.returncode != 0:
            raise RuntimeError("Git could not create the isolated worktree")
        row = {
            "id": uuid.uuid4().hex[:12], "task_id": task_id, "worker_name": worker_name,
            "repository": session_manager.get_active_repo_name(), "repository_root": str(root),
            "path": str(worktree_path), "branch": branch, "base_revision": base.stdout.strip(),
            "source_worktree_dirty": bool(status.stdout.strip()),
            "status": "created", "test_command": None, "test_exit_code": None,
            "tests_passed": None, "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            rows = self._rows()
            rows.append(row)
            self._save(rows)
        audit.log_task_event(task_id, "workstream_created", detail=f"worker={worker_name};branch={branch}")
        return row

    def list(self, task_id: str | None = None) -> list[dict[str, Any]]:
        rows = self._rows()
        return [row for row in rows if task_id is None or row.get("task_id") == task_id]

    def validate(self, workstream_id: str, test_command: str) -> dict[str, Any]:
        policy_engine.require_cmd_execute()
        row = next((item for item in self._rows() if item.get("id") == workstream_id), None)
        if not row:
            raise ValueError("workstream not found")
        path = Path(row["path"]).resolve()
        root = Path(row["repository_root"]).resolve()
        if root not in path.parents or not path.is_dir():
            raise ValueError("workstream path is missing or outside its repository root")
        from app.tools.terminal import run_command
        result = run_command(test_command, working_directory=str(path))
        passed = result.get("exit_code") == 0
        with self._lock:
            rows = self._rows()
            current = next(item for item in rows if item.get("id") == workstream_id)
            current.update({"status": "validated" if passed else "failed", "test_command": test_command,
                            "test_exit_code": result.get("exit_code", -1), "tests_passed": passed,
                            "validated_at": datetime.now(timezone.utc).isoformat()})
            self._save(rows)
        audit.log_task_event(row["task_id"], "workstream_validated" if passed else "workstream_test_failed",
                             detail=f"worker={row['worker_name']};exit={result.get('exit_code')}")
        return {"workstream": current, "tests_passed": passed, "test_result": result}

    def merge(self, workstream_id: str, target_branch: str, test_command: str, approval_id: str) -> dict[str, Any]:
        """Merge a validated worker branch only after an explicit approval and passing target tests."""
        policy_engine.require_git_commit()
        rows = self._rows()
        row = next((item for item in rows if item.get("id") == workstream_id), None)
        if not row:
            raise ValueError("workstream not found")
        if row.get("tests_passed") is not True or row.get("status") != "validated":
            raise ValueError("workstream must pass its recorded test command before merge")
        source_branch = row["branch"]
        if not source_branch.startswith(f"mcp-work/{row['task_id']}/"):
            raise ValueError("source branch is not a managed MCP workstream branch")
        target = f"{source_branch}->{target_branch}"
        if not approval_manager.is_approved(approval_id, "git_merge", target):
            raise ValueError(f"An approved, unexpired git_merge request for '{target}' is required")
        root = Path(row["repository_root"]).resolve()
        current = self._git(["branch", "--show-current"], root)
        if current.returncode != 0 or current.stdout.strip() != target_branch:
            raise ValueError("Active repository must already be on target_branch; no implicit branch switch is performed")
        status = self._git(["status", "--porcelain"], root)
        if status.returncode != 0 or status.stdout.strip():
            raise ValueError("Target repository must have a clean working tree before merge")
        merge = self._git(["merge", "--no-ff", "--no-commit", source_branch], root, timeout=60)
        if merge.returncode != 0:
            self._git(["merge", "--abort"], root)
            audit.log_task_event(row["task_id"], "workstream_merge_conflict", detail=source_branch)
            return {"success": False, "error": "Merge failed or conflicted; merge was aborted.", "stderr": merge.stderr[:2000]}
        from app.tools.terminal import run_command
        tests = run_command(test_command, working_directory=str(root))
        if tests.get("exit_code") != 0:
            self._git(["merge", "--abort"], root)
            audit.log_task_event(row["task_id"], "workstream_merge_tests_failed", detail=source_branch)
            return {"success": False, "error": "Target tests failed after merge; merge was aborted.", "test_result": tests}
        commit = self._git(["commit", "--no-edit"], root, timeout=60)
        if commit.returncode != 0:
            self._git(["merge", "--abort"], root)
            return {"success": False, "error": "Merge commit failed; attempted to abort the in-progress merge.", "stderr": commit.stderr[:2000]}
        revision = self._git(["rev-parse", "HEAD"], root).stdout.strip()
        audit.log_git_op("workstream_merge", row.get("repository", ""), detail=f"{source_branch}->{target_branch};verified_tests=true;revision={revision[:12]}")
        return {"success": True, "workstream_id": workstream_id, "source_branch": source_branch,
                "target_branch": target_branch, "merge_commit": revision, "tests_passed": True,
                "test_command": test_command, "stdout": tests.get("stdout", "")[-2000:]}

    def remove(self, workstream_id: str) -> dict[str, Any]:
        policy_engine.require_git_worktree()
        rows = self._rows()
        row = next((item for item in rows if item.get("id") == workstream_id), None)
        if not row:
            raise ValueError("workstream not found")
        path = Path(row["path"]).resolve()
        root = Path(row["repository_root"]).resolve()
        if root not in path.parents:
            raise ValueError("workstream path escapes repository root")
        result = self._git(["worktree", "remove", str(path)], root, timeout=60)
        if result.returncode != 0:
            raise RuntimeError("Worktree removal failed; it may contain uncommitted changes")
        self._save([item for item in rows if item.get("id") != workstream_id])
        audit.log_task_event(row["task_id"], "workstream_removed", detail=f"worker={row['worker_name']}")
        return {"success": True, "workstream_id": workstream_id, "path": str(path)}


workstream_manager = WorkstreamManager()
