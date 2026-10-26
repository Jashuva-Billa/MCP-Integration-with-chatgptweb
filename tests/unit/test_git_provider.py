from app.tools import git_provider


def test_repo_requires_owner_repo_and_allowlist(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "MCP_GITHUB_ALLOWED_REPOS", "owner/repo")
    assert git_provider._repo("not-a-repo") is None
    assert git_provider._repo("owner/repo") == "owner/repo"
    monkeypatch.setattr(settings, "MCP_GITHUB_ALLOWED_REPOS", "")
    assert git_provider._repo("owner/repo") is None


def test_repo_allowlist_blocks_unlisted(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "MCP_GITHUB_ALLOWED_REPOS", "trusted/project")
    assert git_provider._repo("trusted/project") == "trusted/project"
    assert git_provider._repo("other/project") is None


def test_workflow_runs_sanitizes_api_response(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "MCP_GITHUB_ALLOWED_REPOS", "owner/repo")
    monkeypatch.setattr(git_provider, "_request", lambda *a, **k: {"success": True, "data": {"total_count": 1, "workflow_runs": [{"id": 3, "name": "CI", "status": "completed", "conclusion": "success", "head_sha": "abc", "head_branch": "main", "html_url": "https://github.com/owner/repo/actions/runs/3"}]}})
    result = git_provider.github_workflow_runs("owner/repo")
    assert result["success"] is True
    assert result["workflow_runs"][0]["conclusion"] == "success"
    assert "token" not in str(result).lower()


def test_no_token_returns_actionable_error(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "MCP_GITHUB_ALLOWED_REPOS", "owner/repo")
    monkeypatch.setattr(settings, "MCP_GITHUB_TOKEN", "")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(git_provider.policy_engine, "require_network", lambda *_: None)
    result = git_provider._request("/repos/owner/repo")
    assert result["success"] is False
    assert "not configured" in result["error"]
