import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from app.config import settings
from app.core.session import session_manager
from app.core.security import security_engine, SecurityError

def list_files(path: str = ".", recursive: bool = False, max_results: int = 200) -> Dict[str, Any]:
    """
    List files and directories within the active repository at the given relative path.
    Automatically filters ignored directories (.git, node_modules, __pycache__, .venv) and protected secret files.
    """
    try:
        repo_root = session_manager.get_active_repo_path()
        target_dir = security_engine.sanitize_and_resolve_path(path)
        if not target_dir.is_dir():
            return {"error": f"'{path}' is not a directory or does not exist."}

        results = []
        ignored = {".git", "__pycache__", "node_modules", "venv", ".venv", ".pytest_cache", "dist", "build", "target", ".idea", ".vscode"}

        if recursive:
            for root, dirs, files in os.walk(target_dir):
                dirs[:] = [d for d in dirs if d not in ignored]
                for f in files:
                    try:
                        resolved = security_engine.sanitize_and_resolve_path(str(Path(root) / f))
                        rel = resolved.relative_to(repo_root)
                        results.append({
                            "path": str(rel).replace("\\", "/"),
                            "type": "file",
                            "size_bytes": resolved.stat().st_size
                        })
                    except SecurityError:
                        continue
                    if len(results) >= max_results:
                        break
                if len(results) >= max_results:
                    break
        else:
            for item in target_dir.iterdir():
                if item.name in ignored:
                    continue
                try:
                    resolved = security_engine.sanitize_and_resolve_path(str(item))
                    rel = resolved.relative_to(repo_root)
                    results.append({
                        "path": str(rel).replace("\\", "/"),
                        "type": "directory" if resolved.is_dir() else "file",
                        "size_bytes": resolved.stat().st_size if resolved.is_file() else 0
                    })
                except SecurityError:
                    continue
                if len(results) >= max_results:
                    break

        return {
            "repository": session_manager.get_active_repo_name(),
            "base_directory": str(target_dir.relative_to(repo_root)).replace("\\", "/"),
            "count": len(results),
            "entries": results
        }
    except Exception as e:
        return {"error": str(e)}

def read_file(path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> Dict[str, Any]:
    """
    Read the contents of a source code or text file in the active repository.
    Path must be relative to the active repository root. Secret files (.env, *.key, credentials) are strictly blocked.
    """
    try:
        resolved = security_engine.sanitize_and_resolve_path(path)
        if not resolved.is_file():
            return {"error": f"File '{path}' does not exist or is a directory."}

        if resolved.stat().st_size > settings.MAX_FILE_SIZE_BYTES:
            return {"error": f"File exceeds maximum read size limit of {settings.MAX_FILE_SIZE_BYTES} bytes."}

        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total_lines = len(lines)
        if start_line is not None or end_line is not None:
            s = max(1, start_line or 1)
            e = min(total_lines, end_line or total_lines)
            return {
                "file_path": str(resolved.relative_to(session_manager.get_active_repo_path())).replace("\\", "/"),
                "start_line": s,
                "end_line": e,
                "total_lines": total_lines,
                "content": "".join(lines[s - 1:e])
            }

        return {
            "file_path": str(resolved.relative_to(session_manager.get_active_repo_path())).replace("\\", "/"),
            "total_lines": total_lines,
            "content": "".join(lines)
        }
    except Exception as e:
        return {"error": str(e)}

def write_file(path: str, content: str, overwrite: bool = True) -> Dict[str, Any]:
    """
    Write or update a file in the active repository.
    Directly modifies the file on disk so changes are immediately visible in local VS Code.
    Automatically creates any missing parent directories.
    """
    try:
        resolved = security_engine.sanitize_and_resolve_path(path)
        if resolved.exists() and not overwrite:
            return {"error": f"File '{path}' already exists and overwrite is set to False."}

        encoded_len = len(content.encode("utf-8"))
        if encoded_len > settings.MAX_FILE_SIZE_BYTES:
            return {"error": f"Content exceeds maximum file size limit of {settings.MAX_FILE_SIZE_BYTES} bytes."}

        resolved.parent.mkdir(parents=True, exist_ok=True)
        with open(resolved, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)

        return {
            "success": True,
            "file_path": str(resolved.relative_to(session_manager.get_active_repo_path())).replace("\\", "/"),
            "bytes_written": encoded_len
        }
    except Exception as e:
        return {"error": str(e)}

def create_directory(path: str) -> Dict[str, Any]:
    """
    Create a new directory (and any necessary parent directories) inside the active repository.
    """
    try:
        resolved = security_engine.sanitize_and_resolve_path(path)
        resolved.mkdir(parents=True, exist_ok=True)
        return {
            "success": True,
            "directory_path": str(resolved.relative_to(session_manager.get_active_repo_path())).replace("\\", "/")
        }
    except Exception as e:
        return {"error": str(e)}

def delete_file(path: str) -> Dict[str, Any]:
    """
    Delete a specific file inside the active repository.
    SAFETY GUARANTEE: Directory deletion is rejected to prevent recursive accidental data loss.
    """
    try:
        resolved = security_engine.sanitize_and_resolve_path(path)
        if not resolved.is_file():
            return {"error": f"File '{path}' not found or is a directory."}
        resolved.unlink()
        return {
            "success": True,
            "deleted_file": str(resolved.relative_to(session_manager.get_active_repo_path())).replace("\\", "/")
        }
    except Exception as e:
        return {"error": str(e)}
