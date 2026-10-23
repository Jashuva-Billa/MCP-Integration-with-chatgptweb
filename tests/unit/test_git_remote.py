"""
Tests for git_push, git_fetch, and git_pull remote tools.
"""
import pytest
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


def test_git_push_allowed_in_trusted_admin(test_environment, monkeypatch):
    session_manager.set_active_repo_name("Repo_A")
    policy_engine.set_profile(PermissionProfile.TRUSTED_ADMIN)

    # Mock _run_git so we don't attempt an actual network push to a real upstream
    def mock_run_git(args, cwd, timeout=60):
        return {"stdout": "Everything up-to-date", "stderr": "", "exit_code": 0}

    monkeypatch.setattr(git, "_run_git", mock_run_git)
    res = git.git_push(remote="origin", branch="main")
    assert res["success"] is True
    assert res["remote"] == "origin"
    assert res["branch"] == "main"


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
