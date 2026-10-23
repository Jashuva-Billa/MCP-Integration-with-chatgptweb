import sys
from pathlib import Path

# Ensure project root is in sys.path for direct script execution
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ruff: noqa: E402  # sys.path bootstrap intentionally precedes application imports
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

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
mcp.tool()(git.git_fetch)                     # NEW: remote fetch
mcp.tool()(git.git_pull)                      # NEW: remote pull
mcp.tool()(git.rollback_git_reset_checkpoint) # Restore hard-reset safety checkpoint

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
        "tool_count": 72,
    })


@mcp.custom_route("/tools", methods=["GET"])
async def tool_list(request: Request) -> JSONResponse:
    """Returns a categorized list of all registered MCP tools."""
    return JSONResponse({
        "total_tools": 72,
        "categories": {
            "workspace_management": ["list_repositories", "select_repository", "get_current_repository", "add_repository", "remove_repository"],
            "filesystem_read": ["list_files", "read_file"],
            "filesystem_write": ["write_file", "create_directory"],
            "filesystem_destructive": ["delete_file", "delete_directory", "move_file", "copy_file"],
            "filesystem_safety": ["backup_file", "restore_file", "diff_preview"],
            "editing": ["replace_in_file"],
            "search_and_intelligence": ["search_code", "find_symbol", "find_references", "list_functions", "list_classes", "get_file_structure"],
            "command_execution": ["run_command", "run_tests", "install_dependencies"],
            "git_read": ["git_status", "git_diff", "git_branch", "git_log", "git_show", "git_changed_files"],
            "git_write_and_remote": ["git_stage", "git_commit", "git_create_branch", "git_switch_branch", "git_reset", "git_worktree_add", "git_worktree_remove", "git_push", "git_fetch", "git_pull"],
            "repository_analysis": ["analyze_repository", "inspect_workspace"],
            "permissions": ["get_permission_profile", "set_permission_profile"],
            "execution_profile": ["get_execution_profile", "configure_execution_profile"],
            "skills": ["prepare_task_workflow", "list_skills", "get_skill", "reload_skills"],
            "hooks": ["list_hooks", "fire_hook"],
            "task_state": ["create_task", "get_task", "list_tasks", "update_task_step", "complete_task", "add_task_issue", "record_test_result", "plan_repair_attempt", "verify_task", "start_chatgpt_coding_task", "record_chatgpt_task_progress", "finish_chatgpt_coding_task"],
            "autonomous_execution": ["run_autonomous_task", "rollback_task_checkpoint", "run_coding_benchmark", "get_benchmark_report", "record_chatgpt_benchmark_result"],
            "git_recovery": ["rollback_git_reset_checkpoint"],
        }
    })


def create_app() -> Starlette:
    """
    Builds and returns a unified Starlette application supporting both
    Streamable HTTP (/mcp) and SSE (/sse) transports,
    with custom routes and Bearer authentication middleware.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    transport_sec = TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
        allowed_hosts=["*"],
        allowed_origins=["*"],
    )

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

    if settings.MCP_AUTH_ENABLED:
        http_app.add_middleware(BearerAuthMiddleware)

    return http_app


def start_server(host: str = None, port: int = None):
    """Starts the standalone MCP ASGI server with Uvicorn."""
    srv_host = host or settings.MCP_HOST
    srv_port = port or settings.MCP_PORT

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
