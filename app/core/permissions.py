"""
Centralized Permission and Policy Engine
=========================================
All tool-level authorization is enforced here. Individual tools must call
this engine rather than implementing their own access rules.

Profiles
--------
safe        — read/search/edit + approved tests. No deletes, no git writes.
full        — all file ops, directory delete, approved git writes, dep install.
unrestricted — arbitrary local dev commands, broad fs ops, destructive git.
              Opt-in only. Never active for unauthenticated remote requests.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import FrozenSet, Optional, Set

from app.config import settings

logger = logging.getLogger("mcp_server.permissions")


# ---------------------------------------------------------------------------
# Profile definitions
# ---------------------------------------------------------------------------

class PermissionProfile(str, Enum):
    SAFE = "safe"
    FULL = "full"
    TRUSTED_ADMIN = "trusted_admin"
    UNRESTRICTED = "unrestricted"


@dataclass(frozen=True)
class PolicyRules:
    """Immutable set of capability flags for one profile."""
    # Filesystem
    fs_read: bool = True
    fs_write: bool = False
    fs_delete_file: bool = False
    fs_delete_directory: bool = False          # recursive rmdir
    fs_move_rename: bool = False
    fs_copy: bool = False
    fs_outside_repo: bool = False              # ops outside any registered repo

    # Commands
    cmd_execute: bool = False
    cmd_install_deps: bool = False
    cmd_arbitrary: bool = False                # no allowlist enforcement
    cmd_timeout_seconds: int = 120

    # Git
    git_read: bool = True
    git_stage: bool = False
    git_commit: bool = False
    git_push: bool = False
    git_reset_hard: bool = False
    git_clean: bool = False
    git_branch_create: bool = False
    git_worktree: bool = False

    # Network / remote
    network_access: bool = False

    # Audit / confirmation
    require_confirmation: bool = False
    audit_every_op: bool = True

    # Allowed command binaries (empty = use global config)
    allowed_binaries: FrozenSet[str] = field(default_factory=frozenset)


_SAFE_BINARIES: FrozenSet[str] = frozenset({
    "python", "python3", "pytest", "pip",
    "npm", "node", "npx",
    "git",
    "ruff", "mypy", "flake8", "black", "isort", "pylint",
    "dir", "echo", "where", "cat", "findstr",
    "powershell", "pwsh",
})

_FULL_BINARIES: FrozenSet[str] = _SAFE_BINARIES | frozenset({
    "pip", "uv", "poetry",
    "yarn", "pnpm",
    "cargo", "go",
    "java", "mvn", "gradle",
    "make", "cmake",
    "docker", "kubectl",
    "curl", "wget",
    "ls", "cp", "mv", "rm", "mkdir", "rmdir",
    "grep", "sed", "awk", "find",
    "pytest", "jest", "mocha", "vitest",
})

_TRUSTED_ADMIN_BINARIES: FrozenSet[str] = _FULL_BINARIES | frozenset({
    "gh", "git-lfs", "ssh", "tar", "zip", "unzip", "gzip", "jq", "terraform", "helm",
})

PROFILES: dict[PermissionProfile, PolicyRules] = {
    PermissionProfile.SAFE: PolicyRules(
        fs_read=True,
        fs_write=True,
        fs_delete_file=False,
        fs_delete_directory=False,
        fs_move_rename=False,
        fs_copy=True,
        cmd_execute=True,
        cmd_install_deps=False,
        cmd_arbitrary=False,
        cmd_timeout_seconds=120,
        git_read=True,
        git_stage=False,
        git_commit=False,
        git_branch_create=False,
        network_access=False,
        require_confirmation=False,
        allowed_binaries=_SAFE_BINARIES,
    ),
    PermissionProfile.FULL: PolicyRules(
        fs_read=True,
        fs_write=True,
        fs_delete_file=True,
        fs_delete_directory=True,
        fs_move_rename=True,
        fs_copy=True,
        cmd_execute=True,
        cmd_install_deps=True,
        cmd_arbitrary=False,
        cmd_timeout_seconds=300,
        git_read=True,
        git_stage=True,
        git_commit=True,
        git_push=False,                        # push is opt-in for admin
        git_reset_hard=False,
        git_clean=True,
        git_branch_create=True,
        git_worktree=True,
        network_access=True,                   # full mode allows dependency downloads
        require_confirmation=False,
        allowed_binaries=_FULL_BINARIES,
    ),
    PermissionProfile.TRUSTED_ADMIN: PolicyRules(
        fs_read=True,
        fs_write=True,
        fs_delete_file=True,
        fs_delete_directory=True,
        fs_move_rename=True,
        fs_copy=True,
        fs_outside_repo=False,                 # Still strictly confined to workspace paths
        cmd_execute=True,
        cmd_install_deps=True,
        cmd_arbitrary=False,                   # Governed allowlist
        cmd_timeout_seconds=600,               # Generous 10-minute timeout for builds/deployments
        git_read=True,
        git_stage=True,
        git_commit=True,
        git_push=True,                         # Push authorized for trusted admin
        git_reset_hard=False,                  # Guard against accidental destructive reset
        git_clean=True,
        git_branch_create=True,
        git_worktree=True,
        network_access=True,                   # Full network authorization
        require_confirmation=False,
        allowed_binaries=_TRUSTED_ADMIN_BINARIES,
    ),
    PermissionProfile.UNRESTRICTED: PolicyRules(
        fs_read=True,
        fs_write=True,
        fs_delete_file=True,
        fs_delete_directory=True,
        fs_move_rename=True,
        fs_copy=True,
        fs_outside_repo=True,
        cmd_execute=True,
        cmd_install_deps=True,
        cmd_arbitrary=True,
        cmd_timeout_seconds=600,
        git_read=True,
        git_stage=True,
        git_commit=True,
        git_push=True,
        git_reset_hard=True,
        git_clean=True,
        git_branch_create=True,
        git_worktree=True,
        network_access=True,
        require_confirmation=False,
        audit_every_op=True,
        allowed_binaries=frozenset(),          # no allowlist — arbitrary
    ),
}


# ---------------------------------------------------------------------------
# Policy Engine
# ---------------------------------------------------------------------------

class PolicyViolation(Exception):
    """Raised when an operation is denied by the active policy profile."""
    pass


class PolicyEngine:
    """
    The single source of truth for all permission decisions.

    Usage
    -----
    Call policy_engine.require(capability, context) from any tool.
    If denied, PolicyViolation is raised with a clear message.
    """

    def __init__(self) -> None:
        profile_name = os.environ.get("MCP_PERMISSION_PROFILE", "full").lower()
        try:
            self._profile = PermissionProfile(profile_name)
        except ValueError:
            logger.warning("Unknown MCP_PERMISSION_PROFILE '%s'; defaulting to 'full'", profile_name)
            self._profile = PermissionProfile.FULL

        self._rules = PROFILES[self._profile]

        if self._profile == PermissionProfile.UNRESTRICTED:
            logger.warning(
                "=== UNRESTRICTED LOCAL DEV MODE ACTIVE ==="
                " Arbitrary commands and broad filesystem operations are permitted."
                " Never use this profile with public network access. ==="
            )
        else:
            logger.info("Permission profile active: %s", self._profile.value)

    # ------------------------------------------------------------------ #
    # Profile access                                                       #
    # ------------------------------------------------------------------ #

    @property
    def profile(self) -> PermissionProfile:
        return self._profile

    @property
    def rules(self) -> PolicyRules:
        return self._rules

    def set_profile(self, profile: PermissionProfile) -> None:
        """Runtime profile switch. Logs the change."""
        old = self._profile
        self._profile = profile
        self._rules = PROFILES[profile]
        logger.warning("Permission profile changed: %s → %s", old.value, profile.value)
        if profile == PermissionProfile.UNRESTRICTED:
            logger.warning(
                "UNRESTRICTED mode active — arbitrary commands permitted locally."
            )

    # ------------------------------------------------------------------ #
    # Capability checks                                                    #
    # ------------------------------------------------------------------ #

    def _deny(self, capability: str, hint: str = "") -> None:
        msg = (
            f"Operation denied by '{self._profile.value}' permission profile: {capability}."
            + (f" {hint}" if hint else "")
            + f" To enable, set MCP_PERMISSION_PROFILE=full, trusted_admin, or unrestricted."
        )
        logger.warning("POLICY DENIED [%s]: %s", self._profile.value, capability)
        raise PolicyViolation(msg)

    def require_network(self, operation: str = "network access") -> None:
        if not self._rules.network_access:
            self._deny(operation, f"Profile '{self._profile.value}' does not allow network operations.")

    def require_fs_write(self) -> None:
        if not self._rules.fs_write:
            self._deny("filesystem write")

    def require_fs_delete_file(self) -> None:
        if not self._rules.fs_delete_file:
            self._deny("file deletion", "Profile 'safe' does not permit file deletion.")

    def require_fs_delete_directory(self) -> None:
        if not self._rules.fs_delete_directory:
            self._deny("recursive directory deletion", "Profile 'safe' does not permit directory deletion.")

    def require_fs_move(self) -> None:
        if not self._rules.fs_move_rename:
            self._deny("file move/rename")

    def require_fs_copy(self) -> None:
        if not self._rules.fs_copy:
            self._deny("file copy")

    def require_cmd_execute(self) -> None:
        if not self._rules.cmd_execute:
            self._deny("command execution")

    def require_cmd_install(self) -> None:
        if not self._rules.cmd_install_deps:
            self._deny("dependency installation")
        self.require_network("dependency installation")

    def require_git_stage(self) -> None:
        if not self._rules.git_stage:
            self._deny("git staging (add)")

    def require_git_commit(self) -> None:
        if not self._rules.git_commit:
            self._deny("git commit")

    def require_git_push(self) -> None:
        if not self._rules.git_push:
            self._deny("git push", "Push is disabled by default in safe and full profiles. Use 'trusted_admin' or 'unrestricted'.")
        self.require_network("git push")

    def require_git_fetch(self) -> None:
        self.require_network("git fetch")

    def require_git_pull(self) -> None:
        if not self._rules.git_stage:
            self._deny("git pull", "Profile does not permit modifying workspace working tree.")
        self.require_network("git pull")

    def require_git_reset_hard(self) -> None:
        if not self._rules.git_reset_hard:
            self._deny("git reset --hard")

    def require_git_branch_create(self) -> None:
        if not self._rules.git_branch_create:
            self._deny("git branch creation")

    def require_git_worktree(self) -> None:
        if not self._rules.git_worktree:
            self._deny("git worktree")

    def require_git_clean(self) -> None:
        if not self._rules.git_clean:
            self._deny("git clean")

    def effective_allowed_binaries(self) -> Optional[Set[str]]:
        """Returns None when arbitrary commands are permitted (unrestricted)."""
        if self._rules.cmd_arbitrary:
            return None
        if self._rules.allowed_binaries:
            return set(self._rules.allowed_binaries)
        # Fall back to global config
        return set(settings.ALLOWED_COMMAND_BINARIES)

    def effective_timeout(self, requested: int) -> int:
        return min(requested, self._rules.cmd_timeout_seconds)

    def can_access_outside_repo(self) -> bool:
        return self._rules.fs_outside_repo

    # ------------------------------------------------------------------ #
    # Info helpers                                                         #
    # ------------------------------------------------------------------ #

    def describe(self) -> dict:
        r = self._rules
        return {
            "profile": self._profile.value,
            "fs_read": r.fs_read,
            "fs_write": r.fs_write,
            "fs_delete_file": r.fs_delete_file,
            "fs_delete_directory": r.fs_delete_directory,
            "fs_move_rename": r.fs_move_rename,
            "cmd_execute": r.cmd_execute,
            "cmd_install_deps": r.cmd_install_deps,
            "cmd_arbitrary": r.cmd_arbitrary,
            "cmd_timeout_seconds": r.cmd_timeout_seconds,
            "git_read": r.git_read,
            "git_stage": r.git_stage,
            "git_commit": r.git_commit,
            "git_push": r.git_push,
            "git_reset_hard": r.git_reset_hard,
            "git_branch_create": r.git_branch_create,
            "network_access": r.network_access,
        }


# Singleton — imported by all tools
policy_engine = PolicyEngine()
