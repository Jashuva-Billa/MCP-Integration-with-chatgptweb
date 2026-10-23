"""
Expanded Filesystem Tools
==========================
Implements the full file-operation surface required by an autonomous coding agent:
  read, write, list, create_directory,
  delete_file, delete_directory (recursive),
  move/rename, copy, backup, restore,
  diff preview.

Every destructive operation is guarded by the policy engine.
All operations are audit-logged.
"""

from __future__ import annotations

import difflib
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.audit import audit
from app.core.permissions import PolicyViolation, policy_engine
from app.core.security import SecurityError, security_engine
from app.core.session import session_manager


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _rel(resolved: Path) -> str:
    return str(resolved.relative_to(session_manager.get_active_repo_path())).replace("\\", "/")


def _repo() -> str:
    return session_manager.get_active_repo_name() or ""


def _checkpoint_before(path: Path, operation: str) -> Dict[str, str]:
    """Persist a recoverable snapshot before a mutating filesystem operation."""
    import uuid
    from app.core.orchestrator import checkpoint_store

    repo_root = Path(session_manager.get_active_repo_path()).resolve()
    relative = str(path.resolve().relative_to(repo_root)).replace("\\", "/")
    task_id = f"manual-{uuid.uuid4().hex[:10]}"
    manifest = checkpoint_store.create(task_id, relative, repo_root)
    audit.log_task_event(task_id, "checkpoint_created", detail=f"{operation}:{relative}:{manifest['checkpoint_id']}")
    return {"checkpoint_task_id": task_id, "checkpoint_id": manifest["checkpoint_id"]}


def _fire_mutation_hook(event: str, path: Path, operation: str) -> None:
    from app.core.hooks import hooks_engine
    hooks_engine.fire(event, {"file": str(path), "operation": operation})


def _rollback_checkpoint(checkpoint: Optional[Dict[str, str]]) -> None:
    if not checkpoint:
        return
    from app.core.orchestrator import checkpoint_store
    root = Path(session_manager.get_active_repo_path()).resolve()
    checkpoint_store.rollback(checkpoint["checkpoint_id"], checkpoint["checkpoint_task_id"], root)


def _rollback_checkpoints(checkpoints: List[Dict[str, str]]) -> None:
    for checkpoint in reversed(checkpoints):
        _rollback_checkpoint(checkpoint)


# ---------------------------------------------------------------------------
# Read operations (unchanged API, but now audit-logged)
# ---------------------------------------------------------------------------

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
            for item in sorted(target_dir.iterdir()):
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
            "repository": _repo(),
            "base_directory": str(target_dir.relative_to(repo_root)).replace("\\", "/"),
            "count": len(results),
            "entries": results
        }
    except Exception as e:
        return {"error": str(e)}


def read_file(path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> Dict[str, Any]:
    """
    Read the contents of a source code or text file in the active repository.
    Path must be relative to the active repository root. Secret files are strictly blocked.
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
                "file_path": _rel(resolved),
                "start_line": s,
                "end_line": e,
                "total_lines": total_lines,
                "content": "".join(lines[s - 1:e])
            }

        return {
            "file_path": _rel(resolved),
            "total_lines": total_lines,
            "content": "".join(lines)
        }
    except Exception as e:
        return {"error": str(e)}


def write_file(path: str, content: str, overwrite: bool = True) -> Dict[str, Any]:
    """
    Write or update a file in the active repository.
    Directly modifies the file on disk so changes are immediately visible in VS Code.
    Automatically creates any missing parent directories.
    """
    checkpoint = None
    try:
        policy_engine.require_fs_write()
        resolved = security_engine.sanitize_and_resolve_path(path)
        if resolved.exists() and not overwrite:
            return {"error": f"File '{path}' already exists and overwrite is set to False."}

        if resolved.is_dir():
            return {"error": f"'{path}' is a directory."}
        encoded_len = len(content.encode("utf-8"))
        if encoded_len > settings.MAX_FILE_SIZE_BYTES:
            return {"error": f"Content exceeds maximum file size limit of {settings.MAX_FILE_SIZE_BYTES} bytes."}

        checkpoint = _checkpoint_before(resolved, "write_file")
        _fire_mutation_hook("before_file_edit", resolved, "write")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        with open(resolved, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        _fire_mutation_hook("after_file_edit", resolved, "write")

        rel = _rel(resolved)
        audit.log_file_change("write", rel, _repo(), bytes_written=encoded_len)
        return {"success": True, "file_path": rel, "bytes_written": encoded_len, **checkpoint}
    except PolicyViolation as pv:
        audit.log_permission_denied("write_file", "fs_write", policy_engine.profile.value)
        return {"error": f"Permission denied: {pv}"}
    except Exception as e:
        try:
            _rollback_checkpoint(checkpoint)
        except Exception as rollback_error:
            return {"error": f"{e}; automatic rollback also failed: {rollback_error}"}
        return {"error": str(e)}


def create_directory(path: str) -> Dict[str, Any]:
    """Create a new directory (and any necessary parent directories) inside the active repository."""
    try:
        policy_engine.require_fs_write()
        resolved = security_engine.sanitize_and_resolve_path(path)
        resolved.mkdir(parents=True, exist_ok=True)
        rel = _rel(resolved)
        audit.log_file_change("mkdir", rel, _repo())
        return {"success": True, "directory_path": rel}
    except PolicyViolation as pv:
        return {"error": f"Permission denied: {pv}"}
    except Exception as e:
        return {"error": str(e)}


def delete_file(path: str) -> Dict[str, Any]:
    """
    Delete a specific file inside the active repository.
    SAFETY: Directory deletion is rejected — use delete_directory for that.
    """
    checkpoint = None
    try:
        policy_engine.require_fs_delete_file()
        resolved = security_engine.sanitize_and_resolve_path(path)
        if not resolved.is_file():
            return {"error": f"'{path}' is not a file or does not exist."}
        checkpoint = _checkpoint_before(resolved, "delete_file")
        _fire_mutation_hook("before_file_edit", resolved, "delete")
        resolved.unlink()
        _fire_mutation_hook("after_file_edit", resolved, "delete")
        rel = str(resolved.relative_to(session_manager.get_active_repo_path())).replace("\\", "/")
        audit.log_file_change("delete_file", rel, _repo())
        return {"success": True, "deleted_file": rel, **checkpoint}
    except PolicyViolation as pv:
        audit.log_permission_denied("delete_file", "fs_delete_file", policy_engine.profile.value)
        return {"error": f"Permission denied: {pv}"}
    except Exception as e:
        try:
            _rollback_checkpoint(checkpoint)
        except Exception as rollback_error:
            return {"error": f"{e}; automatic rollback also failed: {rollback_error}"}
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# New operations
# ---------------------------------------------------------------------------

def delete_directory(path: str, dry_run: bool = False) -> Dict[str, Any]:
    """
    Recursively delete a directory and all its contents inside the active repository.

    CAUTION: This is irreversible. Requires the 'full' or 'unrestricted' profile.
    Use dry_run=True to preview what would be deleted without removing anything.

    Safety guards
    - Never deletes the repository root itself.
    - Never deletes outside the active repository boundary.
    - dry_run mode shows the full file list without removing anything.
    """
    checkpoint = None
    try:
        policy_engine.require_fs_delete_directory()
        resolved = security_engine.sanitize_and_resolve_path(path)
        repo_root = session_manager.get_active_repo_path()

        if not resolved.exists():
            return {"error": f"'{path}' does not exist."}
        if not resolved.is_dir():
            return {"error": f"'{path}' is not a directory. Use delete_file for files."}

        # Prevent deleting the repo root itself
        if resolved.resolve() == repo_root.resolve():
            return {"error": "Refusing to delete the active repository root directory."}

        # Collect a manifest of what would be deleted
        manifest: List[str] = []
        for item in resolved.rglob("*"):
            try:
                manifest.append(str(item.relative_to(repo_root)).replace("\\", "/"))
            except ValueError:
                pass
        manifest.append(str(resolved.relative_to(repo_root)).replace("\\", "/"))

        if dry_run:
            return {
                "dry_run": True,
                "directory": str(resolved.relative_to(repo_root)).replace("\\", "/"),
                "would_delete_count": len(manifest),
                "would_delete": manifest,
            }

        checkpoint = _checkpoint_before(resolved, "delete_directory")
        _fire_mutation_hook("before_file_edit", resolved, "delete_directory")
        shutil.rmtree(resolved)
        _fire_mutation_hook("after_file_edit", resolved, "delete_directory")
        rel = str(resolved.relative_to(repo_root)).replace("\\", "/")
        audit.log_file_change("delete_directory", rel, _repo(), bytes_written=None)
        return {
            "success": True,
            "deleted_directory": rel,
            "deleted_count": len(manifest),
            **checkpoint,
        }
    except PolicyViolation as pv:
        audit.log_permission_denied("delete_directory", "fs_delete_directory", policy_engine.profile.value)
        return {"error": f"Permission denied: {pv}"}
    except SecurityError as se:
        return {"error": f"Security Violation: {se}"}
    except Exception as e:
        try:
            _rollback_checkpoint(checkpoint)
        except Exception as rollback_error:
            return {"error": f"{e}; automatic rollback also failed: {rollback_error}"}
        return {"error": str(e)}


def move_file(src: str, dst: str, overwrite: bool = False) -> Dict[str, Any]:
    """
    Move or rename a file or directory within the active repository.
    Both source and destination must remain within the active repository boundary.
    """
    checkpoints: List[Dict[str, str]] = []
    try:
        policy_engine.require_fs_move()
        src_resolved = security_engine.sanitize_and_resolve_path(src)
        dst_resolved = security_engine.sanitize_and_resolve_path(dst)

        if not src_resolved.exists():
            return {"error": f"Source '{src}' does not exist."}
        if dst_resolved.exists() and not overwrite:
            return {"error": f"Destination '{dst}' already exists. Set overwrite=True to replace."}

        checkpoints = [_checkpoint_before(src_resolved, "move_source"),
                       _checkpoint_before(dst_resolved, "move_destination")]
        _fire_mutation_hook("before_file_edit", src_resolved, "move")
        _fire_mutation_hook("before_file_edit", dst_resolved, "move")
        dst_resolved.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_resolved), str(dst_resolved))
        _fire_mutation_hook("after_file_edit", dst_resolved, "move")

        dst_rel = str(dst_resolved.relative_to(session_manager.get_active_repo_path())).replace("\\", "/")
        audit.log_file_change("move", f"{src} -> {dst_rel}", _repo())
        return {"success": True, "source": src, "destination": dst_rel, "checkpoints": checkpoints}
    except PolicyViolation as pv:
        audit.log_permission_denied("move_file", "fs_move_rename", policy_engine.profile.value)
        return {"error": f"Permission denied: {pv}"}
    except SecurityError as se:
        return {"error": f"Security Violation: {se}"}
    except Exception as e:
        try:
            _rollback_checkpoints(checkpoints)
        except Exception as rollback_error:
            return {"error": f"{e}; automatic rollback also failed: {rollback_error}"}
        return {"error": str(e)}


def copy_file(src: str, dst: str, overwrite: bool = False) -> Dict[str, Any]:
    """
    Copy a file within the active repository.
    Source and destination must both remain within the active repository.
    """
    checkpoint = None
    try:
        policy_engine.require_fs_copy()
        src_resolved = security_engine.sanitize_and_resolve_path(src)
        dst_resolved = security_engine.sanitize_and_resolve_path(dst)

        if not src_resolved.is_file():
            return {"error": f"Source '{src}' is not a file or does not exist."}
        if dst_resolved.exists() and not overwrite:
            return {"error": f"Destination '{dst}' already exists. Set overwrite=True to replace."}

        checkpoint = _checkpoint_before(dst_resolved, "copy_destination")
        _fire_mutation_hook("before_file_edit", dst_resolved, "copy")
        dst_resolved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src_resolved), str(dst_resolved))
        _fire_mutation_hook("after_file_edit", dst_resolved, "copy")

        dst_rel = str(dst_resolved.relative_to(session_manager.get_active_repo_path())).replace("\\", "/")
        audit.log_file_change("copy", dst_rel, _repo())
        return {"success": True, "source": src, "destination": dst_rel, "size_bytes": dst_resolved.stat().st_size, **checkpoint}
    except PolicyViolation as pv:
        return {"error": f"Permission denied: {pv}"}
    except SecurityError as se:
        return {"error": f"Security Violation: {se}"}
    except Exception as e:
        try:
            _rollback_checkpoint(checkpoint)
        except Exception as rollback_error:
            return {"error": f"{e}; automatic rollback also failed: {rollback_error}"}
        return {"error": str(e)}


def backup_file(path: str) -> Dict[str, Any]:
    """
    Create a timestamped backup copy of a file before editing it.
    Backups are stored alongside the original with a .bak.{timestamp} suffix.
    Call restore_file to revert to the backup.
    """
    try:
        resolved = security_engine.sanitize_and_resolve_path(path)
        if not resolved.is_file():
            return {"error": f"'{path}' is not a file or does not exist."}

        ts = int(time.time())
        backup_path = resolved.with_suffix(f"{resolved.suffix}.bak.{ts}")
        shutil.copy2(str(resolved), str(backup_path))

        backup_rel = str(backup_path.relative_to(session_manager.get_active_repo_path())).replace("\\", "/")
        audit.log_file_change("backup", backup_rel, _repo())
        return {
            "success": True,
            "original": _rel(resolved),
            "backup": backup_rel,
            "timestamp": ts,
        }
    except SecurityError as se:
        return {"error": f"Security Violation: {se}"}
    except Exception as e:
        return {"error": str(e)}


def restore_file(backup_path: str) -> Dict[str, Any]:
    """
    Restore a file from a backup created by backup_file.
    Overwrites the current version with the backup content.
    The backup file is preserved after restoration.
    """
    checkpoint = None
    try:
        policy_engine.require_fs_write()
        bk_resolved = security_engine.sanitize_and_resolve_path(backup_path)
        if not bk_resolved.is_file():
            return {"error": f"Backup file '{backup_path}' not found."}

        # Strip .bak.{timestamp} to get the original path
        name = bk_resolved.name
        parts = name.rsplit(".bak.", 1)
        if len(parts) != 2:
            return {"error": f"'{backup_path}' does not look like an MCP backup file (.bak.timestamp suffix expected)."}

        original_name = parts[0]
        original_path = bk_resolved.parent / original_name

        # Security: the restored path must also be in the repo
        original_path = security_engine.verify_path_in_root(str(original_path), session_manager.get_active_repo_path())

        checkpoint = _checkpoint_before(original_path, "restore_file")
        _fire_mutation_hook("before_file_edit", original_path, "restore")
        shutil.copy2(str(bk_resolved), str(original_path))
        _fire_mutation_hook("after_file_edit", original_path, "restore")
        rel = str(original_path.relative_to(session_manager.get_active_repo_path())).replace("\\", "/")
        audit.log_file_change("restore", rel, _repo())
        return {"success": True, "restored_to": rel, "backup_source": backup_path, **checkpoint}
    except PolicyViolation as pv:
        return {"error": f"Permission denied: {pv}"}
    except SecurityError as se:
        return {"error": f"Security Violation: {se}"}
    except Exception as e:
        try:
            _rollback_checkpoint(checkpoint)
        except Exception as rollback_error:
            return {"error": f"{e}; automatic rollback also failed: {rollback_error}"}
        return {"error": str(e)}


def diff_preview(path: str, new_content: str) -> Dict[str, Any]:
    """
    Preview a unified diff showing what write_file would change for a given file
    without actually writing anything to disk.
    """
    try:
        resolved = security_engine.sanitize_and_resolve_path(path)
        if not resolved.is_file():
            return {"error": f"'{path}' does not exist. Use write_file to create it."}

        original = resolved.read_text(encoding="utf-8", errors="replace")
        diff_lines = list(difflib.unified_diff(
            original.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{_rel(resolved)}",
            tofile=f"b/{_rel(resolved)}",
            lineterm="",
        ))
        return {
            "file": _rel(resolved),
            "has_changes": len(diff_lines) > 0,
            "diff": "".join(diff_lines),
            "lines_changed": sum(1 for line in diff_lines if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))),
        }
    except SecurityError as se:
        return {"error": f"Security Violation: {se}"}
    except Exception as e:
        return {"error": str(e)}
