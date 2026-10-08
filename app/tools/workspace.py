import subprocess
from pathlib import Path
from typing import Dict, Any, List
from app.core.repository import repository_manager
from app.core.session import session_manager

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
    Add a new local repository path to the MCP workspace registry.
    Does not modify or duplicate any application code.
    """
    try:
        info = repository_manager.add_repository(name, path, description, enabled)
        return {"success": True, "message": f"Repository '{name}' added successfully.", "repository": info}
    except Exception as e:
        return {"error": str(e)}

def remove_repository(name: str) -> Dict[str, Any]:
    """
    Remove a repository from the MCP workspace registry.
    SAFETY GUARANTEE: This only removes the registry entry; it NEVER deletes or modifies the physical repository on disk.
    """
    success = repository_manager.remove_repository(name)
    if not success:
        return {"error": f"Repository '{name}' not found in registry."}
    return {"success": True, "message": f"Repository '{name}' removed from registry. Physical files were untouched."}
