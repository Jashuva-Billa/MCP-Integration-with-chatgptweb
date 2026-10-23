"""
Task State and Memory Engine
==============================
Provides persistent, resumable task state for the autonomous coding loop.

Each task tracks:
  - User objective and requirements
  - Repository and branch at start
  - Implementation plan (steps)
  - Files inspected and modified
  - Commands executed
  - Test results
  - Repair attempts
  - Checkpoints (recoverable snapshots of file state)
  - Final verification status
  - Outstanding issues

Tasks are stored as JSON files in runtime/tasks/.
Temporary task state is separated from persistent project knowledge.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    TESTING = "testing"
    REPAIRING = "repairing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskStep:
    index: int
    description: str
    status: str = "pending"       # pending | done | failed | skipped
    result: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class TestRun:
    command: str
    exit_code: int
    duration_seconds: float
    passed: bool
    stdout: str = ""
    stderr: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Checkpoint:
    id: str
    timestamp: str
    description: str
    file_backups: Dict[str, str]   # relative_path → backup_path


@dataclass
class TaskState:
    id: str
    objective: str
    requirements: List[str]
    repository: str
    branch: str
    status: TaskStatus
    profile: str
    plan: List[TaskStep]
    files_inspected: List[str]
    files_modified: List[str]
    commands_executed: List[str]
    test_runs: List[TestRun]
    repair_attempts: int
    checkpoints: List[Checkpoint]
    outstanding_issues: List[str]
    final_verified: bool
    created_at: str
    updated_at: str
    error: Optional[str] = None
    max_repair_attempts: int = 5


# ---------------------------------------------------------------------------
# Task Manager
# ---------------------------------------------------------------------------

class TaskManager:
    """
    Manages autonomous coding task lifecycle.
    Thread-safe; tasks are persisted to runtime/tasks/.
    """

    def __init__(self) -> None:
        base = Path(__file__).resolve().parent.parent.parent / "runtime" / "tasks"
        base.mkdir(parents=True, exist_ok=True)
        self._tasks_dir = base
        self._lock = threading.Lock()
        self._active_tasks: Dict[str, TaskState] = {}

    # ------------------------------------------------------------------ #
    # CRUD                                                                 #
    # ------------------------------------------------------------------ #

    def create_task(
        self,
        objective: str,
        requirements: Optional[List[str]] = None,
        plan_steps: Optional[List[str]] = None,
        max_repair_attempts: int = 5,
    ) -> TaskState:
        from app.core.session import session_manager
        import subprocess

        repo_name = session_manager.get_active_repo_name() or "unknown"
        try:
            root = session_manager.get_active_repo_path()
            branch_out = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(root), capture_output=True, text=True, timeout=5
            ).stdout.strip()
        except Exception:
            branch_out = "unknown"

        try:
            from app.core.permissions import policy_engine
            profile = policy_engine.profile.value
        except Exception:
            profile = "unknown"

        now = datetime.now(timezone.utc).isoformat()
        task = TaskState(
            id=str(uuid.uuid4())[:8],
            objective=objective,
            requirements=requirements or [],
            repository=repo_name,
            branch=branch_out,
            status=TaskStatus.PENDING,
            profile=profile,
            plan=[
                TaskStep(index=i, description=desc)
                for i, desc in enumerate(plan_steps or [], start=1)
            ],
            files_inspected=[],
            files_modified=[],
            commands_executed=[],
            test_runs=[],
            repair_attempts=0,
            checkpoints=[],
            outstanding_issues=[],
            final_verified=False,
            created_at=now,
            updated_at=now,
            max_repair_attempts=max_repair_attempts,
        )

        with self._lock:
            self._active_tasks[task.id] = task
        self._persist(task)
        return task

    def get_task(self, task_id: str) -> Optional[TaskState]:
        with self._lock:
            if task_id in self._active_tasks:
                return self._active_tasks[task_id]
        # Try loading from disk
        path = self._tasks_dir / f"{task_id}.json"
        if path.exists():
            return self._load(path)
        return None

    def list_tasks(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        tasks = []
        seen: set = set()
        with self._lock:
            for t in self._active_tasks.values():
                if status_filter and t.status.value != status_filter:
                    continue
                seen.add(t.id)
                tasks.append(self._summary(t))
        for p in sorted(self._tasks_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
            tid = p.stem
            if tid in seen:
                continue
            try:
                t = self._load(p)
                if status_filter and t.status.value != status_filter:
                    continue
                tasks.append(self._summary(t))
            except Exception:
                pass
        return tasks

    def update_status(self, task_id: str, status: TaskStatus) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False
        task.status = status
        task.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist(task)
        return True

    def record_file_inspected(self, task_id: str, path: str) -> None:
        task = self.get_task(task_id)
        if task and path not in task.files_inspected:
            task.files_inspected.append(path)
            task.updated_at = datetime.now(timezone.utc).isoformat()
            self._persist(task)

    def record_file_modified(self, task_id: str, path: str) -> None:
        task = self.get_task(task_id)
        if task:
            if path not in task.files_modified:
                task.files_modified.append(path)
            task.updated_at = datetime.now(timezone.utc).isoformat()
            self._persist(task)

    def record_command(self, task_id: str, command: str) -> None:
        task = self.get_task(task_id)
        if task:
            task.commands_executed.append(command)
            task.updated_at = datetime.now(timezone.utc).isoformat()
            self._persist(task)

    def record_test_run(self, task_id: str, run: TestRun) -> None:
        task = self.get_task(task_id)
        if task:
            task.test_runs.append(run)
            task.updated_at = datetime.now(timezone.utc).isoformat()
            self._persist(task)

    def increment_repair(self, task_id: str) -> int:
        task = self.get_task(task_id)
        if task:
            task.repair_attempts += 1
            task.updated_at = datetime.now(timezone.utc).isoformat()
            self._persist(task)
            return task.repair_attempts
        return 0

    def add_issue(self, task_id: str, issue: str) -> None:
        task = self.get_task(task_id)
        if task and issue not in task.outstanding_issues:
            task.outstanding_issues.append(issue)
            task.updated_at = datetime.now(timezone.utc).isoformat()
            self._persist(task)

    def mark_step(self, task_id: str, step_index: int, status: str, result: Optional[str] = None) -> None:
        task = self.get_task(task_id)
        if task:
            for step in task.plan:
                if step.index == step_index:
                    step.status = status
                    step.result = result
                    now = datetime.now(timezone.utc).isoformat()
                    if status == "running":
                        step.started_at = now
                    else:
                        step.completed_at = now
                    break
            task.updated_at = datetime.now(timezone.utc).isoformat()
            self._persist(task)

    def set_verified(self, task_id: str, verified: bool) -> None:
        task = self.get_task(task_id)
        if task:
            task.final_verified = verified
            task.updated_at = datetime.now(timezone.utc).isoformat()
            self._persist(task)

    def cancel_task(self, task_id: str) -> bool:
        return self.update_status(task_id, TaskStatus.CANCELLED)

    def fail_task(self, task_id: str, error: str) -> bool:
        task = self.get_task(task_id)
        if task:
            task.status = TaskStatus.FAILED
            task.error = error
            task.updated_at = datetime.now(timezone.utc).isoformat()
            self._persist(task)
            return True
        return False

    # ------------------------------------------------------------------ #
    # Persistence                                                           #
    # ------------------------------------------------------------------ #

    def _persist(self, task: TaskState) -> None:
        path = self._tasks_dir / f"{task.id}.json"
        data = self._serialize(task)
        content = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        tmp = path.with_suffix(f".tmp_{int(time.time()*1000)}")
        tmp.write_text(content, encoding="utf-8")
        for attempt in range(5):
            try:
                tmp.replace(path)
                break
            except PermissionError:
                if attempt == 4:
                    path.write_text(content, encoding="utf-8")
                    try:
                        tmp.unlink(missing_ok=True)
                    except Exception:
                        pass
                else:
                    time.sleep(0.05)

    def _load(self, path: Path) -> TaskState:
        data = json.loads(path.read_text(encoding="utf-8"))
        plan = [TaskStep(**s) for s in data.get("plan", [])]
        test_runs = [TestRun(**t) for t in data.get("test_runs", [])]
        checkpoints = [Checkpoint(**c) for c in data.get("checkpoints", [])]
        return TaskState(
            id=data["id"],
            objective=data["objective"],
            requirements=data.get("requirements", []),
            repository=data.get("repository", ""),
            branch=data.get("branch", ""),
            status=TaskStatus(data.get("status", "pending")),
            profile=data.get("profile", ""),
            plan=plan,
            files_inspected=data.get("files_inspected", []),
            files_modified=data.get("files_modified", []),
            commands_executed=data.get("commands_executed", []),
            test_runs=test_runs,
            repair_attempts=data.get("repair_attempts", 0),
            checkpoints=checkpoints,
            outstanding_issues=data.get("outstanding_issues", []),
            final_verified=data.get("final_verified", False),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            error=data.get("error"),
            max_repair_attempts=data.get("max_repair_attempts", 5),
        )

    def _serialize(self, task: TaskState) -> Dict[str, Any]:
        return {
            "id": task.id,
            "objective": task.objective,
            "requirements": task.requirements,
            "repository": task.repository,
            "branch": task.branch,
            "status": task.status.value,
            "profile": task.profile,
            "plan": [{"index": s.index, "description": s.description, "status": s.status, "result": s.result, "started_at": s.started_at, "completed_at": s.completed_at} for s in task.plan],
            "files_inspected": task.files_inspected,
            "files_modified": task.files_modified,
            "commands_executed": task.commands_executed,
            "test_runs": [{"command": t.command, "exit_code": t.exit_code, "duration_seconds": t.duration_seconds, "passed": t.passed, "stdout": t.stdout[:2000], "stderr": t.stderr[:2000], "timestamp": t.timestamp} for t in task.test_runs],
            "repair_attempts": task.repair_attempts,
            "checkpoints": [{"id": c.id, "timestamp": c.timestamp, "description": c.description, "file_backups": c.file_backups} for c in task.checkpoints],
            "outstanding_issues": task.outstanding_issues,
            "final_verified": task.final_verified,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "error": task.error,
            "max_repair_attempts": task.max_repair_attempts,
        }

    def _summary(self, task: TaskState) -> Dict[str, Any]:
        done = sum(1 for s in task.plan if s.status == "done")
        total = len(task.plan)
        return {
            "id": task.id,
            "objective": task.objective[:100],
            "status": task.status.value,
            "repository": task.repository,
            "branch": task.branch,
            "profile": task.profile,
            "plan_progress": f"{done}/{total}",
            "repair_attempts": task.repair_attempts,
            "files_modified": len(task.files_modified),
            "final_verified": task.final_verified,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }


# Singleton
task_manager = TaskManager()
