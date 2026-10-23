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


def test_tools_endpoint():
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/tools")
        assert response.status_code == 200
        data = response.json()
        assert data["total_tools"] == 81
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


