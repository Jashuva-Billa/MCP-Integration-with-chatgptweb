from mcp.server import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse
import uvicorn

mcp = MCPServer("Multi-Repo-Code-Agent-MCP")

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request):
    return JSONResponse({"status": "ok", "service": "chatgpt-mcp-server"})

app = mcp.sse_app()
print("Starlette app created with custom routes:", [r.path for r in app.routes if hasattr(r, 'path')])
