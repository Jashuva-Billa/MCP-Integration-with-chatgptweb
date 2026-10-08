from mcp.server import MCPServer
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

mcp = MCPServer(name="Multi-Repo-Code-Agent-MCP")

@mcp.tool()
def hello() -> str:
    return "Hello world"

async def health_check(request):
    return JSONResponse({"status": "ok", "service": "chatgpt-mcp-server"})

# Test custom_route or Starlette mounting
@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    return JSONResponse({"status": "ok", "service": "chatgpt-mcp-server"})

print("MCPServer initialized successfully with custom_route /health")
