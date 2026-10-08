# MCP Integration with ChatGPT Web

A production-grade, standalone **Model Context Protocol (MCP)** server that connects **ChatGPT Web** (the reasoning/coding agent) to your local repositories on Windows/macOS/Linux, while **VS Code** remains your local IDE.

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
           (MCP-Integration-with-chatgptweb)
                           │
                  Repository Registry
              (config/repositories.json)
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
     Repository A     Repository B     Repository C
  (C:\Dev\RepoA)   (C:\Dev\RepoB)   (C:\Dev\RepoC)
          │                │                │
       VS Code          VS Code          VS Code
```

### Complete Separation of Concerns
1. **Zero Contamination**: Your application repositories contain only their own project files. No MCP dependencies or server configuration files are placed in application codebases.
2. **Generic & Reusable**: One standalone MCP server manages an arbitrary number of unrelated workspaces (Python, TypeScript, Go, Rust, etc.) without restarting.
3. **Session Isolation**: Each conversation thread is bound to its selected repository, eliminating cross-workspace interference.

---

## 2. Quick Start & Setup

### Prerequisites
- **Python 3.10+**
- **Cloudflare Tunnel (`cloudflared`)** for secure remote HTTPS connectivity:
  ```powershell
  winget install Cloudflare.cloudflared
  ```

### Step 1: Clone and Install Dependencies
```powershell
git clone https://github.com/Jashuva-Billa/MCP-Integration-with-chatgptweb.git
cd MCP-Integration-with-chatgptweb

python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: System Diagnostic Check
Run the diagnostic doctor to verify all dependencies and network ports:
```powershell
python scripts/doctor.py
```

### Step 3: Configure Repositories
Edit `config/repositories.json` to register your local projects:
```json
{
  "repositories": {
    "AI_jobs_apply": {
      "path": "C:/Development/AI_jobs_apply",
      "description": "Job application automation workspace",
      "enabled": true
    },
    "agentic-sdlc": {
      "path": "C:/Development/agentic-sdlc",
      "description": "Multi-agent autonomous SDLC workspace",
      "enabled": true
    }
  }
}
```

---

## 3. Starting the Server & Tunnel

### Option A: Start Local Server Directly
```powershell
python scripts/start.py
```
*Health Check:* `http://127.0.0.1:8766/health`  
*MCP Endpoint:* `http://127.0.0.1:8766/sse` (alias: `/mcp`)

### Option B: Start Server with Public HTTPS Tunnel (for ChatGPT Web)
```powershell
python scripts/tunnel.py
```
*Output will capture and display:*
```
======================================================================
       CLOUDFLARE SECURE HTTPS MCP TUNNEL ACTIVE
======================================================================
Public Base URL:  https://<random-id>.trycloudflare.com
MCP Endpoint:     https://<random-id>.trycloudflare.com/sse
Health Check:     https://<random-id>.trycloudflare.com/health
======================================================================
```

---

## 4. Connecting to ChatGPT Web

1. Open **ChatGPT Web** in your browser.
2. Navigate to **Settings** → **Connected apps** / **Developer Mode Connectors** / **Custom GPT Actions**.
3. Under **MCP Server Endpoint**, paste the generated URL:
   ```
   https://<random-id>.trycloudflare.com/sse
   ```
4. **Authentication**:
   - If `MCP_AUTH_ENABLED=true` is set in `.env`, choose **Bearer Token** and enter your `MCP_AUTH_TOKEN`.
   - If authentication is disabled for local testing, choose **Anonymous / None**.
5. Save and enable the connector.

---

## 5. Available MCP Tools

| Category | Tool | Parameters | Description |
| :--- | :--- | :--- | :--- |
| **Workspace** | `list_repositories` | None | Returns list of configured workspaces and their paths. |
| | `select_repository` | `repository_name` | Switches the active workspace for subsequent operations. |
| | `get_current_repository` | None | Returns active repository, resolved path, and Git branch. |
| | `add_repository` | `name`, `path`, `description` | Dynamically registers a new local directory. |
| | `remove_repository` | `name` | Removes repository from registry (never touches physical disk). |
| **Filesystem** | `list_files` | `path="."`, `recursive=False` | Lists workspace files (excluding build dirs & secrets). |
| | `read_file` | `path`, `start_line`, `end_line` | Reads file content safely inside active workspace. |
| | `write_file` | `path`, `content`, `overwrite=True` | Writes or updates actual file on disk for VS Code. |
| | `create_directory` | `path` | Creates folder structure in active workspace. |
| | `delete_file` | `path` | Deletes a specific file inside active workspace. |
| **Search** | `search_code` | `query`, `path="."`, `case_sensitive`, `file_extension` | Fast multi-file search with surrounding context lines. |
| **Code Intel** | `find_symbol` | `name`, `path="."` | Finds definitions of functions, classes, and types. |
| | `find_references` | `symbol`, `path="."` | Finds all usages and references of an identifier. |
| | `list_functions` | `file_path` | Extracts all functions, methods, signatures, and line numbers. |
| | `list_classes` | `file_path` | Extracts all classes, inheritance hierarchies, and methods. |
| | `get_file_structure` | `file_path` | Returns imports, classes, and top-level function outline. |
| **Analysis** | `analyze_repository`| None | Detects languages, frameworks, entry points, test runners, and Git state. |
| **Terminal** | `run_command` | `command`, `timeout=120` | Executes dev commands (`pytest`, `npm test`, `ruff`) with `cwd` locked to workspace. |
| **Git** | `git_status` | None | Inspects modified/staged/untracked working tree state. |
| | `git_diff` | `file_path=None` | Inspects uncommitted diffs made during coding. |
| | `git_branch` | None | Lists active and available Git branches. |
| | `git_log` | `max_commits=10` | Shows recent commit history. |
| | `git_show` | `commit_hash="HEAD"` | Inspects specific commit details and stats. |
| | `git_changed_files` | None | Lists all modified, added, or deleted files. |

---

## 6. Running Automated Tests

Run the full suite of unit, integration, security, and end-to-end tests:
```powershell
python -m pytest -v
```

Run the live connection diagnostic test:
```powershell
python scripts/test_connection.py
```

---

## 7. Security Model & Sandbox

1. **Path Boundary Enforcement**: Every path is canonicalized and validated using `Path.resolve()`. Any path that escapes the active repository boundary (`../../`, `C:\Windows`, UNC network paths) is rejected with a `SecurityError`.
2. **Secret Shield**: Access to sensitive files (`.env`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `credentials.json`, `secrets.json`, `id_rsa*`) is blocked.
3. **Command Execution Guard**:
   - `cwd` is permanently locked to the active repository root.
   - Destructive commands (`format`, `shutdown`, `diskpart`, `rm -rf`, `del /s`, `git reset --hard`, `git clean -fd`) are blocked.
   - Automatic `git commit` and `git push` are disabled.
   - Enforces execution timeouts and caps output to 100KB.

---

## 8. Example ChatGPT Prompts

### Example 1: Discover and Inspect
```text
List my repositories and inspect AI_jobs_apply.
Explain the architecture and identify the main entry points without modifying any files.
```

### Example 2: Code Search and Symbol Investigation
```text
Select the AI_jobs_apply repository.
Find where recruiter_email is resolved and explain the flow.
```

### Example 3: Test-Driven Bug Fix & Verification
```text
Fix the recruiter_email parsing issue in AI_jobs_apply.
Run the relevant pytest test suite, inspect failures, apply the fix, rerun the tests, and show me the git diff.
Do not modify unrelated files.
```
