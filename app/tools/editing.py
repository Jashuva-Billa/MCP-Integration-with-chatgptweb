"""Precise, diff-friendly editing primitives for local coding-agent workflows."""

import os
import stat
import tempfile
from pathlib import Path
from typing import Any, Dict

from app.config import settings
from app.core.security import SecurityError, security_engine
from app.core.session import session_manager


def replace_in_file(
    path: str,
    old_text: str,
    new_text: str,
    expected_occurrences: int = 1,
) -> Dict[str, Any]:
    """Replace an exact text block only when its occurrence count matches expectations.

    This is intentionally context-sensitive: it avoids silently changing the wrong
    location when source code has drifted. Files are replaced atomically.
    """
    try:
        if not old_text:
            return {"error": "old_text cannot be empty."}
        if expected_occurrences < 1:
            return {"error": "expected_occurrences must be at least 1."}

        resolved = security_engine.sanitize_and_resolve_path(path)
        if not resolved.is_file():
            return {"error": f"File '{path}' does not exist or is not a regular file."}
        original_stat = resolved.stat()
        if original_stat.st_size > settings.MAX_FILE_SIZE_BYTES:
            return {"error": f"File exceeds maximum edit size limit of {settings.MAX_FILE_SIZE_BYTES} bytes."}

        try:
            original = resolved.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            return {"error": "Only UTF-8 text files can be edited with replace_in_file; file was left unchanged."}

        actual_occurrences = original.count(old_text)
        if actual_occurrences != expected_occurrences:
            return {
                "error": "Exact replacement aborted because the matching text count differed.",
                "file_path": str(resolved.relative_to(session_manager.get_active_repo_path())).replace("\\", "/"),
                "expected_occurrences": expected_occurrences,
                "actual_occurrences": actual_occurrences,
                "unchanged": True,
            }

        updated = original.replace(old_text, new_text, expected_occurrences)
        encoded = updated.encode("utf-8")
        if len(encoded) > settings.MAX_FILE_SIZE_BYTES:
            return {"error": f"Updated content exceeds maximum file size limit of {settings.MAX_FILE_SIZE_BYTES} bytes."}

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=str(resolved.parent),
                prefix=".mcp-edit-",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(encoded)
                temp_file.flush()
                os.fsync(temp_file.fileno())

            os.chmod(temp_path, stat.S_IMODE(original_stat.st_mode))
            os.replace(temp_path, resolved)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()

        return {
            "success": True,
            "file_path": str(resolved.relative_to(session_manager.get_active_repo_path())).replace("\\", "/"),
            "replacements": expected_occurrences,
            "bytes_written": len(encoded),
            "atomic_write": True,
        }
    except SecurityError as exc:
        return {"error": f"Security Violation: {exc}"}
    except Exception as exc:
        return {"error": f"Edit failed: {type(exc).__name__}: {exc}"}
