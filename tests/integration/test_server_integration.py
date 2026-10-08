import pytest
from starlette.testclient import TestClient
from app.main import create_app

def test_health_endpoint():
    app = create_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "chatgpt-mcp-server"

def test_mcp_redirect():
    app = create_app()
    client = TestClient(app, follow_redirects=False)
    response = client.get("/mcp")
    assert response.status_code in [307, 308, 200]
