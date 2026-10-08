import os
import fnmatch
from pathlib import Path
from typing import Dict, Any, Optional, List
from app.config import settings
from app.core.session import session_manager
from app.core.security import security_engine

def search_code(
    query: str,
    path: str = ".",
    case_sensitive: bool = False,
    file_extension: Optional[str] = None,
    max_results: int = 50,
    context_lines: int = 1
) -> Dict[str, Any]:
    """
    Search for text, identifiers, or keywords inside files across the active repository.
    Supports file extension filtering, case sensitivity, context lines, and automatically skips build artifacts & binaries.
    """
    try:
        repo_root = session_manager.get_active_repo_path()
        target_dir = security_engine.sanitize_and_resolve_path(path)
        if not target_dir.is_dir():
            return {"error": f"Search path '{path}' is not a valid directory."}

        matches = []
        ignored = {".git", "__pycache__", "node_modules", "venv", ".venv", ".pytest_cache", "dist", "build", "coverage", "target", ".idea", ".vscode"}

        target_query = query if case_sensitive else query.lower()
        effective_limit = min(max_results, settings.MAX_SEARCH_RESULTS)

        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in ignored]
            for filename in files:
                # Extension filter
                if file_extension:
                    ext = file_extension if file_extension.startswith(".") else f".{file_extension}"
                    if not filename.endswith(ext):
                        continue

                file_full = Path(root) / filename
                try:
                    resolved = security_engine.sanitize_and_resolve_path(str(file_full))
                    if resolved.stat().st_size > settings.MAX_FILE_SIZE_BYTES:
                        continue

                    # Check for binary file
                    with open(resolved, "rb") as bf:
                        chunk = bf.read(1024)
                        if b"\0" in chunk:
                            continue

                    with open(resolved, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()

                    for idx, line in enumerate(lines, start=1):
                        search_target = line if case_sensitive else line.lower()
                        if target_query in search_target:
                            start_ctx = max(0, idx - 1 - context_lines)
                            end_ctx = min(len(lines), idx + context_lines)
                            surrounding = [l.rstrip("\r\n") for l in lines[start_ctx:end_ctx]]

                            matches.append({
                                "file": str(resolved.relative_to(repo_root)).replace("\\", "/"),
                                "line": idx,
                                "match": line.strip(),
                                "context": surrounding
                            })
                            if len(matches) >= effective_limit:
                                break
                except Exception:
                    continue

                if len(matches) >= effective_limit:
                    break
            if len(matches) >= effective_limit:
                break

        return {
            "repository": session_manager.get_active_repo_name(),
            "query": query,
            "total_matches": len(matches),
            "results": matches
        }
    except Exception as e:
        return {"error": str(e)}
