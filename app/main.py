import sys
import json
import ipaddress
from pathlib import Path

# Ensure project root is in sys.path for direct script execution
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ruff: noqa: E402  # sys.path bootstrap intentionally precedes application imports
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

try:
    from mcp.server import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer

from app.config import settings
from app.logging_config import setup_logging
from app.auth.auth import BearerAuthMiddleware
from app.core.session import session_manager
from app.core.repository import repository_manager
from app.core.permissions import policy_engine

# --- Tools ---
from app.tools import (
    workspace,
    filesystem,
    editing,
    search,
    code_intelligence,
    terminal,
    git,
    git_provider,
    github_auth,
    repository_analysis,
    quick_inspect,
    agent,
)

logger = setup_logging(settings.MCP_LOG_LEVEL)

# MCP Server Instance
mcp = MCPServer("Multi-Repo-Code-Agent-MCP")

# ════════════════════════════════════════════════════════════
# 1. Workspace Management
# ════════════════════════════════════════════════════════════
mcp.tool()(workspace.list_repositories)
mcp.tool()(workspace.select_repository)
mcp.tool()(workspace.get_current_repository)
mcp.tool()(workspace.add_repository)
mcp.tool()(workspace.clone_github_repository)
mcp.tool()(workspace.remove_repository)

# ════════════════════════════════════════════════════════════
# 2. Filesystem — Read
# ════════════════════════════════════════════════════════════
mcp.tool()(filesystem.list_files)
mcp.tool()(filesystem.read_file)

# ════════════════════════════════════════════════════════════
# 3. Filesystem — Write / Modify
# ════════════════════════════════════════════════════════════
mcp.tool()(filesystem.write_file)
mcp.tool()(filesystem.create_directory)

# ════════════════════════════════════════════════════════════
# 4. Filesystem — Delete / Move / Copy (policy-gated)
# ════════════════════════════════════════════════════════════
mcp.tool()(filesystem.delete_file)
mcp.tool()(filesystem.delete_directory)       # NEW: recursive delete with dry-run
mcp.tool()(filesystem.move_file)              # NEW
mcp.tool()(filesystem.copy_file)              # NEW

# ════════════════════════════════════════════════════════════
# 5. Filesystem — Backup / Restore / Diff Preview
# ════════════════════════════════════════════════════════════
mcp.tool()(filesystem.backup_file)            # NEW
mcp.tool()(filesystem.restore_file)           # NEW
mcp.tool()(filesystem.diff_preview)           # NEW

# ════════════════════════════════════════════════════════════
# 6. Editing — Precise patching
# ════════════════════════════════════════════════════════════
mcp.tool()(editing.replace_in_file)

# ════════════════════════════════════════════════════════════
# 7. Search and Code Intelligence
# ════════════════════════════════════════════════════════════
mcp.tool()(search.search_code)
mcp.tool()(code_intelligence.find_symbol)
mcp.tool()(code_intelligence.find_references)
mcp.tool()(code_intelligence.list_functions)
mcp.tool()(code_intelligence.list_classes)
mcp.tool()(code_intelligence.get_file_structure)

# ════════════════════════════════════════════════════════════
# 8. Command Execution (policy-gated)
# ════════════════════════════════════════════════════════════
mcp.tool()(terminal.run_command)
mcp.tool()(terminal.run_tests)                # NEW: convenience wrapper
mcp.tool()(terminal.install_dependencies)     # NEW: dependency installation

# ════════════════════════════════════════════════════════════
# 9. Git — Read
# ════════════════════════════════════════════════════════════
mcp.tool()(git.git_status)
mcp.tool()(git.git_diff)
mcp.tool()(git.git_branch)
mcp.tool()(git.git_log)
mcp.tool()(git.git_show)
mcp.tool()(git.git_changed_files)

# ════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════
# 10. Git — Write & Remote (policy-gated)
# ════════════════════════════════════════════════════════════
mcp.tool()(git.git_stage)                     # NEW
mcp.tool()(git.git_commit)                    # NEW
mcp.tool()(git.git_create_branch)             # NEW
mcp.tool()(git.git_switch_branch)             # NEW
mcp.tool()(git.git_reset)                     # NEW
mcp.tool()(git.git_worktree_add)              # NEW
mcp.tool()(git.git_worktree_remove)           # NEW
mcp.tool()(git.git_push)                      # NEW: remote push
mcp.tool()(git.git_fetch)                     # remote fetch
mcp.tool()(git.git_pull)                      # remote pull
mcp.tool()(git.rollback_git_reset_checkpoint) # Restore hard-reset safety checkpoint

# ════════════════════════════════════════════════════════════
# 10b. GitHub onboarding (per-user local OAuth device flow)
# ════════════════════════════════════════════════════════════
mcp.tool()(github_auth.github_connect_start)
mcp.tool()(github_auth.github_connect_complete)
mcp.tool()(github_auth.github_connection_status)
mcp.tool()(github_auth.github_list_available_repositories)
mcp.tool()(github_auth.github_select_repositories)
mcp.tool()(github_auth.github_disconnect)

# ════════════════════════════════════════════════════════════
# 10c. Remote Git hosting / CI/CD intelligence (read-only)
# ════════════════════════════════════════════════════════════
mcp.tool()(git_provider.github_repo_overview)
mcp.tool()(git_provider.github_commit_history)
mcp.tool()(git_provider.github_pull_requests)
mcp.tool()(git_provider.github_workflow_runs)
mcp.tool()(git_provider.github_workflow_jobs)
mcp.tool()(git_provider.github_deployments)

# ════════════════════════════════════════════════════════════
# 11. Repository Analysis
# ════════════════════════════════════════════════════════════
mcp.tool()(repository_analysis.analyze_repository)
mcp.tool()(quick_inspect.inspect_workspace)

# ════════════════════════════════════════════════════════════
# 12. Permissions and Profiles
# ════════════════════════════════════════════════════════════
mcp.tool()(agent.get_permission_profile)      # NEW
mcp.tool()(agent.set_permission_profile)      # NEW
mcp.tool()(agent.get_execution_profile)       # AUTONOMY configuration
mcp.tool()(agent.configure_execution_profile) # AUTONOMY configuration
mcp.tool()(agent.prepare_task_workflow)       # AUTO skill/superpower routing

# ════════════════════════════════════════════════════════════
# 13. Skills System
# ════════════════════════════════════════════════════════════
mcp.tool()(agent.list_skills)                 # NEW
mcp.tool()(agent.get_skill)                   # NEW
mcp.tool()(agent.reload_skills)               # NEW

# ════════════════════════════════════════════════════════════
# 14. Lifecycle Hooks
# ════════════════════════════════════════════════════════════
mcp.tool()(agent.list_hooks)                  # NEW
mcp.tool()(agent.fire_hook)                   # NEW

# ════════════════════════════════════════════════════════════
# 15. Autonomous Task State and Memory
# ════════════════════════════════════════════════════════════
mcp.tool()(agent.create_task)                 # NEW
mcp.tool()(agent.get_task)                    # NEW
mcp.tool()(agent.list_tasks)                  # NEW
mcp.tool()(agent.update_task_step)            # NEW
mcp.tool()(agent.complete_task)               # NEW
mcp.tool()(agent.add_task_issue)              # NEW
mcp.tool()(agent.record_test_result)          # NEW
mcp.tool()(agent.plan_repair_attempt)         # NEW: structured repair loop
mcp.tool()(agent.verify_task)                 # NEW: automated verification
mcp.tool()(agent.run_autonomous_task)           # Persistent model-driven orchestration
mcp.tool()(agent.rollback_task_checkpoint)      # Deterministic checkpoint recovery
mcp.tool()(agent.run_coding_benchmark)           # Repeatable coding benchmark
mcp.tool()(agent.get_benchmark_report)           # Benchmark metrics and comparison report
mcp.tool()(agent.start_chatgpt_coding_task)      # ChatGPT Web-native task start
mcp.tool()(agent.record_chatgpt_task_progress)   # Persist model-driven task progress
mcp.tool()(agent.finish_chatgpt_coding_task)     # Verified ChatGPT Web task completion
mcp.tool()(agent.record_chatgpt_benchmark_result) # API-free ChatGPT Web/Claude Code benchmark capture
mcp.tool()(agent.request_approval)
mcp.tool()(agent.resolve_approval)
mcp.tool()(agent.list_approvals)
mcp.tool()(agent.create_parallel_workstream)
mcp.tool()(agent.list_parallel_workstreams)
mcp.tool()(agent.validate_parallel_workstream)
mcp.tool()(agent.merge_parallel_workstream)
mcp.tool()(agent.remove_parallel_workstream)
mcp.tool()(agent.start_coding_workers)
mcp.tool()(agent.get_coding_worker_job)
mcp.tool()(agent.list_coding_worker_jobs)
mcp.tool()(agent.cancel_coding_worker_job)
mcp.tool()(agent.run_independent_verification)
mcp.tool()(agent.transition_task_phase)
mcp.tool()(agent.start_worker_benchmark)
mcp.tool()(agent.get_worker_benchmark)
mcp.tool()(agent.list_worker_benchmarks)


# ════════════════════════════════════════════════════════════
# Health Route
# ════════════════════════════════════════════════════════════
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Returns real-time health, transport, active workspace, and permission profile."""
    active_name = session_manager.get_active_repo_name()
    repos = repository_manager.list_repositories()
    return JSONResponse({
        "status": "ok",
        "service": "chatgpt-mcp-server",
        "version": "2.0.0",
        "transports": ["Streamable HTTP (/mcp)", "SSE (/sse)"],
        "active_repository": active_name,
        "configured_repositories_count": len(repos),
        "permission_profile": policy_engine.profile.value,
        "auth_enabled": bool(settings.MCP_AUTH_ENABLED),
        "host": settings.MCP_HOST,
        "port": settings.MCP_PORT,
        "tool_count": 96,
    })


@mcp.custom_route("/tools", methods=["GET"])
async def tool_list(request: Request) -> JSONResponse:
    """Returns a categorized list of all registered MCP tools."""
    return JSONResponse({
        "total_tools": 96,
        "categories": {
            "workspace_management": ["list_repositories", "select_repository", "get_current_repository", "add_repository", "clone_github_repository", "remove_repository"],
            "filesystem_read": ["list_files", "read_file"],
            "filesystem_write": ["write_file", "create_directory"],
            "filesystem_destructive": ["delete_file", "delete_directory", "move_file", "copy_file"],
            "filesystem_safety": ["backup_file", "restore_file", "diff_preview"],
            "editing": ["replace_in_file"],
            "search_and_intelligence": ["search_code", "find_symbol", "find_references", "list_functions", "list_classes", "get_file_structure"],
            "command_execution": ["run_command", "run_tests", "install_dependencies"],
            "git_read": ["git_status", "git_diff", "git_branch", "git_log", "git_show", "git_changed_files"],
            "git_write_and_remote": ["git_stage", "git_commit", "git_create_branch", "git_switch_branch", "git_reset", "git_worktree_add", "git_worktree_remove", "git_push", "git_fetch", "git_pull"],
            "github_onboarding": ["github_connect_start", "github_connect_complete", "github_connection_status", "github_list_available_repositories", "github_select_repositories", "github_disconnect"],
            "github_ci_cd_read": ["github_repo_overview", "github_commit_history", "github_pull_requests", "github_workflow_runs", "github_workflow_jobs", "github_deployments"],
            "repository_analysis": ["analyze_repository", "inspect_workspace"],
            "permissions": ["get_permission_profile", "set_permission_profile"],
            "execution_profile": ["get_execution_profile", "configure_execution_profile"],
            "skills": ["prepare_task_workflow", "list_skills", "get_skill", "reload_skills"],
            "hooks": ["list_hooks", "fire_hook"],
            "task_state": ["create_task", "get_task", "list_tasks", "update_task_step", "complete_task", "add_task_issue", "record_test_result", "plan_repair_attempt", "verify_task", "start_chatgpt_coding_task", "record_chatgpt_task_progress", "finish_chatgpt_coding_task"],
            "autonomous_execution": ["run_autonomous_task", "rollback_task_checkpoint", "run_coding_benchmark", "get_benchmark_report", "record_chatgpt_benchmark_result"],
            "git_recovery": ["rollback_git_reset_checkpoint"],
            "approvals": ["request_approval", "resolve_approval", "list_approvals"],
            "parallel_workstreams": ["create_parallel_workstream", "list_parallel_workstreams", "validate_parallel_workstream", "merge_parallel_workstream", "remove_parallel_workstream"],
            "worker_runtime": ["start_coding_workers", "get_coding_worker_job", "list_coding_worker_jobs", "cancel_coding_worker_job"],
            "independent_verification": ["run_independent_verification", "transition_task_phase"],
            "benchmark_harness": ["start_worker_benchmark", "get_worker_benchmark", "list_worker_benchmarks"],
        }
    })


@mcp.custom_route("/api/tasks", methods=["GET"])
async def tasks_api(request: Request) -> JSONResponse:
    """Machine-readable task list for the local developer dashboard."""
    return JSONResponse(agent.list_tasks(request.query_params.get("status")))


@mcp.custom_route("/api/task", methods=["GET"])
async def task_detail_api(request: Request) -> JSONResponse:
    task_id = request.query_params.get("id", "")
    if not task_id:
        return JSONResponse({"error": "Provide ?id=<task_id>."}, status_code=400)
    result = agent.get_task(task_id)
    return JSONResponse(result, status_code=404 if "error" in result else 200)


@mcp.custom_route("/api/checkpoints", methods=["GET"])
async def checkpoints_api(request: Request) -> JSONResponse:
    """List only checkpoints whose recorded repository root matches the active workspace."""
    import json
    from app.core.orchestrator import checkpoint_store
    active_root = Path(session_manager.get_active_repo_path()).resolve()
    found = []
    for manifest_path in checkpoint_store.root.glob("*/*/manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            recorded_root = manifest.get("repository_root")
            if not recorded_root or Path(recorded_root).resolve() != active_root:
                continue
            found.append({"task_id": manifest["task_id"], "checkpoint_id": manifest["checkpoint_id"],
                          "path": manifest["path"], "kind": manifest.get("kind"),
                          "created_at": manifest.get("created_at"), "description": manifest.get("description", "")})
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            continue
    found.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return JSONResponse({"total": min(len(found), 100), "checkpoints": found[:100]})


@mcp.custom_route("/api/rollback", methods=["POST"])
async def rollback_checkpoint_api(request: Request) -> JSONResponse:
    """Recover a selected checkpoint after repository-root validation and write-policy enforcement."""
    import json
    from app.core.orchestrator import checkpoint_store
    try:
        payload = await request.json()
        task_id = str(payload.get("task_id", ""))
        checkpoint_id = str(payload.get("checkpoint_id", ""))
        active_root = Path(session_manager.get_active_repo_path()).resolve()
        checkpoint_root = checkpoint_store.root.resolve()
        manifest_path = (checkpoint_root / task_id / checkpoint_id / "manifest.json").resolve()
        if (not task_id or not checkpoint_id or checkpoint_root not in manifest_path.parents
                or manifest_path.name != "manifest.json" or not manifest_path.is_file()):
            return JSONResponse({"error": "Checkpoint was not found."}, status_code=404)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        recorded_root = manifest.get("repository_root")
        if not recorded_root or Path(recorded_root).resolve() != active_root:
            return JSONResponse({"error": "Checkpoint repository does not match the active workspace."}, status_code=403)
        result = agent.rollback_task_checkpoint(task_id, checkpoint_id)
        return JSONResponse(result, status_code=400 if "error" in result else 200)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@mcp.custom_route("/api/diff", methods=["GET"])
async def diff_api(request: Request) -> JSONResponse:
    """Return the current active repository diff for dashboard review."""
    file_path = request.query_params.get("path") or None
    staged = request.query_params.get("staged", "false").lower() == "true"
    result = git.git_diff(file_path=file_path, staged=staged)
    if "diff" in result:
        result["diff"] = result["diff"][:100_000]
        result["truncated"] = len(result["diff"]) >= 100_000
    return JSONResponse(result)


@mcp.custom_route("/api/approvals", methods=["GET"])
async def approvals_api(request: Request) -> JSONResponse:
    return JSONResponse(agent.list_approvals(request.query_params.get("status")))


@mcp.custom_route("/api/approvals/resolve", methods=["POST"])
async def resolve_approval_api(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Expected a JSON body."}, status_code=400)
    result = agent.resolve_approval(str(payload.get("approval_id", "")),
                                    str(payload.get("decision", "")), "dashboard-user")
    return JSONResponse(result, status_code=400 if "error" in result else 200)


@mcp.custom_route("/api/events", methods=["GET"])
async def events_api(request: Request) -> JSONResponse:
    from app.core.audit import audit
    limit = request.query_params.get("limit", "100")
    try:
        bounded_limit = max(1, min(int(limit), 500))
    except ValueError:
        return JSONResponse({"error": "limit must be an integer between 1 and 500."}, status_code=400)
    return JSONResponse({"events": audit.recent_events(request.query_params.get("task_id"), bounded_limit)})


@mcp.custom_route("/api/workers", methods=["GET"])
async def worker_jobs_api(request: Request) -> JSONResponse:
    return JSONResponse(agent.list_coding_worker_jobs(request.query_params.get("task_id")))


@mcp.custom_route("/api/worker", methods=["GET"])
async def worker_job_detail_api(request: Request) -> JSONResponse:
    job_id = request.query_params.get("id", "")
    if not job_id:
        return JSONResponse({"error": "Provide ?id=<job_id>."}, status_code=400)
    result = agent.get_coding_worker_job(job_id)
    return JSONResponse(result, status_code=404 if "error" in result else 200)


@mcp.custom_route("/api/worker/cancel", methods=["POST"])
async def worker_cancel_api(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Expected a JSON body."}, status_code=400)
    result = agent.cancel_coding_worker_job(str(payload.get("job_id", "")))
    return JSONResponse(result, status_code=400 if "error" in result else 200)


@mcp.custom_route("/api/worker-benchmarks", methods=["GET"])
async def worker_benchmarks_api(request: Request) -> JSONResponse:
    run_id = request.query_params.get("id")
    if run_id:
        result = agent.get_worker_benchmark(run_id)
        return JSONResponse(result, status_code=404 if "error" in result else 200)
    try:
        limit = max(1, min(int(request.query_params.get("limit", "50")), 200))
    except ValueError:
        return JSONResponse({"error": "limit must be an integer between 1 and 200."}, status_code=400)
    return JSONResponse(agent.list_worker_benchmarks(limit))


@mcp.custom_route("/api/worker-benchmarks/start", methods=["POST"])
async def worker_benchmark_start_api(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Expected a JSON body."}, status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse({"error": "JSON body must be an object."}, status_code=400)
    try:
        timeout_seconds = int(payload.get("timeout_seconds", 1800))
    except (TypeError, ValueError):
        return JSONResponse({"error": "timeout_seconds must be an integer."}, status_code=400)
    result = agent.start_worker_benchmark(json.dumps(payload.get("cases", [])), payload.get("workers"), timeout_seconds)
    return JSONResponse(result, status_code=400 if "error" in result else 202)


@mcp.custom_route("/dashboard", methods=["GET"])
async def task_dashboard(request: Request) -> HTMLResponse:
    """Lightweight live task/approval dashboard served by the MCP server itself."""
    return HTMLResponse(r'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MCP Coding Tool Dashboard</title><style>
body{font:14px system-ui;margin:0;background:#10151d;color:#e8edf5}header{padding:18px 24px;background:#192331;position:sticky;top:0}h1{font-size:20px;margin:0}main{padding:20px;display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}.panel{background:#192331;border:1px solid #2c3a4d;border-radius:10px;padding:16px;min-width:0}h2{font-size:16px;margin:0 0 12px}button{border:1px solid #53647a;background:#26364a;color:#fff;padding:6px 10px;border-radius:6px;cursor:pointer;margin:2px}button:hover{background:#344a64}.item{border-top:1px solid #344052;padding:10px 0;overflow-wrap:anywhere}.muted{color:#a9b8ca}.pill{border-radius:20px;background:#26364a;padding:2px 8px}.log{white-space:pre-wrap;max-height:320px;overflow:auto;font:12px ui-monospace,monospace}pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#8fc7ff}</style>
<header><h1>MCP Coding Tool <span class="muted">· live dashboard</span></h1><div class="muted">Tasks, approval requests, test state and audit events · refreshes every 4 seconds</div></header>
<main><section class="panel"><h2>Tasks</h2><div id="tasks">Loading…</div></section><section class="panel"><h2>Pending approvals</h2><div id="approvals">Loading…</div></section><section class="panel"><h2>Live audit log</h2><div class="muted">Latest redacted events</div><div id="events" class="log"></div></section><section class="panel"><h2>Diff review</h2><button onclick="loadDiff(false)">Working tree diff</button><button onclick="loadDiff(true)">Staged diff</button><div id="diff" class="log"></div></section><section class="panel"><h2>Recovery checkpoints</h2><div class="muted">Only checkpoints for the active repository are shown. Recovery restores the selected snapshot.</div><div id="checkpoints"></div></section><section class="panel"><h2>Worker jobs</h2><div class="muted">Independent CLI workers in isolated worktrees</div><div id="workers"></div></section><section class="panel"><h2>Benchmark runs</h2><div id="benchmarks"></div></section><section class="panel"><h2>Selected task details</h2><div id="detail" class="muted">Select a task to inspect plan, tests, and changed files.</div></section></main>
<script>
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function json(url,opts){const r=await fetch(url,opts);return await r.json()}
async function selectTask(id){const d=await json('/api/task?id='+encodeURIComponent(id));document.getElementById('detail').innerHTML='<pre>'+esc(JSON.stringify(d,null,2))+'</pre>'}
async function decide(id,decision){const r=await json('/api/approvals/resolve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({approval_id:id,decision})});if(r.error)alert(r.error);await refresh()}
async function loadDiff(staged){const d=await json('/api/diff?staged='+String(staged));document.getElementById('diff').textContent=d.diff||d.error||'No diff';}
async function rollbackCheckpoint(taskId,checkpointId,path){if(!confirm('Restore '+path+' from checkpoint '+checkpointId+'? This overwrites the current file state.'))return;const r=await json('/api/rollback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task_id:taskId,checkpoint_id:checkpointId})});if(r.error)alert(r.error);else alert('Restored '+(r.restored_path||path));await refresh()}
async function refresh(){try{const t=await json('/api/tasks');document.getElementById('tasks').innerHTML=(t.tasks||[]).map(x=>`<div class="item"><button onclick="selectTask('${esc(x.id)}')">Inspect</button> <b>${esc(x.objective)}</b><br><span class="muted">${esc(x.repository)} · ${esc(x.branch)} · ${esc(x.plan_progress)} steps · repairs ${esc(x.repair_attempts)}</span><br><span class="pill">${esc(x.status)}</span> ${x.final_verified?'✓ verified':'not verified'}</div>`).join('')||'<span class="muted">No tasks recorded.</span>';const a=await json('/api/approvals?status=pending');document.getElementById('approvals').innerHTML=(a.approvals||[]).map(x=>`<div class="item"><b>${esc(x.operation)}</b> → ${esc(x.target)}<br><span class="muted">Expires ${esc(x.expires_at)}</span><p>${esc(x.details)}</p><button onclick="decide('${esc(x.id)}','approved')">Approve</button><button onclick="decide('${esc(x.id)}','denied')">Deny</button></div>`).join('')||'<span class="muted">No pending approvals.</span>';const e=await json('/api/events?limit=80');document.getElementById('events').textContent=(e.events||[]).map(x=>`${x.ts||''} ${x.event||''} ${x.sub_event||x.operation||x.tool||''} ${x.task_id||''} ${x.detail||x.error||''}`).join('\n')||'No events yet.';const c=await json('/api/checkpoints');document.getElementById('checkpoints').innerHTML=(c.checkpoints||[]).map(x=>`<div class="item"><b>${esc(x.path)}</b><br><span class="muted">${esc(x.created_at)} · ${esc(x.kind)}</span><br><button onclick="rollbackCheckpoint('${esc(x.task_id)}','${esc(x.checkpoint_id)}','${esc(x.path)}')">Recover snapshot</button></div>`).join('')||'<span class="muted">No recoverable checkpoints for this workspace.</span>';}catch(err){document.getElementById('events').textContent='Dashboard API error: '+err}}
async function refreshWorkers(){try{const w=await json('/api/workers');document.getElementById('workers').innerHTML=(w.jobs||[]).slice(0,20).map(function(j){return '<div class="item"><b>'+esc(j.job_id)+'</b> <span class="pill">'+esc(j.status)+'</span><br><span class="muted">'+esc((j.workers||[]).join(', '))+'</span>'+(j.status==='running'?'<br><button onclick="cancelWorker(\''+esc(j.job_id)+'\')">Cancel</button>':'')+'<br><button onclick="showWorker(\''+esc(j.job_id)+'\')">Details</button></div>'}).join('')||'<span class="muted">No worker jobs yet.</span>';const b=await json('/api/worker-benchmarks?limit=10');document.getElementById('benchmarks').innerHTML=(b.runs||[]).map(function(x){return '<div class="item"><b>'+esc(x.run_id)+'</b> <span class="pill">'+esc(x.status)+'</span><br><span class="muted">'+esc(x.baseline_revision||'')+'</span><br><button onclick="showBenchmark(\''+esc(x.run_id)+'\')">Results</button></div>'}).join('')||'<span class="muted">No benchmark runs yet.</span>'}catch(err){document.getElementById('workers').textContent='Worker API unavailable: '+err}}
async function cancelWorker(id){const r=await json('/api/worker/cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:id})});if(r.error)alert(r.error);await refreshWorkers()}
async function showWorker(id){const d=await json('/api/worker?id='+encodeURIComponent(id));document.getElementById('detail').innerHTML='<pre>'+esc(JSON.stringify(d,null,2))+'</pre>'}
async function showBenchmark(id){const d=await json('/api/worker-benchmarks?id='+encodeURIComponent(id));document.getElementById('detail').innerHTML='<pre>'+esc(JSON.stringify(d,null,2))+'</pre>'}
refresh();refreshWorkers();setInterval(function(){refresh();refreshWorkers()},4000);
</script></html>''')


def create_app() -> Starlette:
    """
    Builds and returns a unified Starlette application supporting both
    Streamable HTTP (/mcp) and SSE (/sse) transports,
    with custom routes and Bearer authentication middleware.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    import os

    deployment_mode = settings.MCP_DEPLOYMENT_MODE.strip().lower()
    if deployment_mode not in {"local", "cloud"}:
        raise RuntimeError("MCP_DEPLOYMENT_MODE must be either 'local' or 'cloud'.")
    cloud_mode = deployment_mode == "cloud"
    if not settings.MCP_DASHBOARD_ENABLED:
        logger.info("Developer dashboard and /api/* dashboard endpoints are disabled by configuration.")
    try:
        host_ip = ipaddress.ip_address(settings.MCP_HOST.strip("[]"))
        non_loopback = not host_ip.is_loopback
    except ValueError:
        non_loopback = settings.MCP_HOST.lower() not in {"localhost"}
    if non_loopback and not settings.MCP_AUTH_ENABLED:
        raise RuntimeError("Refusing to bind an unauthenticated MCP server to a non-loopback host. Enable MCP_AUTH_ENABLED and set a strong MCP_AUTH_TOKEN.")
    if non_loopback and len(settings.MCP_AUTH_TOKEN.strip()) < 32:
        raise RuntimeError("Non-loopback MCP hosts require MCP_AUTH_TOKEN with at least 32 characters.")
    if cloud_mode:
        token = settings.MCP_AUTH_TOKEN.strip()
        if len(token) < 32:
            raise RuntimeError(
                "Cloud deployment requires MCP_AUTH_TOKEN with at least 32 characters."
            )
        if not settings.MCP_AUTH_ENABLED:
            raise RuntimeError("Cloud deployment requires MCP_AUTH_ENABLED=true.")

    # Preserve the MCP SDK's DNS-rebinding protection in every environment.
    # In cloud mode require an exact service hostname rather than a wildcard.
    allowed_hosts_env = os.environ.get("MCP_ALLOWED_HOSTS", "").strip()
    allowed_origins_env = os.environ.get("MCP_ALLOWED_ORIGINS", "").strip()
    allowed_hosts = [v.strip() for v in allowed_hosts_env.split(",") if v.strip()]
    allowed_origins = [v.strip() for v in allowed_origins_env.split(",") if v.strip()]
    if cloud_mode:
        if not allowed_hosts:
            raise RuntimeError("Cloud deployment requires MCP_ALLOWED_HOSTS set to the exact public service hostname.")
        if any("*" in host for host in allowed_hosts):
            raise RuntimeError("Wildcard hosts are not permitted for cloud deployment; use the exact service hostname.")
        if any("/" in host or "://" in host or "@" in host or any(ch.isspace() for ch in host)
               for host in allowed_hosts):
            raise RuntimeError("MCP_ALLOWED_HOSTS must contain exact hostnames only, without scheme, path, or credentials.")
        if any("*" in origin or not origin.startswith("https://") or "/" in origin[len("https://"):]
               for origin in allowed_origins):
            raise RuntimeError("MCP_ALLOWED_ORIGINS must contain exact HTTPS origins without paths or wildcards.")
    # Hosted mode always enforces Host validation. Local mode preserves the
    # existing tunnel workflow unless the developer explicitly configures hosts.
    # Public cloud deployments must never fall back to disabled protection.
    transport_kwargs = {
        "enable_dns_rebinding_protection": cloud_mode or bool(allowed_hosts)
    }
    if allowed_hosts:
        transport_kwargs["allowed_hosts"] = allowed_hosts
    if allowed_origins:
        transport_kwargs["allowed_origins"] = allowed_origins
    transport_sec = TransportSecuritySettings(**transport_kwargs)

    http_app = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        transport_security=transport_sec,
    )

    sse_app = mcp.sse_app(
        sse_path="/sse",
        transport_security=transport_sec,
    )

    for route in sse_app.routes:
        path = getattr(route, "path", None)
        if path and path not in [getattr(cr, "path", None) for cr in http_app.routes]:
            http_app.routes.append(route)

    # Middleware also enforces dashboard disablement in local mode; auth itself remains config-gated.
    http_app.add_middleware(BearerAuthMiddleware)

    return http_app


def start_server(host: str = None, port: int = None):
    """Starts the standalone MCP ASGI server with Uvicorn."""
    srv_host = host or settings.MCP_HOST
    srv_port = port or settings.MCP_PORT
    try:
        host_ip = ipaddress.ip_address(srv_host.strip("[]"))
        non_loopback = not host_ip.is_loopback
    except ValueError:
        non_loopback = srv_host.lower() not in {"localhost"}
    if non_loopback and (not settings.MCP_AUTH_ENABLED or len(settings.MCP_AUTH_TOKEN.strip()) < 32):
        raise RuntimeError("Non-loopback server binds require MCP_AUTH_ENABLED=true and MCP_AUTH_TOKEN with at least 32 characters.")

    logger.info("=" * 70)
    logger.info("Multi-Repository Autonomous Coding Agent MCP Server v2.0")
    logger.info(f"Listening: http://{srv_host}:{srv_port}")
    logger.info(f"Health Endpoint: http://{srv_host}:{srv_port}/health")
    logger.info(f"Tool List:       http://{srv_host}:{srv_port}/tools")
    logger.info(f"Streamable HTTP: http://{srv_host}:{srv_port}/mcp")
    logger.info(f"SSE Transport:   http://{srv_host}:{srv_port}/sse")
    logger.info(f"Permission Profile: {policy_engine.profile.value}")
    logger.info(f"Authentication: {'ENABLED' if settings.MCP_AUTH_ENABLED else 'DISABLED (No Authentication Mode)'}")
    logger.info("=" * 70)

    app = create_app()
    uvicorn.run(app, host=srv_host, port=srv_port, log_level=settings.MCP_LOG_LEVEL.lower())


if __name__ == "__main__":
    start_server()
