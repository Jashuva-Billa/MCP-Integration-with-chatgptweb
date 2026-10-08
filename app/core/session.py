import logging
import threading
from pathlib import Path
from typing import Dict, Optional, Tuple
from app.core.repository import repository_manager

logger = logging.getLogger("mcp_server.session")

class SessionManager:
    """
    Manages active repository workspace selection per MCP session ID.
    Provides multi-session thread safety and isolation.
    """

    def __init__(self):
        self._sessions: Dict[str, str] = {}
        self._default_workspace: Optional[str] = None
        self._lock = threading.Lock()
        
        # Initialize default workspace if repositories exist
        repos = repository_manager.list_repositories()
        if repos:
            # Pick first enabled existing repo
            for r in repos:
                if r.get("enabled", True) and r.get("exists_on_disk", False):
                    self._default_workspace = r["name"]
                    break
            if not self._default_workspace and repos:
                self._default_workspace = repos[0]["name"]

    def get_active_repo_name(self, session_id: Optional[str] = None) -> Optional[str]:
        """Returns the active repository name for the session, or the default workspace."""
        with self._lock:
            if session_id and session_id in self._sessions:
                return self._sessions[session_id]
            return self._default_workspace

    def set_active_repo_name(self, repo_name: str, session_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        Sets the active repository for the specified session.
        Validates repository existence in registry and on disk.
        """
        repo_info = repository_manager.get_repository(repo_name)
        if not repo_info:
            available = [r["name"] for r in repository_manager.list_repositories()]
            avail_str = ", ".join(available) if available else "None"
            return False, f"Repository '{repo_name}' not found in registry. Available: [{avail_str}]"

        if not repo_info.get("enabled", True):
            return False, f"Repository '{repo_name}' is currently disabled in configuration."

        repo_path = Path(repo_info["path"]).resolve()
        if not repo_path.exists() or not repo_path.is_dir():
            return False, f"Configured path for '{repo_name}' does not exist on disk: {repo_path}"

        with self._lock:
            if session_id:
                self._sessions[session_id] = repo_name
            self._default_workspace = repo_name

        logger.info(f"Session [{session_id or 'default'}] active workspace set to '{repo_name}' ({repo_path})")
        return True, f"Active repository set to '{repo_name}' ({repo_path})"

    def get_active_repo_path(self, session_id: Optional[str] = None) -> Path:
        """
        Returns the resolved Path of the currently active repository.
        Raises RuntimeError if no active repository is selected or if path is missing.
        """
        active_name = self.get_active_repo_name(session_id)
        if not active_name:
            raise RuntimeError("No active repository selected. Please call select_repository() first.")

        repo_info = repository_manager.get_repository(active_name)
        if not repo_info:
            raise RuntimeError(f"Active repository '{active_name}' not found in registry.")

        repo_path = Path(repo_info["path"]).resolve()
        if not repo_path.exists() or not repo_path.is_dir():
            raise RuntimeError(f"Active repository directory does not exist: {repo_path}")

        return repo_path

session_manager = SessionManager()
