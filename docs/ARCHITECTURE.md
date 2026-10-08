# Architecture Specification

## 1. System Topology

```
┌────────────────────────────────────────────────────────┐
│                      ChatGPT Web                       │
│             (Remote Reasoning & Coding Agent)          │
└───────────────────────────┬────────────────────────────┘
                            │ HTTPS (Bearer Auth / SSE Transport)
                            ▼
┌────────────────────────────────────────────────────────┐
│       Cloudflare Tunnel (trycloudflare.com / ngrok)    │
└───────────────────────────┬────────────────────────────┘
                            │ Local Reverse Proxy
                            ▼
┌────────────────────────────────────────────────────────┐
│     Standalone MCP Server (MCP-Integration-with-web)   │
│  - ASGI / FastMCP / Streamable HTTP & SSE Engine       │
│  - Constant-time Bearer Authentication Gate            │
│  - Session-Scoped Workspace Switcher                   │
│  - Security Sandbox & Canonical Path Verifier          │
│  - Dynamic External Registry (config/repositories.json)│
└────────────┬─────────────────────────────┬─────────────┘
             │                             │
    Repo A (Active)               Repo B (Isolated)
             ▼                             ▼
┌─────────────────────────┐   ┌──────────────────────────┐
│ C:\Development\         │   │ C:\Development\          │
│ AI_jobs_apply           │   │ agentic-sdlc             │
└────────────┬────────────┘   └──────────────────────────┘
             │ Direct on-disk file writes
             ▼
┌─────────────────────────┐
│         VS Code         │
│  (Local Code View/IDE)  │
└─────────────────────────┘
```

---

## 2. Core Architectural Principles

1. **Standalone Infrastructure**: The MCP server is completely decoupled from application repositories. Application code is never imported into the MCP server process, and application repositories do not require MCP dependencies.
2. **Generic Workspaces**: Every target project is managed as a standalone directory on disk.
3. **Canonical Path Sandboxing**: Filesystem operations strictly verify that resolved targets remain within the active repository root. Symlinks escaping the root are forbidden.
4. **Session Isolation**: Multi-threaded session manager ensures different conversations/clients operate on isolated workspaces.
5. **Tool Categorization**:
   - **Workspace**: Discovers and switches active repository contexts.
   - **Filesystem**: Safe CRUD operations directly modifying files on disk for VS Code.
   - **Search**: Multi-file text search with context lines and exclusion rules.
   - **Code Intelligence**: AST parsing for symbols, functions, classes, and references.
   - **Terminal**: Sandboxed subprocess execution with timeout, output limits, and command allowlisting.
   - **Git**: Non-destructive, read-only version control inspections.
   - **Repository Analysis**: Deep architecture and dependency inspection.
