---
name: mcp-server-development
description: Building, testing, and extending Model Context Protocol servers
version: 1.0.0
activation: ["app/main.py", "app/tools/", "app/core/"]
tags: [mcp, server, tools, fastmcp, starlette, uvicorn]
requires_profile: full
---

# MCP Server Development Skill

## Adding a New Tool
1. Create the implementation in `app/tools/your_tool.py`.
2. Add security checks using `security_engine.sanitize_and_resolve_path`.
3. Add permission check: `policy_engine.require_fs_write()` (or relevant capability).
4. Register in `app/main.py`: `mcp.tool()(your_tool.function_name)`.
5. Export from `app/tools/__init__.py`.
6. Write tests in `tests/unit/test_your_tool.py`.

## Testing
1. Unit test each tool function with mock session/security.
2. Integration test against the live server with `httpx`.
3. Security test with path traversal and command injection inputs.

## Health Check
- GET `/health` should return `{"status": "ok"}`.
- All endpoints require Bearer token when `MCP_AUTH_ENABLED=true`.
