import os
from pathlib import Path

readme_content = """# Standalone Reusable Multi-Repository MCP Server

An infrastructure-level Model Context Protocol (MCP) server designed to connect **ChatGPT Web** (the reasoning/coding agent) to **local codebases** on Windows, while **VS Code** remains purely an IDE for inspecting and working with files.

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

### Why MCP is Completely Separate from Application Repositories
1. **Zero Contamination**: Your application repositories contain only their own project files. No MCP dependencies, no wrapper code, and no server configuration files are introduced into application codebases.
2. **Generic & Reusable**: One MCP server instance manages an arbitrary number of unrelated workspaces (Python, Node.js, Rust, Go, etc.) simultaneously.
3. **Continuous Operation**: Switching projects does not require stopping, restarting, or reconfiguring the MCP server.

---

## 2. Directory Structure

```
C:\\Development\\chatgpt-mcp-server\\
│
├── server/
│   ├── __init__.py
│   ├── main.py                # FastMCP server, SSE / HTTP routes, auth middleware
│   ├── config.py              # Pydantic settings, environment variables loader
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
├── config/
│   └── repositories.yaml      # External YAML repository registry
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # Isolated mock multi-repo test fixtures
│   ├── test_workspace.py      # Workspace listing, switching, session isolation tests
│   ├── test_security.py       # Traversal, symlink, secret files, UNC, command security tests
│   ├── test_filesystem.py     # Relative CRUD filesystem tests
│   ├── test_search.py         # Substring search and ignore filter tests
│   ├── test_terminal.py       # Sandboxed terminal execution, timeout tests
│   └── test_git.py            # Git status, diff, branch verification tests
│
├── .env.example               # Configuration template
├── .gitignore
├── requirements.txt           # Production dependencies
├── README.md                  # Operational documentation
└── run_server.py              # Server entry point
```

---

## 3. Installation & Windows Setup

### Step 1: Clone or Navigate to Standalone Directory
```powershell
cd C:\\Development\\chatgpt-mcp-server
```

### Step 2: Initialize Virtual Environment
```powershell
python -m venv venv
.\\venv\\Scripts\\activate
```

### Step 3: Install Dependencies
```powershell
pip install -r requirements.txt
```

---

## 4. Configuration & Repository Registry

### Environment Variables (`.env`)
Copy `.env.example` to `.env`:
```powershell
copy .env.example .env
```

| Variable | Default | Description |
| :--- | :--- | :--- |
| `MCP_HOST` | `127.0.0.1` | Local IP address for the MCP server |
| `MCP_PORT` | `8000` | Local port for HTTP & SSE endpoints |
| `AUTH_TOKEN` | `""` | Optional Bearer token for remote access authentication |
| `COMMAND_TIMEOUT_SECONDS`| `120` | Max duration for shell command execution |
| `MAX_FILE_SIZE_BYTES` | `2097152` | Max file read/write size (2MB) |
| `MAX_COMMAND_OUTPUT_BYTES`| `102400` | Max stdout/stderr size (100KB) |

### Repository Registry (`config/repositories.yaml`)
Configure your local repositories using forward slashes or escaped backslashes:
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

## 5. Security Model & Isolation

1. **Path Boundary Enforcement**: Every path is canonicalized and validated using `Path.resolve()`. Any path that escapes the active repository boundary (e.g. `../../`, `C:\\Windows`, UNC paths `\\\\server\\share`) is immediately rejected with a `SecurityError`.
2. **Cross-Repo Isolation**: When `Repo A` is selected, attempts to reference `Repo B` are blocked.
3. **Secret Shield**: Access to sensitive files (`.env`, `.env.*`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `credentials.json`, `secrets.json`, `id_rsa*`, etc.) is strictly blocked.
4. **Command Execution Guard**:
   - `cwd` is permanently locked to the active repository root.
   - Destructive commands (`format`, `shutdown`, `diskpart`, `rm -rf`, `del /s`, `rmdir /s`, `git reset --hard`, `git clean -fd`) are blocked.
   - Automatic `git commit` and `git push` are disabled.
   - Enforces execution timeouts and caps output to 100KB.

---

## 6. Available MCP Tools

| Category | Tool | Parameters | Description |
| :--- | :--- | :--- | :--- |
| **Workspace** | `list_repositories` | None | Returns list of configured workspaces and their paths. |
| | `select_repository` | `repository_name` | Switches the active workspace for subsequent operations. |
| | `get_current_repository` | None | Returns active repository, resolved path, and Git branch. |
| | `add_repository` | `name`, `path`, `description` | Dynamically adds a new repository to `repositories.yaml`. |
| | `remove_repository` | `name` | Removes repository from registry (never deletes physical directory). |
| **Filesystem** | `list_files` | `path="."`, `recursive=False` | Lists workspace files (excluding build dirs & secrets). |
| | `read_file` | `path`, `start_line`, `end_line` | Reads file content safely inside active workspace. |
| | `write_file` | `path`, `content`, `overwrite=True` | Writes or updates actual file on disk for VS Code. |
| | `create_directory` | `path` | Creates folder structure in active workspace. |
| | `delete_file` | `path` | Deletes a specific file inside active workspace. |
| **Search** | `search_code` | `query`, `path="."` | Searches text/regex across source files (skips binary & `.git`). |
| **Terminal** | `run_command` | `command`, `timeout=120` | Executes dev commands (`pytest`, `npm test`, `python`) with `cwd` locked. |
| **Git** | `git_status` | None | Inspects working tree modifications and untracked files. |
| | `git_diff` | `file_path=None` | Shows uncommitted diffs to review modifications. |
| | `git_branch` | None | Lists local and remote branches. |

---

## 7. Running the Server & Local Testing

### Start the Server
```powershell
.\\venv\\Scripts\\python run_server.py
```
*Output:*
```
======================================================================
Standalone Multi-Repository MCP Server Initializing
Host: 127.0.0.1:8000
Streamable HTTP & SSE Endpoint: http://127.0.0.1:8000/sse
Authentication: DISABLED (Local Dev Mode)
======================================================================
```

### Running Automated Test Suite
```powershell
.\\venv\\Scripts\\pytest -v
```

---

## 8. Exposing to ChatGPT Web (Remote HTTPS Connection)

Because ChatGPT Web runs in the cloud, it cannot connect to `http://localhost:8000` directly. It requires a secure public HTTPS endpoint with optional Bearer Token authentication.

### Option A: Cloudflare Tunnel (Recommended - Free & Fast)
1. Install Cloudflare Tunnel CLI (`cloudflared`).
2. Run tunnel pointing to local MCP server:
   ```powershell
   cloudflared tunnel --url http://127.0.0.1:8000
   ```
3. Copy the generated HTTPS URL:
   `https://<random-subdomain>.trycloudflare.com`

### Option B: ngrok
1. Run ngrok:
   ```powershell
   ngrok http 8000
   ```
2. Copy the generated HTTPS URL:
   `https://<subdomain>.ngrok-free.app`

### ChatGPT Web Connector Registration
1. In ChatGPT Web, navigate to **Settings** → **Connected apps** (or **Custom GPT Actions / MCP Connectors**).
2. Enter the MCP Endpoint URL:
   `https://<your-tunnel-domain>/sse` (or `https://<your-tunnel-domain>/mcp`)
3. Select **Authentication**: `Bearer Token` (or `API Key`).
4. Enter the token configured in your `.env` file (`AUTH_TOKEN`).

---

## 9. ChatGPT Prompt Validation Sequence

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

## 10. Reusable Coding Agent System Prompt

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
print(f"Created: {dest}")
