import json

from app.tools import github_auth, git_provider


def test_device_flow_requires_client_id(monkeypatch):
    monkeypatch.delenv("MCP_GITHUB_CLIENT_ID", raising=False)
    assert github_auth.github_connect_start()["success"] is False


def test_selection_rejects_invalid_repo_without_saving(monkeypatch, tmp_path):
    monkeypatch.setattr(github_auth, "get_access_token", lambda: "fake-token")
    monkeypatch.setattr(github_auth, "_SELECTION_PATH", tmp_path / "selected.json")
    monkeypatch.setattr(github_auth, "_github_get", lambda *a, **k: (200, {"full_name": "owner/repo"}))
    result = github_auth.github_select_repositories(["not-a-repo"])
    assert result["success"] is False
    assert not (tmp_path / "selected.json").exists()


def test_selection_validates_visibility_and_persists(monkeypatch, tmp_path):
    monkeypatch.setattr(github_auth, "get_access_token", lambda: "fake-token")
    monkeypatch.setattr(github_auth, "_SELECTION_PATH", tmp_path / "selected.json")
    monkeypatch.setattr(github_auth, "_github_get", lambda *a, **k: (200, {"full_name": "owner/repo"}))
    result = github_auth.github_select_repositories(["owner/repo"])
    assert result["success"] is True
    assert json.loads((tmp_path / "selected.json").read_text())["repositories"] == ["owner/repo"]
    assert github_auth.get_allowed_repositories() == {"owner/repo"}


def test_select_does_not_save_if_repo_not_visible(monkeypatch, tmp_path):
    monkeypatch.setattr(github_auth, "get_access_token", lambda: "fake-token")
    monkeypatch.setattr(github_auth, "_SELECTION_PATH", tmp_path / "selected.json")
    monkeypatch.setattr(github_auth, "_github_get", lambda *a, **k: (404, {}))
    result = github_auth.github_select_repositories(["owner/private"])
    assert result["success"] is False
    assert not (tmp_path / "selected.json").exists()


def test_selected_repositories_override_legacy_allowlist(monkeypatch, tmp_path):
    monkeypatch.setattr(github_auth, "_SELECTION_PATH", tmp_path / "selected.json")
    (tmp_path / "selected.json").write_text(json.dumps({"repositories": ["owner/selected"]}))
    from app.config import settings
    monkeypatch.setattr(settings, "MCP_GITHUB_ALLOWED_REPOS", "owner/legacy,owner/selected")
    assert git_provider._repo("owner/selected") == "owner/selected"
    assert git_provider._repo("owner/legacy") is None


def test_connect_complete_handles_pending_authorization(monkeypatch):
    github_auth._PENDING.clear()
    github_auth._PENDING.update({"device_code": "device", "client_id": "client", "interval": 5})
    monkeypatch.setattr(github_auth, "_keyring", lambda: object())
    monkeypatch.setattr(github_auth, "_request_json", lambda *a, **k: {"error": "authorization_pending"})
    result = github_auth.github_connect_complete()
    assert result["pending"] is True
    assert result["retry_after_seconds"] == 5
    github_auth._PENDING.clear()
