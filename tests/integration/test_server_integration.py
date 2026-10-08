import pytest
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
    assert "/mcp" in route_paths
    assert "/sse" in route_paths

