import pytest
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from app.auth.auth import BearerAuthMiddleware
from app.config import settings

def test_bearer_auth_enforcement(monkeypatch):
    monkeypatch.setattr(settings, "MCP_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "MCP_AUTH_TOKEN", "valid-test-token-12345")

    async def endpoint(request):
        return JSONResponse({"data": "secret_data"})

    async def health(request):
        return JSONResponse({"status": "ok"})

    app = Starlette(routes=[
        Route("/health", health),
        Route("/secure", endpoint)
    ])
    app.add_middleware(BearerAuthMiddleware)
    client = TestClient(app)

    # 1. Health is public without token
    assert client.get("/health").status_code == 200

    # 2. Secure endpoint rejected without token
    assert client.get("/secure").status_code == 401

    # 3. Secure endpoint rejected with invalid token
    assert client.get("/secure", headers={"Authorization": "Bearer wrong-token"}).status_code == 401

    # 4. Secure endpoint accepted with valid token
    res = client.get("/secure", headers={"Authorization": "Bearer valid-test-token-12345"})
    assert res.status_code == 200
    assert res.json()["data"] == "secret_data"
