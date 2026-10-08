import logging
import sys
import uvicorn
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

try:
    from mcp.server import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP

from server.config import config
from server.session import session_manager
from tools import workspace, filesystem, search, terminal, git

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("mcp_server")

# FastMCP application instance
mcp = FastMCP("Multi-Repo-Code-Agent-MCP")

# 1. Register Workspace Management Tools
mcp.tool()(workspace.list_repositories)
mcp.tool()(workspace.select_repository)
mcp.tool()(workspace.get_current_repository)
mcp.tool()(workspace.add_repository)
mcp.tool()(workspace.remove_repository)

# 2. Register Filesystem Tools
mcp.tool()(filesystem.list_files)
mcp.tool()(filesystem.read_file)
mcp.tool()(filesystem.write_file)
mcp.tool()(filesystem.create_directory)
mcp.tool()(filesystem.delete_file)

# 3. Register Code Search Tool
mcp.tool()(search.search_code)

# 4. Register Terminal Execution Tool
mcp.tool()(terminal.run_command)

# 5. Register Git Inspection Tools
mcp.tool()(git.git_status)
mcp.tool()(git.git_diff)
mcp.tool()(git.git_branch)

# 6. Register Health and Compatibility Routes
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request):
    return JSONResponse({
        "status": "ok",
        "service": "chatgpt-mcp-server",
        "active_repository": session_manager.get_active_repo_name(),
        "host": config.MCP_HOST,
        "port": config.MCP_PORT
    })

@mcp.custom_route("/mcp", methods=["GET", "POST"])
async def mcp_compatibility_route(request: Request):
    return RedirectResponse(url="/sse")

class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow health checks and root without auth
        if request.url.path in ["/health", "/", "/favicon.ico"]:
            return await call_next(request)

        if config.AUTH_TOKEN:
            auth_header = request.headers.get("Authorization", "")
            expected = f"Bearer {config.AUTH_TOKEN}"
            if not auth_header or auth_header.strip() != expected:
                logger.warning(f"Unauthorized request rejected from {request.client.host if request.client else 'unknown'}")
                return JSONResponse({"error": "Unauthorized. Invalid or missing Bearer token."}, status_code=401)

        return await call_next(request)

def start_server():
    logger.info("=" * 70)
    logger.info("Standalone Multi-Repository MCP Server Initializing")
    logger.info(f"Host: {config.MCP_HOST}:{config.MCP_PORT}")
    logger.info(f"Streamable HTTP & SSE Endpoint: http://{config.MCP_HOST}:{config.MCP_PORT}/sse")
    logger.info(f"Health Endpoint: http://{config.MCP_HOST}:{config.MCP_PORT}/health")
    logger.info(f"Authentication: {'ENABLED (Bearer Token required)' if config.AUTH_TOKEN else 'DISABLED (Local Dev Mode)'}")
    logger.info("=" * 70)
    
    app = mcp.sse_app()
    if config.AUTH_TOKEN:
        app.add_middleware(BearerAuthMiddleware)
        
    uvicorn.run(app, host=config.MCP_HOST, port=config.MCP_PORT, log_level="info")

if __name__ == "__main__":
    start_server()
