import hmac
import logging
from typing import Optional, Set
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings

logger = logging.getLogger("mcp_server.auth")

PUBLIC_ENDPOINTS: Set[str] = {
    "/health",
    "/",
    "/favicon.ico",
    "/docs",
    "/openapi.json"
}

def verify_token(provided_token: str, expected_token: str) -> bool:
    """Constant-time token verification to protect against timing attacks."""
    if not provided_token or not expected_token:
        return False
    return hmac.compare_digest(provided_token.strip(), expected_token.strip())

class BearerAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces Bearer Token authentication when MCP_AUTH_ENABLED is True.
    Exempts public endpoints such as /health.
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        # Check if auth is disabled globally
        if not settings.MCP_AUTH_ENABLED and not settings.MCP_AUTH_TOKEN:
            return await call_next(request)

        # Allow public health check endpoints
        if request.url.path in PUBLIC_ENDPOINTS:
            return await call_next(request)

        auth_header: Optional[str] = request.headers.get("Authorization")
        
        if not auth_header:
            logger.warning(f"Unauthorized request to '{request.url.path}': Missing Authorization header.")
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized. Missing Authorization header with Bearer token."}
            )

        parts = auth_header.strip().split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            logger.warning(f"Unauthorized request to '{request.url.path}': Malformed Authorization header.")
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized. Authorization header must be in 'Bearer <token>' format."}
            )

        provided_token = parts[1]
        if not verify_token(provided_token, settings.MCP_AUTH_TOKEN):
            logger.warning(f"Unauthorized request to '{request.url.path}': Invalid Bearer token.")
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized. Invalid Bearer token."}
            )

        return await call_next(request)
