from __future__ import annotations

import uuid

from app.core.approvals import ApprovalManager
from app.core.permissions import PermissionProfile, policy_engine
from app.core.session import session_manager
from app.core.workstreams import WorkstreamManager


def test_approval_lifecycle_is_targeted_and_expires(tmp_path):
    manager = ApprovalManager(tmp_path / "approvals.json")
    request = manager.request("git_push", "origin/main", "release", ttl_minutes=60)
    assert request["status"] == "pending"
    assert manager.is_approved(request["id"], "git_push", "origin/main") is False
    manager.resolve(request["id"], "approved", "test-user")
    assert manager.is_approved(request["id"], "git_push", "origin/main") is True
    assert manager.is_approved(request["id"], "git_push", "origin/dev") is False
    assert manager.consume_approved(request["id"], "git_push", "origin/main") is True
    assert manager.consume_approved(request["id"], "git_push", "origin/main") is False
    assert manager.list(status="consumed")[0]["id"] == request["id"]


def test_approval_cannot_be_resolved_twice(tmp_path):
    manager = ApprovalManager(tmp_path / "approvals.json")
    request = manager.request("git_merge", "feature->main")
    manager.resolve(request["id"], "denied")
    try:
        manager.resolve(request["id"], "approved")
    except ValueError as exc:
        assert "already denied" in str(exc)
    else:
        raise AssertionError("resolved approvals must be immutable")


def test_workstream_uses_isolated_git_worktree(test_environment, tmp_path):
    original_profile = policy_engine.profile
    try:
        policy_engine.set_profile(PermissionProfile.FULL)
        session_manager.set_active_repo_name("Repo_A")
        manager = WorkstreamManager(tmp_path / "workstreams.json")
        task_id = "task-" + uuid.uuid4().hex[:8]
        row = manager.create(task_id, "worker-a")
        assert row["branch"] == f"mcp-work/{task_id}/worker-a"
        assert row["path"] != str(test_environment["repo_a"])
        assert (test_environment["repo_a"] / ".mcp-worktrees" / f"{task_id}-worker-a").is_dir()
        assert manager.list(task_id)[0]["id"] == row["id"]
        removed = manager.remove(row["id"])
        assert removed["success"] is True
        assert manager.list(task_id) == []
    finally:
        policy_engine.set_profile(original_profile)
