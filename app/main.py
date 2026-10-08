import sys
from pathlib import Path

# Ensure project root is in sys.path for direct script execution
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import logging
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

try:
    from mcp.server import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer

from app.config import settings
from app.logging_config import setup_logging
from app.auth.auth import BearerAuthMiddleware
from app.core.session import session_manager
from app.core.repository import repository_manager
from app.tools import (
    workspace,
    filesystem,
    search,
    code_intelligence,
    terminal,
    git,
    repository_analysis
)

logger = setup_logging(settings.MCP_LOG_LEVEL)

# MCP Server Instance
mcp = MCPServer("Multi-Repo-Code-Agent-MCP")

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

# 3. Register Search Tools
mcp.tool()(search.search_code)

# 4. Register Code Intelligence Tools
mcp.tool()(code_intelligence.find_symbol)
mcp.tool()(code_intelligence.find_references)
mcp.tool()(code_intelligence.list_functions)
mcp.tool()(code_intelligence.list_classes)
mcp.tool()(code_intelligence.get_file_structure)

# 5. Register Terminal Execution Tool
mcp.tool()(terminal.run_command)

# 6. Register Git Inspection Tools
mcp.tool()(git.git_status)
mcp.tool()(git.git_diff)
mcp.tool()(git.git_branch)
mcp.tool()(git.git_log)
mcp.tool()(git.git_show)
mcp.tool()(git.git_changed_files)

# 7. Register Repository Analysis Tool
mcp.tool()(repository_analysis.analyze_repository)

# 8. Register Health Route
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Returns real-time health, transport, and active workspace metadata."""
    active_name = session_manager.get_active_repo_name()
    repos = repository_manager.list_repositories()
    return JSONResponse({
        "status": "ok",
        "service": "chatgpt-mcp-server",
        "version": "1.0.0",
        "transports": ["Streamable HTTP (/mcp)", "SSE (/sse)"],
        "active_repository": active_name,
        "configured_repositories_count": len(repos),
        "auth_enabled": bool(settings.MCP_AUTH_ENABLED or settings.MCP_AUTH_TOKEN),
        "host": settings.MCP_HOST,
        "port": settings.MCP_PORT
    })

def create_app() -> Starlette:
    """
    Builds and returns a unified Starlette application supporting both
    Streamable HTTP (/mcp) and SSE (/sse, /messages) transports,
    with custom routes and Bearer authentication middleware.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    # Allow tunnel and proxy traffic (e.g., Cloudflare tunnel, ChatGPT Web)
    transport_sec = TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
        allowed_hosts=["*"],
        allowed_origins=["*"],
    )

    # Create Streamable HTTP transport app (/mcp)
    http_app = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        transport_security=transport_sec,
    )
    
    # Create SSE transport app (/sse)
    sse_app = mcp.sse_app(
        sse_path="/sse",
        transport_security=transport_sec,
    )

    # Merge SSE routes into the HTTP app so all endpoints share the same lifespan/port
    for route in sse_app.routes:
        path = getattr(route, "path", None)
        if path and path not in [getattr(cr, "path", None) for cr in http_app.routes]:
            http_app.routes.append(route)

    if settings.MCP_AUTH_ENABLED or settings.MCP_AUTH_TOKEN:
        http_app.add_middleware(BearerAuthMiddleware)

    return http_app

def start_server(host: str = None, port: int = None):
    """Starts the standalone MCP ASGI server with Uvicorn."""
    srv_host = host or settings.MCP_HOST
    srv_port = port or settings.MCP_PORT

    logger.info("=" * 70)
    logger.info("Standalone Multi-Repository MCP Server Initializing")
    logger.info(f"Listening: http://{srv_host}:{srv_port}")
    logger.info(f"Health Endpoint: http://{srv_host}:{srv_port}/health")
    logger.info(f"Streamable HTTP Transport: http://{srv_host}:{srv_port}/mcp")
    logger.info(f"SSE Transport: http://{srv_host}:{srv_port}/sse")
    logger.info(f"Authentication: {'ENABLED (Bearer Token required)' if (settings.MCP_AUTH_ENABLED or settings.MCP_AUTH_TOKEN) else 'DISABLED (Local Dev Mode)'}")
    logger.info("=" * 70)

    app = create_app()
    uvicorn.run(app, host=srv_host, port=srv_port, log_level=settings.MCP_LOG_LEVEL.lower())

if __name__ == "__main__":
    start_server()
