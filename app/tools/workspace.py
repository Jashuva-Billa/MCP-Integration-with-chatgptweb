import subprocess
from pathlib import Path
from typing import Dict, Any
from app.core.repository import repository_manager
from app.core.session import session_manager
from app.config import settings


def list_repositories() -> Dict[str, Any]:
    """
    List all registered repositories in the registry, their local disk paths, and active status.
    ChatGPT should call this tool to discover available local codebases.
    """
    repos = repository_manager.list_repositories()
    active = session_manager.get_active_repo_name()
    return {
        "active_repository": active,
        "total_configured": len(repos),
        "repositories": [
            {
                "name": r["name"],
                "path": r["path"],
                "description": r.get("description", ""),
                "enabled": r.get("enabled", True),
                "is_active": (r["name"] == active),
                "exists_on_disk": r.get("exists_on_disk", False)
            }
            for r in repos
        ]
    }


def select_repository(repository_name: str) -> Dict[str, Any]:
    """
    Select the active repository that will become the working workspace for the current MCP session.
    All subsequent filesystem, search, code intelligence, terminal, and Git tools will operate ONLY inside this repository.
    """
    success, message = session_manager.set_active_repo_name(repository_name)
    return {
        "success": success,
        "message": message,
        "active_repository": session_manager.get_active_repo_name()
    }


def get_current_repository() -> Dict[str, Any]:
    """
    Get metadata, root absolute path, and active Git branch of the currently selected repository.
    """
    active_name = session_manager.get_active_repo_name()
    if not active_name:
        return {"error": "No repository currently selected. Please call select_repository() first."}

    repo_path = session_manager.get_active_repo_path()
    branch = "unknown"
    try:
        res = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=5
        )
        if res.returncode == 0 and res.stdout.strip():
            branch = res.stdout.strip()
    except Exception:
        pass

    return {
        "repository_name": active_name,
        "absolute_path": str(repo_path),
        "git_branch": branch
    }


def add_repository(name: str, path: str, description: str = "", enabled: bool = True) -> Dict[str, Any]:
    """
    Register an existing directory on the server. In cloud mode, prefer clone_github_repository.
    """
    try:
        if settings.MCP_DEPLOYMENT_MODE.strip().lower() == "cloud":
            allowed_root = Path(settings.MCP_WORKSPACE_ROOT).expanduser().resolve()
            requested_path = Path(path).expanduser().resolve()
            if requested_path == allowed_root or allowed_root not in requested_path.parents:
                return {"error": "Cloud mode only allows registering repositories inside MCP_WORKSPACE_ROOT. Use clone_github_repository for remote code."}
        info = repository_manager.add_repository(name, path, description, enabled)
        return {"success": True, "message": f"Repository '{name}' added successfully.", "repository": info}
    except Exception as e:
        return {"error": str(e)}


def clone_github_repository(
    repository_url: str,
    workspace_name: str,
    branch: str = "",
    description: str = "",
) -> Dict[str, Any]:
    """
    Clone an explicitly allowlisted GitHub repository into the cloud workspace and register it.

    Set MCP_GITHUB_ALLOWED_REPOS to comma-separated owner/repository slugs before using this tool.
    For private repositories, set MCP_GITHUB_TOKEN as a secret in the hosting provider.
    """
    try:
        if not settings.MCP_GITHUB_CLONE_ENABLED:
            return {"error": "GitHub cloning is disabled. Set MCP_GITHUB_CLONE_ENABLED=true after configuring the repository allowlist."}
        from app.core.github_workspace import clone_github_repository as clone_workspace
        return clone_workspace(repository_url, workspace_name, branch, description)
    except Exception as e:
        return {"error": str(e)}


def remove_repository(name: str) -> Dict[str, Any]:
    """
    Remove a repository from the registry ONLY.
    SAFETY GUARANTEE: This only removes the registry entry; it NEVER deletes or modifies the physical repository on disk.
    """
    success = repository_manager.remove_repository(name)
    if not success:
        return {"error": f"Repository '{name}' not found in registry."}
    return {"success": True, "message": f"Repository '{name}' removed from registry. Physical files were untouched."}
