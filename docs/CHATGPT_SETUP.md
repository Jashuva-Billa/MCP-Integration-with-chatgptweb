# Connecting ChatGPT Web to Local MCP Server

This guide explains how to connect **ChatGPT Web** to your local standalone MCP server via a secure HTTPS tunnel.

---

## 1. Prerequisites

1. **Python 3.10+** installed.
2. **Cloudflare Tunnel (`cloudflared`)** installed:
   ```powershell
   winget install Cloudflare.cloudflared
   ```
   *(Or download `cloudflared.exe` from official Cloudflare releases).*

---

## 2. Startup Sequence

### Step 1: Start the Local MCP Server & Tunnel
Run the diagnostic and startup script:
```powershell
python scripts/doctor.py
python scripts/tunnel.py
```
*Output will display:*
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

## 3. Registering in ChatGPT Web

1. Open **ChatGPT Web** (browser).
2. Navigate to **Settings** → **Connected apps** / **Developer Mode Connectors** / **Custom GPT Actions**.
3. Under **MCP Server Endpoint**, paste the generated URL:
   ```
   https://<random-id>.trycloudflare.com/sse
   ```
4. **Authentication**:
   - If `MCP_AUTH_ENABLED=true` is set in `.env`, choose **Bearer Token** and enter your `MCP_AUTH_TOKEN`.
   - If authentication is disabled for local testing, choose **Anonymous / None**.
5. Click **Save** and enable the connector.

---

## 4. Reusable Coding Agent System Prompt

Use this prompt in ChatGPT to establish its role as your primary coding agent:

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
8. Understand the architecture using analyze_repository().
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
