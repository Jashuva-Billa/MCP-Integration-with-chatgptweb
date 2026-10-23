"""Secure, allowlisted GitHub cloning for hosted MCP workspaces.

Only repositories explicitly listed in MCP_GITHUB_ALLOWED_REPOS can be cloned.
The optional MCP_GITHUB_TOKEN is used for authentication without embedding
credentials in clone URLs or logs.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.config import settings
from app.core.repository import repository_manager

_REPO_SLUG = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


class GitHubWorkspaceError(ValueError):
    """Raised when a requested remote workspace fails validation or cloning."""


def _allowed_repositories() -> set[str]:
    raw = getattr(settings, "MCP_GITHUB_ALLOWED_REPOS", "")
    return {item.strip().lower().removesuffix(".git") for item in raw.split(",") if item.strip()}


def _workspace_root() -> Path:
    raw = getattr(settings, "MCP_WORKSPACE_ROOT", "/tmp/mcp-workspaces")
    root = Path(raw).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def normalize_github_url(repository_url: str) -> str:
    """Return canonical HTTPS URL after rejecting non-GitHub and malformed URLs."""
    parsed = urlparse((repository_url or "").strip())
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise GitHubWorkspaceError("Only https://github.com/OWNER/REPOSITORY URLs are accepted.")
    if parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment:
        raise GitHubWorkspaceError("Repository URL must not contain credentials, a port, query, or fragment.")
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) != 2:
        raise GitHubWorkspaceError("Provide a repository URL with exactly an owner and repository name.")
    if any(part in {".", ".."} for part in parts):
        raise GitHubWorkspaceError("Repository URL contains an invalid owner or repository segment.")
    slug = "/".join(parts).removesuffix(".git")
    owner, repository = slug.split("/", 1)
    if owner in {".", ".."} or repository in {".", ".."} or not _REPO_SLUG.fullmatch(slug):
        raise GitHubWorkspaceError("Repository URL contains invalid owner or repository characters.")
    if slug.lower() not in _allowed_repositories():
        raise GitHubWorkspaceError(
            "Repository is not in MCP_GITHUB_ALLOWED_REPOS. Add its OWNER/REPOSITORY slug in host settings first."
        )
    return f"https://github.com/{slug}.git"


def clone_github_repository(
    repository_url: str,
    workspace_name: str,
    branch: str = "",
    description: str = "",
) -> dict[str, Any]:
    """Clone an allowlisted GitHub repository into the configured workspace root and register it."""
    workspace_name = (workspace_name or "").strip()
    if not _NAME.fullmatch(workspace_name):
        raise GitHubWorkspaceError("workspace_name must be 1-64 safe letters, digits, dots, underscores, or hyphens.")
    clone_url = normalize_github_url(repository_url)
    root = _workspace_root()
    destination = (root / workspace_name).resolve()
    if destination.parent != root:
        raise GitHubWorkspaceError("Workspace destination escapes the configured workspace root.")
    if destination.exists() or destination.is_symlink():
        raise GitHubWorkspaceError(f"Workspace '{workspace_name}' already exists; refusing to overwrite it.")
    if repository_manager.get_repository(workspace_name) is not None:
        raise GitHubWorkspaceError(f"A repository named '{workspace_name}' is already registered.")

    cmd = ["git", "clone", "--single-branch"]
    if branch:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}", branch) or ".." in branch or branch.endswith("/"):
            raise GitHubWorkspaceError("Branch name contains unsupported characters.")
        cmd.extend(["--branch", branch])
    cmd.extend([clone_url, str(destination)])

    env = os.environ.copy()
    token = getattr(settings, "MCP_GITHUB_TOKEN", "").strip()
    # Use Git's one-shot credential header, never place the token in the URL/arguments.
    if token:
        import base64
        authorization = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env["GIT_CONFIG_COUNT"] = "1"
        env["GIT_CONFIG_KEY_0"] = "http.https://github.com/.extraheader"
        env["GIT_CONFIG_VALUE_0"] = f"AUTHORIZATION: basic {authorization}"
    try:
        result = subprocess.run(
            cmd,
            cwd=str(root),
            env=env,
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitHubWorkspaceError("Git clone timed out; no repository was registered.") from exc
    if result.returncode != 0:
        # Git output can contain remote-provided details; don't return full stdout/stderr or tokens.
        if destination.exists():
            import shutil
            shutil.rmtree(destination, ignore_errors=True)
        raise GitHubWorkspaceError("Git clone failed. Verify repository access, branch, and host network settings.")

    try:
        registered = repository_manager.add_repository(
            workspace_name, str(destination), description or f"GitHub workspace {clone_url}", True
        )
    except Exception:
        import shutil
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return {
        "success": True,
        "repository": registered,
        "branch": branch or "default",
        "message": "Repository cloned and registered. Use select_repository to work in this workspace.",
    }
