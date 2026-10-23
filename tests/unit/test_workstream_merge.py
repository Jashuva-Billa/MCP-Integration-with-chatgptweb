from __future__ import annotations

import subprocess
import uuid

from app.core.approvals import approval_manager
from app.core.permissions import PermissionProfile, policy_engine
from app.core.repository import repository_manager
from app.core.session import session_manager
from app.core.workstreams import WorkstreamManager


def _git(args: list[str], cwd) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)


def test_merge_requires_validation_and_exact_approval(test_environment, tmp_path, monkeypatch):
    repo = tmp_path / "clean-repo"
    repo.mkdir()
    _git(["init"], repo)
    _git(["config", "user.name", "Test User"], repo)
    _git(["config", "user.email", "test@example.com"], repo)
    (repo / ".gitignore").write_text(".mcp-worktrees/\n", encoding="utf-8")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(["add", ".gitignore", "README.md"], repo)
    _git(["commit", "-m", "baseline"], repo)
    target_branch = _git(["branch", "--show-current"], repo).stdout.strip()

    repo_name = "WorkstreamMerge" + uuid.uuid4().hex[:6]
    repository_manager.add_repository(repo_name, str(repo), "temporary merge test", True)
    previous_profile = policy_engine.profile
    monkeypatch.setattr(approval_manager, "path", tmp_path / "approvals.json")
    monkeypatch.setattr("app.tools.terminal.run_command", lambda command, **kwargs: {
        "exit_code": 0, "stdout": "2 passed", "stderr": "", "duration_seconds": 0.1
    })
    try:
        policy_engine.set_profile(PermissionProfile.FULL)
        session_manager.set_active_repo_name(repo_name)
        manager = WorkstreamManager(tmp_path / "workstreams.json")
        task_id = "merge-" + uuid.uuid4().hex[:8]
        workstream = manager.create(task_id, "worker-a")
        feature_file = __import__("pathlib").Path(workstream["path"]) / "feature.txt"
        feature_file.write_text("implemented\n", encoding="utf-8")
        _git(["add", "feature.txt"], workstream["path"])
        _git(["commit", "-m", "worker implementation"], workstream["path"])

        manager.validate(workstream["id"], "pytest -q")
        target = f"{workstream['branch']}->{target_branch}"
        try:
            manager.merge(workstream["id"], target_branch, "pytest -q", "missing-approval")
        except ValueError as exc:
            assert "approved, unexpired git_merge request" in str(exc)
        else:
            raise AssertionError("merge must require an exact approval")
        request = approval_manager.request("git_merge", target, "test merge")
        approval_manager.resolve(request["id"], "approved")
        result = manager.merge(workstream["id"], target_branch, "pytest -q", request["id"])
        assert result["success"] is True
        assert result["tests_passed"] is True
        assert (repo / "feature.txt").read_text(encoding="utf-8") == "implemented\n"
    finally:
        session_manager.set_active_repo_name("Repo_A")
        repository_manager.remove_repository(repo_name)
        policy_engine.set_profile(previous_profile)
