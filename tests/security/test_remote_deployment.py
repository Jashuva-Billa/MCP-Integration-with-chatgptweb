import pytest

from app.config import settings
from app.main import create_app


def test_cloud_mode_fails_closed_when_authentication_disabled(monkeypatch):
    monkeypatch.setattr(settings, "MCP_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setattr(settings, "MCP_AUTH_ENABLED", False)
    monkeypatch.setattr(settings, "MCP_AUTH_TOKEN", "a" * 48)
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "mcp.example.com")
    with pytest.raises(RuntimeError, match="MCP_AUTH_ENABLED=true"):
        create_app()


def test_cloud_mode_requires_long_bearer_token(monkeypatch):
    monkeypatch.setattr(settings, "MCP_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setattr(settings, "MCP_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "MCP_AUTH_TOKEN", "short")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "mcp.example.com")
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        create_app()


def test_cloud_mode_requires_exact_allowed_host(monkeypatch):
    monkeypatch.setattr(settings, "MCP_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setattr(settings, "MCP_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "MCP_AUTH_TOKEN", "a" * 48)
    monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
    with pytest.raises(RuntimeError, match="MCP_ALLOWED_HOSTS"):
        create_app()


def test_cloud_mode_rejects_wildcard_allowed_host(monkeypatch):
    monkeypatch.setattr(settings, "MCP_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setattr(settings, "MCP_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "MCP_AUTH_TOKEN", "a" * 48)
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "*.onrender.com")
    with pytest.raises(RuntimeError, match="Wildcard hosts"):
        create_app()


def test_cloud_mode_rejects_wildcard_origin(monkeypatch):
    monkeypatch.setattr(settings, "MCP_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setattr(settings, "MCP_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "MCP_AUTH_TOKEN", "a" * 48)
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "mcp.example.com")
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", "*")
    with pytest.raises(RuntimeError, match="MCP_ALLOWED_ORIGINS"):
        create_app()


def test_cloud_mode_accepts_secure_configuration(monkeypatch):
    monkeypatch.setattr(settings, "MCP_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setattr(settings, "MCP_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "MCP_AUTH_TOKEN", "a" * 48)
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "mcp.example.com")
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", "https://chatgpt.com")
    app = create_app()
    assert any(getattr(route, "path", None) == "/mcp" for route in app.routes)


def test_cloud_add_repository_cannot_register_outside_workspace(monkeypatch, tmp_path):
    from app.tools.workspace import add_repository

    allowed_root = tmp_path / "workspaces"
    allowed_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setattr(settings, "MCP_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setattr(settings, "MCP_WORKSPACE_ROOT", str(allowed_root))

    result = add_repository("outside", str(outside))
    assert "only allows registering repositories inside MCP_WORKSPACE_ROOT" in result["error"]
