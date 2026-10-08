from mcp.server import MCPServer
s = MCPServer("Test")
print("MCPServer attributes:")
for a in dir(s):
    if not a.startswith("_"):
        print(f"  {a}")

print("\nTransport options in mcp.server:")
import mcp.server.sse
import mcp.server.streamable_http
print("mcp.server has sse and streamable_http")
