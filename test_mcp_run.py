from mcp.server import MCPServer
import inspect

mcp = MCPServer("Multi-Repo-Code-Agent-MCP")
print("mcp.run args:", inspect.signature(mcp.run))
try:
    app = mcp.sse_app()
    print("mcp.sse_app() returns:", type(app))
except Exception as e:
    print("sse_app error:", e)
