import fnmatch
import logging
import shlex
from pathlib import Path
from typing import Tuple, List, Optional, Set
from app.config import settings
from app.core.session import session_manager

logger = logging.getLogger("mcp_server.security")

class SecurityError(Exception):
    """Raised when an operation violates filesystem sandboxing or execution policies."""
    pass

class SecurityEngine:
    """Centralized security validation for filesystem operations and shell commands."""

    def __init__(self):
        self.blocked_patterns: List[str] = settings.BLOCKED_PATTERNS
        self.allowed_binaries: Set[str] = settings.ALLOWED_COMMAND_BINARIES
        self.blocked_commands: List[str] = settings.BLOCKED_COMMANDS

    def sanitize_and_resolve_path(self, path: str, session_id: Optional[str] = None) -> Path:
        """
        Resolves, canonicalizes, and verifies that the given path is strictly within the active repository root.
        Rejects path traversal, external absolute paths, UNC network shares, symlink escapes, and secret files.
        """
        repo_root = session_manager.get_active_repo_path(session_id)
        return self.verify_path_in_root(path, repo_root)

    def verify_path_in_root(self, path: str, repo_root: Path) -> Path:
        """Verifies that a given path stays within a specific repository root."""
        clean_root = repo_root.resolve(strict=True)
        raw_path_str = str(path).strip()

        if not raw_path_str:
            raise SecurityError("Path cannot be empty.")

        # Block UNC network paths
        if raw_path_str.startswith(("\\\\", "//")):
            logger.warning(f"Rejected UNC path: {raw_path_str}")
            raise SecurityError("Access Denied: UNC network paths are strictly prohibited.")

        target = Path(raw_path_str)
        if not target.is_absolute():
            # Strip leading slashes to prevent root-resetting behavior
            rel_str = raw_path_str.lstrip("/\\")
            target = clean_root / rel_str

        try:
            resolved = target.resolve(strict=False)
        except Exception as e:
            raise SecurityError(f"Path resolution failure: {e}")

        # Enforce repository boundary containment
        try:
            resolved.relative_to(clean_root)
        except ValueError:
            logger.error(f"Path traversal detected: '{raw_path_str}' resolved to '{resolved}' outside '{clean_root}'")
            raise SecurityError(
                f"Access Denied: Path '{raw_path_str}' escapes active repository boundary ({clean_root.name})."
            )

        # Check for symlink escapes pointing outside root
        if resolved.is_symlink():
            symlink_target = resolved.resolve()
            try:
                symlink_target.relative_to(clean_root)
            except ValueError:
                logger.error(f"Symlink escape detected: '{resolved}' points to '{symlink_target}' outside '{clean_root}'")
                raise SecurityError(
                    f"Access Denied: Symlink '{resolved.name}' targets location outside repository boundary."
                )

        # Block access to secret and credential files
        filename = resolved.name.lower()
        rel_to_root = str(resolved.relative_to(clean_root)).replace("\\", "/").lower()

        for pattern in self.blocked_patterns:
            pat = pattern.lower()
            if fnmatch.fnmatch(filename, pat) or fnmatch.fnmatch(rel_to_root, pat):
                logger.warning(f"Blocked secret access to '{rel_to_root}' matching pattern '{pattern}'")
                raise SecurityError(f"Access Denied: Access to sensitive file or secret '{resolved.name}' is prohibited.")

        return resolved

    def validate_command_security(self, command: str) -> Tuple[str, List[str]]:
        """
        Validates a shell command string against the allowed binaries list and blocked command patterns.
        Returns the sanitized binary name and arguments list.
        """
        normalized_cmd = command.strip()
        if not normalized_cmd:
            raise SecurityError("Command string cannot be empty.")

        lower_cmd = normalized_cmd.lower()

        # Check blocked command substrings
        for blocked in self.blocked_commands:
            if blocked.lower() in lower_cmd:
                logger.warning(f"Blocked forbidden command pattern '{blocked}' in: '{command}'")
                raise SecurityError(f"Command execution blocked: '{blocked}' is strictly forbidden.")

        # Safe tokenization
        try:
            args = shlex.split(normalized_cmd, posix=(False if Path("/").resolve() != Path("/") else True))
        except Exception as e:
            raise SecurityError(f"Invalid command syntax: {e}")

        if not args:
            raise SecurityError("Command is empty.")

        raw_binary = args[0]
        binary_name = Path(raw_binary).name.lower()
        if binary_name.endswith(".exe"):
            binary_name = binary_name[:-4]

        if binary_name not in self.allowed_binaries:
            allowed_list = ", ".join(sorted(self.allowed_binaries))
            logger.warning(f"Unapproved binary '{binary_name}' rejected. Command: '{command}'")
            raise SecurityError(
                f"Binary '{binary_name}' is not permitted. Allowed binaries: [{allowed_list}]"
            )

        return binary_name, args

security_engine = SecurityEngine()
