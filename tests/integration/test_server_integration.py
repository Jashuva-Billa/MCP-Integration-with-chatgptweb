from starlette.testclient import TestClient
from app.main import create_app

def test_health_endpoint():
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "chatgpt-mcp-server"
        assert "Streamable HTTP (/mcp)" in data["transports"]
        assert "SSE (/sse)" in data["transports"]

def test_streamable_http_and_sse_routes():
    app = create_app()
    route_paths = [getattr(r, "path", None) for r in app.routes]
    assert "/health" in route_paths
    assert "/tools" in route_paths
    assert "/dashboard" in route_paths
    assert "/api/tasks" in route_paths
    assert "/api/diff" in route_paths
    assert "/api/checkpoints" in route_paths
    assert "/api/rollback" in route_paths
    assert "/api/workers" in route_paths
    assert "/api/worker" in route_paths
    assert "/api/worker/cancel" in route_paths
    assert "/api/worker-benchmarks" in route_paths
    assert "/api/worker-benchmarks/start" in route_paths
    assert "/api/approvals" in route_paths
    assert "/mcp" in route_paths
    assert "/sse" in route_paths


def test_dashboard_and_task_apis():
    app = create_app()
    with TestClient(app) as client:
        page = client.get("/dashboard")
        assert page.status_code == 200
        assert "MCP Coding Tool" in page.text
        tasks = client.get("/api/tasks")
        approvals = client.get("/api/approvals")
        events = client.get("/api/events?limit=10")
        diff = client.get("/api/diff")
        checkpoints = client.get("/api/checkpoints")
        assert tasks.status_code == 200 and "tasks" in tasks.json()
        assert approvals.status_code == 200 and "approvals" in approvals.json()
        assert events.status_code == 200 and "events" in events.json()
        assert diff.status_code == 200 and "diff" in diff.json()
        assert checkpoints.status_code == 200 and "checkpoints" in checkpoints.json()


def test_dashboard_requires_bearer_auth_when_auth_is_enabled(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "MCP_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "MCP_AUTH_TOKEN", "test-token-that-is-long-enough-for-middleware")
    monkeypatch.setattr(settings, "MCP_HOST", "127.0.0.1")
    app = create_app()
    with TestClient(app) as client:
        assert client.get("/dashboard").status_code == 401
        response = client.get("/dashboard", headers={"Authorization": "Bearer test-token-that-is-long-enough-for-middleware"})
        assert response.status_code == 200
        assert client.get("/api/workers").status_code == 401


def test_server_refuses_unauthenticated_non_loopback_bind(monkeypatch):
    import pytest
    from app.config import settings
    monkeypatch.setattr(settings, "MCP_AUTH_ENABLED", False)
    monkeypatch.setattr(settings, "MCP_HOST", "0.0.0.0")
    monkeypatch.setattr(settings, "MCP_DEPLOYMENT_MODE", "local")
    with pytest.raises(RuntimeError, match="non-loopback host"):
        create_app()


def test_start_server_cannot_bypass_bind_auth_with_host_override(monkeypatch):
    import pytest
    from app.config import settings
    from app.main import start_server
    monkeypatch.setattr(settings, "MCP_AUTH_ENABLED", False)
    monkeypatch.setattr(settings, "MCP_AUTH_TOKEN", "")
    monkeypatch.setattr(settings, "MCP_HOST", "127.0.0.1")
    with pytest.raises(RuntimeError, match="Non-loopback server binds require"):
        start_server(host="0.0.0.0", port=8766)


def test_dashboard_can_be_disabled(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "MCP_AUTH_ENABLED", False)
    monkeypatch.setattr(settings, "MCP_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "MCP_DASHBOARD_ENABLED", False)
    app = create_app()
    with TestClient(app) as client:
        assert client.get("/dashboard").status_code == 404
        assert client.get("/api/workers").status_code == 404


def test_tools_endpoint():
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/tools")
        assert response.status_code == 200
        data = response.json()
        assert data["total_tools"] == 90
        assert "categories" in data
        assert "workspace_management" in data["categories"]
        assert "command_execution" in data["categories"]
        assert "git_write_and_remote" in data["categories"]
        assert "task_state" in data["categories"]
        assert "execution_profile" in data["categories"]
        assert "autonomous_execution" in data["categories"]
        assert "git_recovery" in data["categories"]
        assert "approvals" in data["categories"]
        assert "parallel_workstreams" in data["categories"]
        assert "worker_runtime" in data["categories"]
        assert "independent_verification" in data["categories"]
        assert "benchmark_harness" in data["categories"]


