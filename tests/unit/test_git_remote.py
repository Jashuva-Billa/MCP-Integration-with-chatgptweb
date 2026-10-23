"""
Tests for git_push, git_fetch, and git_pull remote tools.
"""
from app.tools import git
from app.core.permissions import PermissionProfile, policy_engine
from app.core.session import session_manager


def test_git_push_denied_in_safe_and_full(test_environment):
    session_manager.set_active_repo_name("Repo_A")

    # In SAFE profile
    policy_engine.set_profile(PermissionProfile.SAFE)
    res = git.git_push()
    assert "error" in res
    assert "Permission denied" in res["error"]

    # In FULL profile (push is disabled by default)
    policy_engine.set_profile(PermissionProfile.FULL)
    res = git.git_push()
    assert "error" in res
    assert "Permission denied" in res["error"]


def test_git_push_allowed_in_trusted_admin_when_explicitly_enabled(test_environment, monkeypatch):
    session_manager.set_active_repo_name("Repo_A")
    policy_engine.set_profile(PermissionProfile.TRUSTED_ADMIN)
    monkeypatch.setattr(git.settings, "MCP_GIT_PUSH_ENABLED", True)
    monkeypatch.setattr(git.settings, "MCP_GIT_PUSH_REQUIRE_APPROVAL", False)

    def mock_run_git(args, cwd, timeout=60):
        if args[0] == "rev-parse":
            return {"stdout": "abc123\n", "stderr": "", "exit_code": 0}
        if args[0] == "ls-remote":
            return {"stdout": "abc123\trefs/heads/main\n", "stderr": "", "exit_code": 0}
        return {"stdout": "Everything up-to-date", "stderr": "", "exit_code": 0}

    monkeypatch.setattr(git, "_run_git", mock_run_git)
    res = git.git_push(remote="origin", branch="main")
    assert res["success"] is True
    assert res["remote"] == "origin"
    assert res["branch"] == "main"
    assert res["remote_verified"] is True
    assert res["local_sha"] == res["remote_sha"] == "abc123"


def test_git_push_requires_exact_approved_target(test_environment, monkeypatch, tmp_path):
    from app.core.approvals import approval_manager
    session_manager.set_active_repo_name("Repo_A")
    policy_engine.set_profile(PermissionProfile.TRUSTED_ADMIN)
    monkeypatch.setattr(git.settings, "MCP_GIT_PUSH_ENABLED", True)
    monkeypatch.setattr(git.settings, "MCP_GIT_PUSH_REQUIRE_APPROVAL", True)
    monkeypatch.setattr(approval_manager, "path", tmp_path / "approvals.json")
    denied = git.git_push(remote="origin", branch="main")
    assert denied["approval_required"] is True
    request = approval_manager.request("git_push", "origin/main", "Test-only push approval")
    approval_manager.resolve(request["id"], "approved")

    def mock_run_git(args, cwd, timeout=60):
        if args[0] == "rev-parse":
            return {"stdout": "abc123\n", "stderr": "", "exit_code": 0}
        if args[0] == "ls-remote":
            return {"stdout": "abc123\trefs/heads/main\n", "stderr": "", "exit_code": 0}
        return {"stdout": "pushed", "stderr": "", "exit_code": 0}

    monkeypatch.setattr(git, "_run_git", mock_run_git)
    result = git.git_push(remote="origin", branch="main", approval_id=request["id"])
    assert result["success"] is True
    assert result["remote_verified"] is True


def test_git_fetch_and_pull(test_environment, monkeypatch):
    session_manager.set_active_repo_name("Repo_A")
    policy_engine.set_profile(PermissionProfile.TRUSTED_ADMIN)

    def mock_run_git(args, cwd, timeout=60):
        return {"stdout": "Fetched refs", "stderr": "", "exit_code": 0}

    monkeypatch.setattr(git, "_run_git", mock_run_git)

    # Fetch
    fetch_res = git.git_fetch(remote="origin", prune=True)
    assert fetch_res["success"] is True

    # Pull
    pull_res = git.git_pull(remote="origin", branch="main", rebase=True)
    assert pull_res["success"] is True
