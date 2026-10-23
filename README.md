# MCP Integration with ChatGPT Web

A production-grade, standalone **Model Context Protocol (MCP)** server that connects **ChatGPT Web** (the reasoning/coding agent) to your local repositories on Windows/macOS/Linux, while **VS Code** remains your local IDE.

> **Automatic skills and superpowers:** At the start of every coding task, call `prepare_task_workflow` to choose relevant skills and capabilities, read each selected skill with `get_skill`, then inspect → edit → test/repair → verify. See [Agent Operating Protocol](docs/AGENT_OPERATING_PROTOCOL.md). The user should not need to specify skills or tools manually.

> **Automatic skills and superpowers:** At the start of every coding task, call `prepare_task_workflow` to choose relevant skills and capabilities, read each selected skill with `get_skill`, then inspect → edit → test/repair → verify. See [Agent Operating Protocol](docs/AGENT_OPERATING_PROTOCOL.md). The user should not need to specify skills or tools manually.

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
  (C:\\Dev\\RepoA)   (C:\\Dev\\RepoB)   (C:\\Dev\\RepoC)
          │                │                │
       VS Code          VS Code          VS Code
```

### Complete Separation of Concerns
1. **Zero Contamination**: Your application repositories contain only their own project files. No MCP dependencies or server configuration files are placed in application codebases.
2. **Generic & Reusable**: One standalone MCP server manages an arbitrary number of unrelated workspaces (Python, TypeScript, Go, Rust, etc.) without restarting.
3. **Session Isolation**: Session bookkeeping exists, but per-client isolation must be verified end-to-end before relying on concurrent repository selection.

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
.\\venv\\Scripts\\activate
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

## 3. Starting the Server & Tunnel

### Option A: One-Click Quick Start (Windows)
Double-click `start.bat` in the root directory. This will:
- Auto-detect your virtual environment (`venv`).
- Start the standalone MCP server.
- Start the configured HTTPS tunnel and print your public ChatGPT connector URL.

Companion scripts:
- `status_all.bat`: Checks health status and displays current endpoints.
- `stop_all.bat`: Safely terminates the MCP server and tunnel.

### Option B: Start Local Server Directly via CLI
```powershell
python scripts/start.py
```
*Health Check:* `http://127.0.0.1:8766/health`  
*Streamable HTTP Transport:* `http://127.0.0.1:8766/mcp`  
*SSE Transport:* `http://127.0.0.1:8766/sse`  

### Option C: Start Server with Public HTTPS Tunnel via CLI (for ChatGPT Web)
```powershell
python scripts/tunnel.py
```
*Output will capture and display:*
```
======================================================================
       CLOUDFLARE SECURE HTTPS MCP TUNNEL ACTIVE
======================================================================
Public Base URL:  https://<random-id>.trycloudflare.com
Streamable HTTP:  https://<random-id>.trycloudflare.com/mcp
SSE Endpoint:     https://<random-id>.trycloudflare.com/sse
Health Check:     https://<random-id>.trycloudflare.com/health
======================================================================
```

---

## 4. Connecting to ChatGPT Web

1. Open **ChatGPT Web** in your browser.
2. Navigate to **Settings** → **Connected apps** / **Developer Mode Connectors** / **Custom GPT Actions**.
3. Under **MCP Server Endpoint**, paste the generated URL:
   - For **Streamable HTTP** (recommended): `https://<random-id>.trycloudflare.com/mcp`
   - For **SSE Transport**: `https://<random-id>.trycloudflare.com/sse`
4. **Authentication**:
   - Before using a public tunnel, set `MCP_AUTH_ENABLED=true` and `MCP_AUTH_TOKEN` (at least 32 random characters) in your private `.env` file. Generate a token with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
   - Choose **Bearer Token** and enter that token in the connector's authentication settings.
   - For local-only development, authentication can remain disabled when no tunnel is exposed.
5. Save and enable the connector. HTTPS protects transport but does not make an unauthenticated local-filesystem API private. The tunnel launcher now refuses public exposure if authentication is not configured.

---

## 5. Connecting with VS Code

You can integrate VS Code in two complementary ways:

### A. Live Code Sync (Observe ChatGPT changes in real-time)
Open the pre-configured Multi-Root Workspace in VS Code:
```powershell
code multi-repo.code-workspace
```
Or use **Option [2]** in `start.bat`. This mounts:
- `MCP Server` (the bridge engine)
- `interview-copilot`
- `AI_jobs_apply`

Whenever ChatGPT Web executes `write_file()` or runs a command through the MCP server, the files change immediately on disk and appear hot-reloaded in VS Code.

### B. Direct VS Code MCP Client Connection
If you use VS Code extensions that support MCP (such as GitHub Copilot MCP preview, Cline, Roo Code, or Continue):
- The project includes `.vscode/mcp.json` automatically configured to connect to your local MCP server:
  - Streamable HTTP: `http://127.0.0.1:8766/mcp`
  - SSE Transport: `http://127.0.0.1:8766/sse`

---

## 6. Available MCP Tools (61 Tools Across 15 Categories)

The server exposes 61 specialized MCP tools across 15 capability categories:

| Category | Tools | Description |
| :--- | :--- | :--- |
| **Workspace Management** | `list_repositories`, `select_repository`, `get_current_repository`, `add_repository`, `remove_repository` | Manage multi-repo workspaces dynamically without restarting the server. |
| **Filesystem (Read)** | `list_files`, `read_file` | Read files safely with line slicing and secret protection. |
| **Filesystem (Write)** | `write_file`, `create_directory` | Create or update files and directories within repo boundaries. |
| **Filesystem (Destructive)** | `delete_file`, `delete_directory`, `move_file`, `copy_file` | Policy-gated directory deletion (with dry-run preview), file moves, and copies. |
| **Filesystem (Safety)** | `backup_file`, `restore_file`, `diff_preview` | Checkpoint and restore files before and after editing, preview unified diffs. |
| **Editing** | `replace_in_file` | Atomic, exact-match text replacement with occurrence verification. |
| **Search & Intelligence** | `search_code`, `find_symbol`, `find_references`, `list_functions`, `list_classes`, `get_file_structure` | AST-based symbol definition, reference tracking, and code structural analysis. |
| **Command Execution** | `run_command`, `run_tests`, `install_dependencies` | Policy-gated execution of approved developer commands, test runners, and package managers with process-tree cleanup and automated failure diagnostics. |
| **Git (Read)** | `git_status`, `git_diff`, `git_branch`, `git_log`, `git_show`, `git_changed_files` | Full repository history and working tree inspection. |
| **Git (Write & Remote)** | `git_stage`, `git_commit`, `git_create_branch`, `git_switch_branch`, `git_reset`, `git_worktree_add`, `git_worktree_remove`, `git_push`, `git_fetch`, `git_pull` | Staging, atomic commits, branch management, worktrees, and network-gated fetch/pull/push operations. |
| **Repository Analysis** | `analyze_repository`, `inspect_workspace` | Auto-detect frameworks, test runners, entry points, and workspace summaries. |
| **Permissions & Profiles** | `get_permission_profile`, `set_permission_profile` | Runtime inspection and switching of security permission profiles. |
| **Execution Profile** | `get_execution_profile`, `configure_execution_profile` | Persistent autonomy, automatic skills, bounded repair loops, parallel workstream planning, Git delivery policy, and checkpoint policy. |
| **Skills System** | `prepare_task_workflow`, `list_skills`, `get_skill`, `reload_skills` | Automatically routes tasks to relevant skills and superpowers; skill instructions are read before execution. |
| **Lifecycle Hooks** | `list_hooks`, `fire_hook` | User-defined pre/post commands for file edits, tests, and commits (`.mcp/hooks.json`). |
| **Autonomous Workflow & State** | `create_task`, `get_task`, `list_tasks`, `update_task_step`, `complete_task`, `add_task_issue`, `record_test_result`, `plan_repair_attempt`, `verify_task` | Multi-step planning, automated hypothesis-driven test-repair loops, and structured goal verification. |

---

## 7. Permission Profiles & Security Model

The server implements a centralized 4-tier capability gating engine controlled by `MCP_PERMISSION_PROFILE` in `.env`:

| Capability | `safe` (Default) | `full` (Autonomous Dev) | `trusted_admin` (Full CI/CD Admin) | `unrestricted` (Local Opt-in Only) |
| :--- | :---: | :---: | :---: | :---: |
| Read / Search Files | ✅ | ✅ | ✅ | ✅ |
| Write Files & Dirs | ✅ | ✅ | ✅ | ✅ |
| Delete Files / Dirs | ❌ | ✅ | ✅ | ✅ |
| Move / Copy Files | ❌ | ✅ | ✅ | ✅ |
| Run Test Commands | ✅ (pytest/npm/cargo/etc.) | ✅ (All dev binaries) | ✅ (Arbitrary commands) | ✅ (Arbitrary commands) |
| Install Dependencies | ❌ | ✅ (pip/npm/poetry/cargo) | ✅ | ✅ |
| Git Commits & Branches | ❌ (Read only) | ✅ | ✅ | ✅ |
| Remote Git (Fetch / Pull) | ❌ | ❌ | ✅ | ✅ |
| Remote Git (Push) | ❌ | ❌ | ✅ | ✅ |
| Network Access Authorization | ❌ | ❌ | ✅ | ✅ |
| Destructive Git Hard Reset | ❌ | ❌ | ❌ | ✅ |
| Path Traversal Beyond Workspace | ❌ | ❌ | ❌ | ✅ |
| Command Timeout | 120 seconds | 300 seconds | 600 seconds | 600 seconds |
| Output Secret Redaction | ✅ | ✅ | ✅ | ✅ |
| Process Tree Cleanup on Timeout | ✅ | ✅ | ✅ | ✅ |

### Robust Command Handling & Diagnostics
- **Process Tree Cleanup**: Commands that exceed timeout are killed along with their entire process subtree (`taskkill /PID <pid> /T /F` on Windows) to prevent orphan child processes holding port or file locks.
- **Automated Failure Diagnostics**: Non-zero exits and timeouts are automatically analyzed, classified, and paired with actionable fix recommendations:
  - `TIMEOUT`: Suggests command optimization or profile timeout increase.
  - `MISSING_DEPENDENCY`: Identifies missing packages or modules (e.g. `ModuleNotFoundError`).
  - `SYNTAX_ERROR`: Pinpoints syntax errors and file locations.
  - `TEST_FAILURE`: Identifies failed assertion count and test file.
  - `PERMISSION_DENIED`: Detects file lock or OS privilege issues.
  - `PORT_IN_USE`: Identifies port conflicts.
  - `GIT_CONFLICT`: Detects merge conflicts and file conflict markers.
- **Output Truncation Metrics**: Commands that produce massive logs report exact `output_bytes`, `stdout_truncated` (bool), and `stderr_truncated` (bool).

### Switching Profiles
- In `.env`: `MCP_PERMISSION_PROFILE=trusted_admin`
- Or via tool at runtime: `set_permission_profile(profile="trusted_admin")`

---

## 8. Skills & Extensibility

Skills are specialized workflow instructions located in the `skills/` directory. Built-in skills include:
- `python-development`: Best practices for virtualenvs, type hints, pytest, and ruff.
- `git-workflow`: Feature branch creation, commit conventions, worktree safety, and remote tracking.
- `debugging-guide`: Systematic hypothesis-driven debugging and error reproduction.
- `security-review`: Secret leakage scanning, OWASP top 10 checks, and path validation.
- `test-driven-development`: Red-Green-Refactor loop and regression coverage.

Agents can discover available skills with `list_skills()` and read full instructions with `get_skill(name="python-development")`.

---

## 9. Lifecycle Hooks (`.mcp/hooks.json`)

Configure automated commands triggered during agent execution:
- `before_file_edit` / `after_file_edit`: Run auto-formatters (e.g. `black {file}`).
- `before_test_run` / `after_test_run`: Setup fixtures or cleanup test artifacts.
- `before_git_commit`: Run linters (`flake8`, `eslint`) before committing.
- `after_task_complete`: Run notification scripts or generate change summaries.

---

## 10. Running Automated Tests

Run the full test suite (79 tests covering unit, integration, security, command diagnostics, git remote, and E2E):
```powershell
python -m pytest -v
```

Run specific test suites:
```powershell
python -m pytest tests/unit/test_permissions.py -v
python -m pytest tests/unit/test_command_diagnostics.py -v
python -m pytest tests/unit/test_git_remote.py -v
python -m pytest tests/unit/test_agent_workflow.py -v
python -m pytest tests/integration/test_server_integration.py -v
```

---

## 11. Example Prompts for ChatGPT / Claude

### Autonomous Task Execution Loop
```text
Select the AI_jobs_apply repository.
Create an autonomous task to add token refresh support to the OAuth flow.
Plan the implementation steps, inspect the existing auth module, write unit tests,
implement the refresh logic, run the test suite, and record the final verification.
```

### Safe Refactoring with Diff Preview
```text
Select the interview-copilot repository.
Check the git status. Create a backup of src/main.py, preview the diff for removing deprecated arguments,
apply the replacement using replace_in_file, run the test suite, and show the git diff.
```



## Autonomous Coding with ChatGPT Web (No API Key)

This setup uses the ChatGPT Web model that is already connected to the MCP server. The server executes tools and persists task state; ChatGPT Web plans the work, interprets results, and decides the next action. No separate LLM API key is needed.

Key tools:
- `run_autonomous_task` / `start_chatgpt_coding_task`: start or resume a persistent ChatGPT-driven task.
- `record_chatgpt_task_progress`: record plan progress, test outcomes, and repair notes.
- `finish_chatgpt_coding_task`: run final verification before marking the task complete.
- `rollback_task_checkpoint` and `rollback_git_reset_checkpoint`: recover changes.
- `record_chatgpt_benchmark_result` and `get_benchmark_report`: compare ChatGPT Web and Claude Code on the same cases without an API.

See `docs/AUTONOMOUS_ORCHESTRATION.md` for the execution loop, checkpoint behavior, and benchmark workflow.

Important: the MCP server cannot spawn independent ChatGPT Web model sessions. Reviews can be performed as separate passes in the current ChatGPT conversation, while filesystem changes remain checkpointed and permission-controlled. The API-backed benchmark runner is optional and is not needed for this workflow. Git commits and pushes are not performed unless explicitly requested.
