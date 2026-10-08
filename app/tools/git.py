import subprocess
from typing import Dict, Any, Optional, List
from app.core.session import session_manager
from app.core.security import security_engine

def git_status() -> Dict[str, Any]:
    """
    Inspect working tree status of the active repository (staged, unstaged, untracked files).
    """
    try:
        repo_root = session_manager.get_active_repo_path()
        res = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10
        )
        return {
            "repository": session_manager.get_active_repo_name(),
            "status_output": res.stdout,
            "stderr": res.stderr,
            "exit_code": res.returncode
        }
    except Exception as e:
        return {"error": str(e)}

def git_diff(file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    View uncommitted git diffs in the active repository to inspect modifications before finishing a task.
    """
    try:
        repo_root = session_manager.get_active_repo_path()
        cmd = ["git", "diff"]
        if file_path:
            resolved = security_engine.sanitize_and_resolve_path(file_path)
            cmd.append(str(resolved.relative_to(repo_root)))

        res = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=15
        )
        return {
            "repository": session_manager.get_active_repo_name(),
            "diff": res.stdout,
            "exit_code": res.returncode
        }
    except Exception as e:
        return {"error": str(e)}

def git_branch() -> Dict[str, Any]:
    """
    List active branch and all available local and remote branches in the active repository.
    """
    try:
        repo_root = session_manager.get_active_repo_path()
        res = subprocess.run(
            ["git", "branch", "-a"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10
        )
        return {
            "repository": session_manager.get_active_repo_name(),
            "branches": res.stdout,
            "exit_code": res.returncode
        }
    except Exception as e:
        return {"error": str(e)}

def git_log(max_commits: int = 10) -> Dict[str, Any]:
    """
    View recent commit history in the active repository.
    """
    try:
        repo_root = session_manager.get_active_repo_path()
        limit = min(max_commits, 50)
        res = subprocess.run(
            ["git", "log", f"-n{limit}", "--oneline"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10
        )
        return {
            "repository": session_manager.get_active_repo_name(),
            "log": res.stdout,
            "exit_code": res.returncode
        }
    except Exception as e:
        return {"error": str(e)}

def git_show(commit_hash: str = "HEAD") -> Dict[str, Any]:
    """
    Inspect the details and diff of a specific Git commit (defaults to HEAD).
    """
    try:
        repo_root = session_manager.get_active_repo_path()
        # Sanitize commit hash to prevent injection
        safe_hash = "".join(c for c in commit_hash if c.isalnum() or c in "^~_-")
        res = subprocess.run(
            ["git", "show", "--stat", safe_hash],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10
        )
        return {
            "repository": session_manager.get_active_repo_name(),
            "commit": safe_hash,
            "details": res.stdout,
            "exit_code": res.returncode
        }
    except Exception as e:
        return {"error": str(e)}

def git_changed_files() -> Dict[str, Any]:
    """
    List names of all files modified, added, or deleted in the working tree.
    """
    try:
        repo_root = session_manager.get_active_repo_path()
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10
        )
        files = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if len(line) > 3:
                files.append(line[3:])
        return {
            "repository": session_manager.get_active_repo_name(),
            "total_changed": len(files),
            "changed_files": files
        }
    except Exception as e:
        return {"error": str(e)}
