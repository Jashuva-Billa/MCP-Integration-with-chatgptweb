from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from app.config import settings
from app.core.permissions import PermissionProfile, policy_engine
from app.core.session import session_manager
from app.core.verification import _redact, verify_repository
from app.core.worker_runtime import WorkerRuntimeManager


def _make_repo(path):
    path.mkdir()
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Worker Test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "worker-test@example.com"], cwd=path, check=True)
    (path / ".gitignore").write_text(".mcp-worktrees/\n", encoding="utf-8")
    (path / "README.md").write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=path, check=True, capture_output=True)


def test_verification_runs_fresh_configured_processes_and_redacts(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _make_repo(repo)
    monkeypatch.setattr(settings, "MCP_VERIFICATION_COMMANDS", json.dumps([
        ["python", "-c", "print('API_KEY=sk-test-value')"]
    ]))
    evidence = verify_repository(repo, "test-verification")
    assert evidence["passed"] is True
    assert evidence["revision_stable"] is True
    assert evidence["checks"][0]["passed"] is True
    assert "[REDACTED]" in evidence["checks"][0]["stdout"]
    assert "sk-test-value" not in evidence["checks"][0]["stdout"]
    assert _redact("Authorization: Bearer abcdefghijklmnop") == "Authorization: Bearer [REDACTED]"


def test_verification_fails_if_working_tree_changes_during_checks(tmp_path, monkeypatch):
    repo = tmp_path / "repo-mutated-during-check"
    _make_repo(repo)
    monkeypatch.setattr(settings, "MCP_VERIFICATION_COMMANDS", json.dumps([
        ["python", "-c", "__import__('pathlib').Path('README.md').write_text('changed during verification')"]
    ]))

    evidence = verify_repository(repo, "test-working-tree-stability")

    assert evidence["revision_stable"] is True
    assert evidence["working_tree_stable"] is False
    assert evidence["passed"] is False


def test_worker_runtime_executes_worker_in_isolated_worktree(test_environment, tmp_path, monkeypatch):
    repo = tmp_path / "worker-success-repo"
    _make_repo(repo)
    repo_name = "WorkerRuntimeSuccess"
    from app.core.repository import repository_manager
    from app.core.workstreams import workstream_manager

    repository_manager.add_repository(repo_name, str(repo), "worker runtime success test", True)
    previous_profile = policy_engine.profile
    try:
        session_manager.set_active_repo_name(repo_name)
        policy_engine.set_profile(PermissionProfile.FULL)
        monkeypatch.setattr(settings, "MCP_WORKER_COMMANDS", json.dumps({
            "python-worker": [
                "python", "-c",
                "__import__('pathlib').Path('README.md').write_text('worker changed')"
            ]
        }))
        monkeypatch.setattr(settings, "MCP_WORKER_SANDBOX_MODE", "host")
        monkeypatch.setattr(settings, "MCP_WORKER_HOST_MODE_ALLOWED", True)
        manager = WorkerRuntimeManager()
        started = manager.start(
            "worker-success", "modify README in isolated worktree", ["python-worker"], 30,
            repository_root=str(repo), repository_name=repo_name,
        )
        deadline = time.monotonic() + 15
        job = manager.get(started["job_id"])
        while job["status"] in {"running", "cancelling"} and time.monotonic() < deadline:
            time.sleep(0.05)
            job = manager.get(started["job_id"])

        assert job["status"] == "completed", job
        result = job["results"][0]
        assert result["status"] == "completed", job["results"]
        assert (Path(result["path"]) / "README.md").read_text(encoding="utf-8") == "worker changed"
    finally:
        workstreams = [item for item in workstream_manager.list()
                       if item.get("parent_task_id") == "worker-success"]
        for workstream in workstreams:
            worktree = workstream.get("path")
            if worktree and Path(worktree).is_dir():
                subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=worktree, check=False,
                               capture_output=True, timeout=10)
                workstream_manager.remove(workstream["id"])
        session_manager.set_active_repo_name("Repo_A")
        repository_manager.remove_repository(repo_name)
        policy_engine.set_profile(previous_profile)


def test_worker_runtime_requires_explicit_host_mode_opt_in(test_environment, tmp_path, monkeypatch):
    repo = tmp_path / "worker-repo"
    _make_repo(repo)
    repo_name = "WorkerRuntimeTest"
    from app.core.repository import repository_manager
    repository_manager.add_repository(repo_name, str(repo), "worker runtime test", True)
    previous_profile = policy_engine.profile
    old_commands = settings.MCP_WORKER_COMMANDS
    old_mode = settings.MCP_WORKER_SANDBOX_MODE
    old_allowed = settings.MCP_WORKER_HOST_MODE_ALLOWED
    try:
        session_manager.set_active_repo_name(repo_name)
        policy_engine.set_profile(PermissionProfile.FULL)
        monkeypatch.setattr(settings, "MCP_WORKER_COMMANDS", json.dumps({
            "python-worker": ["python", "-c", "print('worker ran')"]
        }))
        monkeypatch.setattr(settings, "MCP_WORKER_SANDBOX_MODE", "host")
        monkeypatch.setattr(settings, "MCP_WORKER_HOST_MODE_ALLOWED", False)
        manager = WorkerRuntimeManager()
        started = manager.start("worker-security", "test safe host-mode denial", ["python-worker"], 30)
        deadline = time.monotonic() + 10
        job = manager.get(started["job_id"])
        while job["status"] in {"running", "cancelling"} and time.monotonic() < deadline:
            time.sleep(0.05)
            job = manager.get(started["job_id"])
        assert job["status"] == "failed", job
        assert job["results"][0]["status"] == "blocked", job["results"]
        assert "not sandboxed" in job["results"][0]["error"] or "Host execution is disabled" in job["results"][0]["error"]
    finally:
        session_manager.set_active_repo_name("Repo_A")
        repository_manager.remove_repository(repo_name)
        policy_engine.set_profile(previous_profile)
        settings.MCP_WORKER_COMMANDS = old_commands
        settings.MCP_WORKER_SANDBOX_MODE = old_mode
        settings.MCP_WORKER_HOST_MODE_ALLOWED = old_allowed

def test_worker_runtime_executes_a_real_cli_in_an_isolated_worktree(test_environment, tmp_path, monkeypatch):
    import uuid
    from app.core.repository import repository_manager
    from app.core.workstreams import workstream_manager

    repo = tmp_path / "worker-exec-repo"
    _make_repo(repo)
    repo_name = "WorkerExec" + uuid.uuid4().hex[:6]
    repository_manager.add_repository(repo_name, str(repo), "worker execution test", True)
    previous_profile = policy_engine.profile
    old_commands = settings.MCP_WORKER_COMMANDS
    old_mode = settings.MCP_WORKER_SANDBOX_MODE
    old_allowed = settings.MCP_WORKER_HOST_MODE_ALLOWED
    task_label = "worker-exec-" + uuid.uuid4().hex[:8]
    manager = WorkerRuntimeManager()
    try:
        session_manager.set_active_repo_name(repo_name)
        policy_engine.set_profile(PermissionProfile.FULL)
        monkeypatch.setattr(settings, "MCP_WORKER_COMMANDS", json.dumps({
            "python-worker": ["python", "-c", "print('isolated worker executed')"]
        }))
        monkeypatch.setattr(settings, "MCP_WORKER_SANDBOX_MODE", "host")
        monkeypatch.setattr(settings, "MCP_WORKER_HOST_MODE_ALLOWED", True)
        started = manager.start(task_label, "Smoke-test the worker subprocess", ["python-worker"], 30)
        deadline = time.monotonic() + 10
        job = manager.get(started["job_id"])
        while job["status"] in {"running", "cancelling"} and time.monotonic() < deadline:
            time.sleep(0.05)
            job = manager.get(started["job_id"])
        assert job["status"] == "completed", job
        result = job["results"][0]
        assert result["status"] == "completed", job["results"]
        assert "isolated worker executed" in result["output_tail"]
        assert result["path"] != str(repo)
        assert result["branch"].startswith("mcp-work/")
        workstream_manager.remove(result["workstream_id"])
    finally:
        session_manager.set_active_repo_name("Repo_A")
        repository_manager.remove_repository(repo_name)
        policy_engine.set_profile(previous_profile)
        settings.MCP_WORKER_COMMANDS = old_commands
        settings.MCP_WORKER_SANDBOX_MODE = old_mode
        settings.MCP_WORKER_HOST_MODE_ALLOWED = old_allowed
        worktrees = repo / ".mcp-worktrees"
        if worktrees.exists() and not any(worktrees.iterdir()):
            worktrees.rmdir()

def test_worker_runtime_cancels_running_process(test_environment, tmp_path, monkeypatch):
    import uuid
    from app.core.repository import repository_manager
    from app.core.workstreams import workstream_manager

    repo = tmp_path / "worker-cancel-repo"
    _make_repo(repo)
    repo_name = "WorkerCancel" + uuid.uuid4().hex[:6]
    repository_manager.add_repository(repo_name, str(repo), "worker cancellation test", True)
    previous_profile = policy_engine.profile
    old_commands = settings.MCP_WORKER_COMMANDS
    old_mode = settings.MCP_WORKER_SANDBOX_MODE
    old_allowed = settings.MCP_WORKER_HOST_MODE_ALLOWED
    task_label = "worker-cancel-" + uuid.uuid4().hex[:8]
    manager = WorkerRuntimeManager()
    try:
        session_manager.set_active_repo_name(repo_name)
        policy_engine.set_profile(PermissionProfile.FULL)
        monkeypatch.setattr(settings, "MCP_WORKER_COMMANDS", json.dumps({
            "slow-worker": ["python", "-c", "import time; time.sleep(20)"]
        }))
        monkeypatch.setattr(settings, "MCP_WORKER_SANDBOX_MODE", "host")
        monkeypatch.setattr(settings, "MCP_WORKER_HOST_MODE_ALLOWED", True)
        started = manager.start(task_label, "verify cancellation", ["slow-worker"], 30)
        deadline = time.monotonic() + 10
        while not any(key.startswith(started["job_id"] + ":") for key in manager._processes) and time.monotonic() < deadline:
            time.sleep(0.05)
        cancelled = manager.cancel(started["job_id"])
        assert cancelled["status"] == "cancelling"
        deadline = time.monotonic() + 10
        job = manager.get(started["job_id"])
        while job["status"] in {"running", "cancelling"} and time.monotonic() < deadline:
            time.sleep(0.05)
            job = manager.get(started["job_id"])
        assert job["status"] == "cancelled", job
        assert job["results"][0]["status"] == "cancelled"
        for workstream in [item for item in workstream_manager.list() if item.get("parent_task_id") == task_label]:
            workstream_manager.remove(workstream["id"])
    finally:
        session_manager.set_active_repo_name("Repo_A")
        repository_manager.remove_repository(repo_name)
        policy_engine.set_profile(previous_profile)
        settings.MCP_WORKER_COMMANDS = old_commands
        settings.MCP_WORKER_SANDBOX_MODE = old_mode
        settings.MCP_WORKER_HOST_MODE_ALLOWED = old_allowed
        worktrees = repo / ".mcp-worktrees"
        if worktrees.exists() and not any(worktrees.iterdir()):
            worktrees.rmdir()
