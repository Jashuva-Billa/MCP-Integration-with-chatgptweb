import subprocess

import pytest

from app.config import settings
from app.core import github_workspace


def test_only_allowlisted_github_repository_is_accepted(monkeypatch):
    monkeypatch.setattr(settings, "MCP_GITHUB_ALLOWED_REPOS", "Jashuva-Billa/MCP-Integration-with-chatgptweb")
    assert github_workspace.normalize_github_url(
        "https://github.com/Jashuva-Billa/MCP-Integration-with-chatgptweb"
    ) == "https://github.com/Jashuva-Billa/MCP-Integration-with-chatgptweb.git"

    with pytest.raises(github_workspace.GitHubWorkspaceError, match="not in MCP_GITHUB_ALLOWED_REPOS"):
        github_workspace.normalize_github_url("https://github.com/other/private-repo")


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/owner/repo",
        "https://github.com.evil.test/owner/repo",
        "https://user:password@github.com/owner/repo",
        "https://github.com/owner/repo/tree/main",
        "https://github.com/owner/repo?token=secret",
        "https://github.com/../repo",
    ],
)
def test_rejects_unsafe_github_urls(monkeypatch, url):
    monkeypatch.setattr(settings, "MCP_GITHUB_ALLOWED_REPOS", "owner/repo")
    with pytest.raises(github_workspace.GitHubWorkspaceError):
        github_workspace.normalize_github_url(url)


def test_clone_creates_workspace_and_registers_it(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "MCP_GITHUB_ALLOWED_REPOS", "owner/repo")
    monkeypatch.setattr(settings, "MCP_GITHUB_TOKEN", "")
    monkeypatch.setattr(settings, "MCP_WORKSPACE_ROOT", str(tmp_path))

    def fake_run(command, cwd, env, text, capture_output, timeout, check):
        assert command[:3] == ["git", "clone", "--single-branch"]
        assert command[-1] == str(tmp_path / "repo-workspace")
        (tmp_path / "repo-workspace").mkdir()
        (tmp_path / "repo-workspace" / "README.md").write_text("test", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    registered = {}
    def fake_register(name, path, description, enabled):
        registered.update(name=name, path=path, description=description, enabled=enabled)
        return dict(registered)

    monkeypatch.setattr(github_workspace.subprocess, "run", fake_run)
    monkeypatch.setattr(github_workspace.repository_manager, "add_repository", fake_register)

    result = github_workspace.clone_github_repository(
        "https://github.com/owner/repo.git", "repo-workspace"
    )
    assert result["success"] is True
    assert registered["name"] == "repo-workspace"
    assert (tmp_path / "repo-workspace" / "README.md").exists()


def test_clone_refuses_to_overwrite_existing_workspace(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "MCP_GITHUB_ALLOWED_REPOS", "owner/repo")
    monkeypatch.setattr(settings, "MCP_WORKSPACE_ROOT", str(tmp_path))
    (tmp_path / "existing").mkdir()
    with pytest.raises(github_workspace.GitHubWorkspaceError, match="already exists"):
        github_workspace.clone_github_repository("https://github.com/owner/repo", "existing")
