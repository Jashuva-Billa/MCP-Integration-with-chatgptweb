"""Combined read-only inspection to reduce serial MCP round trips."""
from typing import Any, Dict

from app.tools import filesystem, git, workspace


def inspect_workspace(max_files: int = 60) -> Dict[str, Any]:
    """Return active repository metadata, Git status, and a shallow file listing in one call.

    Use this for an initial repository overview instead of calling repository metadata,
    Git status, and top-level file listing separately. File contents are not returned.
    """
    limit = max(1, min(int(max_files), 100))
    metadata = workspace.get_current_repository()
    status = git.git_status()
    files = filesystem.list_files(".", recursive=False, max_results=limit)
    return {
        "repository": metadata,
        "git_status": status,
        "top_level_files": files,
        "note": "Read-only overview. Use targeted file reads and searches for details.",
    }
