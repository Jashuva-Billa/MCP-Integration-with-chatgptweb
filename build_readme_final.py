import os
from pathlib import Path

readme_content = """# Standalone Reusable Multi-Repository MCP Server

An infrastructure-level Model Context Protocol (MCP) server that connects **ChatGPT Web** (the reasoning/coding agent) to **arbitrary local repositories** on Windows, while **VS Code** remains purely an IDE for inspecting and working with local files.

---

## 1. Architecture Overview

```
                      CHATGPT WEB
                           │
                      HTTPS / MCP
                           │
             Secure HTTPS Ingress (Cloudflare / ngrok)
                           │
              STANDALONE MCP SERVER
           (C:\\Development\\chatgpt-mcp-server)
                           │
                  Repository Registry
              (config/repositories.yaml)
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
     Repository A     Repository B     Repository C
  (C:\\Dev\\RepoA)   (C:\\Dev\\RepoB)   (C:\\Dev\\RepoC)
          │                │                │
       VS Code          VS Code          VS Code
```

### Complete Separation from Application Repositories
1. **Zero Contamination**: Your application repositories contain only their own project files. No MCP dependencies, no wrapper code, and no server configuration files are introduced into application codebases.
2. **Generic & Reusable**: One standalone MCP server manages multiple independent workspaces (Python, TypeScript, Go, Rust, etc.) without restarting.
3. **Session Isolation**: Each conversation thread is bound to its selected repository, eliminating cross-workspace interference.

---

## 2. Directory Structure

```
C:\\Development\\chatgpt-mcp-server\\
│
├── server/
│   ├── __init__.py
│   ├── main.py                # FastMCP server, SSE / HTTP routes, auth middleware
│   ├── config.py              # Pydantic Settings, environment variables loader
│   ├── security.py            # Path sandboxing, traversal guard, secret shield, command filter
│   └── session.py             # Session isolation manager (session_id -> active workspace)
│
├── tools/
│   ├── __init__.py            # Tool exports
│   ├── workspace.py           # list/select/get/add/remove repository registry tools
│   ├── filesystem.py          # list_files, read_file, write_file, create_directory, delete_file
│   ├── search.py              # search_code with build artifact and binary exclusions
│   ├── terminal.py            # run_command with cwd lock, timeout, and output capping
│   └── git.py                 # git_status, git_diff, git_branch inspection tools
│
├── scripts/
│   └── manage.py              # Background daemon controller, health poller & tunnel monitor
│
├── config/
│   └── repositories.yaml      # External YAML repository registry
│
├── runtime/                   # Ephemeral process states (ignored in git)
│   ├── mcp_server.pid         # Process ID of active MCP server
│   ├── cloudflared.pid        # Process ID of active tunnel
│   ├── tunnel.url             # Cached public HTTPS endpoint
│   ├── mcp_server.log         # Server stdout/stderr
│   ├── cloudflared.log        # Tunnel output & URL detection
│   └── startup.log            # Lifecycle log
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # Isolated mock multi-repo test fixtures
│   ├── test_workspace.py      # Workspace listing, switching, session isolation tests
│   ├── test_security.py       # Traversal, symlink, secret files, UNC, command security tests
│   ├── test_filesystem.py     # Relative CRUD filesystem tests
│   ├── test_search.py         # Substring search and ignore filter tests
│   ├── test_terminal.py       # Sandboxed terminal execution, timeout tests
│   ├── test_launcher.py       # Daemon controller, PID tracking & health check tests
│   └── test_git.py            # Git status, diff, branch verification tests
│
├── start_mcp.bat              # One-click Windows startup script
├── stop_mcp.bat               # One-click safe process termination script
├── restart_mcp.bat            # One-click clean restart script
├── status_mcp.bat             # One-click status viewer script
├── test_mcp_connection.bat    # Diagnostics and endpoint verification script
├── .env.example               # Configuration template
├── .gitignore
├── requirements.txt           # Production dependencies
├── README.md                  # Complete operational manual
└── run_server.py              # Direct server entry point
```

---

## 3. One-Click Windows Control Center

The entire server environment can be operated by double-clicking the root batch scripts:

| Script | Action | Description |
| :--- | :--- | :--- |
| **`start_mcp.bat`** | **Start** | Validates venv, starts MCP server in background, verifies health on `http://127.0.0.1:8000/health`, launches HTTPS tunnel, captures public URL, and prints dashboard. |
| **`stop_mcp.bat`** | **Stop** | Safely terminates *only* the tracked MCP server and tunnel PIDs without touching other Python instances. |
| **`restart_mcp.bat`**| **Restart**| Performs a clean shutdown and starts fresh instances with new health checks. |
| **`status_mcp.bat`** | **Status** | Shows active PIDs, local port status, health status, and active public HTTPS URL. |
| **`test_mcp_connection.bat`**| **Test** | Runs connectivity diagnostics and verifies endpoints. |

---

## 4. Configuration & Repository Registry

### Environment Variables (`.env`)
```ini
MCP_HOST=127.0.0.1
MCP_PORT=8000

# Optional path to cloudflared executable (leave blank if cloudflared is in PATH)
CLOUDFLARED_PATH=

# Optional Bearer Token for remote access authentication (leave blank for local dev)
AUTH_TOKEN=

# Tunnel operation mode
TUNNEL_MODE=quick

# Operational & Security Limits
MAX_FILE_SIZE_BYTES=2097152
MAX_COMMAND_OUTPUT_BYTES=102400
COMMAND_TIMEOUT_SECONDS=120
```

### External Repository Registry (`config/repositories.yaml`)
Register all your local projects here:
```yaml
repositories:
  interview-copilot:
    path: 'C:/Users/Jashuva/Desktop/interview-copilot'
    description: 'Real-time AI voice copilot workspace'

  AI_jobs_apply:
    path: 'C:/Development/AI_jobs_apply'
    description: 'Job application automation workspace'

  agentic-sdlc:
    path: 'C:/Development/agentic-sdlc'
    description: 'Multi-agent autonomous SDLC workspace'
```

---

## 5. Security & Isolation Matrix

1. **Path Boundary Enforcement**: Every path is canonicalized and validated using `Path.resolve()`. Any path that escapes the active repository boundary (e.g. `../../`, `C:\\Windows`, UNC paths `\\\\server\\share`) is immediately rejected with a `SecurityError`.
2. **Cross-Repo Isolation**: When `Repo A` is selected, attempts to access `Repo B` are strictly rejected.
3. **Secret Shield**: Access to sensitive files (`.env`, `.env.*`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `credentials.json`, `secrets.json`, `id_rsa*`, etc.) is strictly blocked.
4. **Command Execution Guard**:
   - `cwd` is permanently locked to the active repository root.
   - Destructive commands (`format`, `shutdown`, `diskpart`, `rm -rf`, `del /s`, `rmdir /s`, `git reset --hard`, `git clean -fd`) are blocked.
   - Automatic `git commit` and `git push` are disabled.
   - Enforces execution timeouts and caps output to 100KB.

---

## 6. Connect This MCP Server to ChatGPT Web

### Step 1: Start the MCP Server
Double-click `start_mcp.bat` (or run in terminal):
```powershell
.\\start_mcp.bat
```

### Step 2: Wait for the Startup Dashboard
Wait until the banner displays:
```
======================================================================
           STANDALONE MCP SERVER STATUS DASHBOARD
======================================================================
Project Root:    C:\\Development\\chatgpt-mcp-server
MCP Server:      [RUNNING] (PID: 12345)
Local URL:       http://127.0.0.1:8000
Health Status:   [OK] http://127.0.0.1:8000/health
Tunnel Status:   [RUNNING] (PID: 67890)
Public HTTPS:    https://<subdomain>.trycloudflare.com
MCP Endpoint:    https://<subdomain>.trycloudflare.com/sse
======================================================================
       READY FOR CHATGPT WEB / IDE CONNECTION
======================================================================
```

### Step 3: Copy the Generated HTTPS MCP Endpoint
Copy the **MCP Endpoint** from the output:
`https://<subdomain>.trycloudflare.com/sse` (or `/mcp`)

### Step 4: Register in ChatGPT Web
1. Open **ChatGPT Web** in your browser.
2. Go to **Settings** → **Connected apps** / **Developer Mode Connectors** / **Custom GPT Actions**.
3. Under **MCP Server URL**, enter the copied endpoint:
   `https://<subdomain>.trycloudflare.com/sse`
4. If `AUTH_TOKEN` is configured in your `.env`, select **Authentication: Bearer Token** and paste your token. If left blank, select **None / Anonymous**.
5. Save and enable the connector.

*(Note: Depending on your active ChatGPT plan and UI rollout, custom MCP connectors are configured via Developer Connectors, Connected Apps, or Custom GPT Actions).*

---

## 7. ChatGPT Prompt Validation Sequence

### Test 1: Connectivity & Workspace Discovery
```text
Use the connected MCP server.
Do not modify anything.
1. List all registered repositories.
2. Show repository names.
3. Show repository paths.
4. Do not read application source code.
5. Do not create, delete or modify files.
Confirm that the MCP server is connected.
```

### Test 2: Repository Inspection
```text
Select the AI_jobs_apply repository.
Do not modify anything.
Inspect:
- top-level files
- README
- dependency files
- application entry point
- test structure
- Git branch
- Git status
Explain the architecture.
Do not modify any files.
```

### Test 3: Safe Write & Verification Loop
```text
Select the AI_jobs_apply repository.
Create a temporary file named: mcp_test.py
Put a simple function in it:
def hello_mcp():
    return 'Hello from MCP'
Then:
1. Read the file.
2. Execute it.
3. Verify the output.
4. Show git diff.
5. Delete ONLY the temporary file.
6. Verify it is deleted.
7. Verify no other files changed.
Do not modify production files.
```

---

## 8. Reusable Coding Agent System Prompt

To configure ChatGPT Web as your primary coding agent, use this prompt:

```text
You are my coding agent.
I have multiple local repositories connected through the standalone MCP server.

Before doing any coding:
1. Determine the target repository.
2. If ambiguous, ask me which repository to use.
3. Select the repository using select_repository().
4. Inspect Git status using git_status().
5. Inspect repository structure using list_files().
6. Search relevant code using search_code().
7. Read relevant files using read_file().
8. Understand the architecture.
9. Identify the root cause.
10. Plan the smallest production-safe change.

Then:
11. Modify the actual repository using write_file().
12. Run relevant tests using run_command().
13. Inspect failures and fix them.
14. Rerun tests until they pass.
15. Review changes using git_diff().
16. Report files changed and validation results.

Strict Rules:
- Never assume the repository name.
- Never modify another repository.
- Never access files outside the selected repository.
- Never expose secrets or read .env files.
- Never automatically commit or push.
- Never delete unrelated files.
- Do not merely provide code snippets; actually modify the workspace through MCP.
- Preserve existing code architecture.
```
"""

dest = Path(r"C:\Development\chatgpt-mcp-server\README.md")
with open(dest, "w", encoding="utf-8") as f:
    f.write(readme_content)
print(f"Updated README: {dest}")
