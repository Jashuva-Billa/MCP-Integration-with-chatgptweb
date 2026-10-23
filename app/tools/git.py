"""
Git Tools — Read + Write
=========================
Read operations: status, diff, branch list, log, show, changed_files.
Write operations (policy-gated): stage, commit, create_branch,
                                  switch_branch, worktree_create,
                                  worktree_remove, git_reset, git_clean.

All write operations are audit-logged.
Push and destructive resets require the 'full' or 'unrestricted' profile.
"""

from __future__ import annotations

import json
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.audit import audit
from app.core.approvals import approval_manager
from app.core.permissions import PermissionProfile, PolicyViolation, policy_engine
from app.core.security import security_engine
from app.core.session import session_manager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_git(args: List[str], cwd: str, timeout: int = 30) -> Dict[str, Any]:
    res = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {"stdout": res.stdout, "stderr": res.stderr, "exit_code": res.returncode}


def _repo_root() -> Path:
    return session_manager.get_active_repo_path()


def _repo_name() -> str:
    return session_manager.get_active_repo_name() or ""


def _sanitize_ref(ref: str) -> str:
    """Allow only safe git ref characters."""
    return re.sub(r"[^A-Za-z0-9_./-]", "", ref)


# ---------------------------------------------------------------------------
# READ operations (unchanged semantics)
# ---------------------------------------------------------------------------

def git_status() -> Dict[str, Any]:
    """Inspect working tree status of the active repository (staged, unstaged, untracked files)."""
    try:
        r = _run_git(["status", "--short"], str(_repo_root()))
        return {"repository": _repo_name(), "status_output": r["stdout"], "stderr": r["stderr"], "exit_code": r["exit_code"]}
    except Exception as e:
        return {"error": str(e)}


def git_diff(file_path: Optional[str] = None, staged: bool = False) -> Dict[str, Any]:
    """
    View git diffs in the active repository.
    Pass staged=True to see what's staged for commit.
    """
    try:
        root = _repo_root()
        cmd = ["diff"]
        if staged:
            cmd.append("--staged")
        if file_path:
            resolved = security_engine.sanitize_and_resolve_path(file_path)
            cmd.append(str(resolved.relative_to(root)))
        r = _run_git(cmd, str(root), timeout=30)
        return {"repository": _repo_name(), "diff": r["stdout"], "exit_code": r["exit_code"]}
    except Exception as e:
        return {"error": str(e)}


def git_branch() -> Dict[str, Any]:
    """List active branch and all available local and remote branches."""
    try:
        r = _run_git(["branch", "-a", "--format=%(refname:short) %(HEAD)"], str(_repo_root()))
        return {"repository": _repo_name(), "branches": r["stdout"], "exit_code": r["exit_code"]}
    except Exception as e:
        return {"error": str(e)}


def git_log(max_commits: int = 20, oneline: bool = True) -> Dict[str, Any]:
    """View recent commit history in the active repository."""
    try:
        limit = min(max_commits, 100)
        fmt = ["--oneline"] if oneline else ["--format=%H %an %ae %aI %s"]
        r = _run_git(["log", f"-n{limit}"] + fmt, str(_repo_root()))
        return {"repository": _repo_name(), "log": r["stdout"], "exit_code": r["exit_code"]}
    except Exception as e:
        return {"error": str(e)}


def git_show(commit_hash: str = "HEAD") -> Dict[str, Any]:
    """Inspect the details and diff of a specific Git commit."""
    try:
        safe_hash = _sanitize_ref(commit_hash)
        r = _run_git(["show", "--stat", safe_hash], str(_repo_root()))
        return {"repository": _repo_name(), "commit": safe_hash, "details": r["stdout"], "exit_code": r["exit_code"]}
    except Exception as e:
        return {"error": str(e)}


def git_changed_files() -> Dict[str, Any]:
    """List names of all files modified, added, or deleted in the working tree."""
    try:
        r = _run_git(["status", "--porcelain"], str(_repo_root()))
        files = [line.strip()[3:] for line in r["stdout"].splitlines() if len(line.strip()) > 3]
        return {"repository": _repo_name(), "total_changed": len(files), "changed_files": files}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# WRITE operations (policy-gated)
# ---------------------------------------------------------------------------

def git_stage(paths: Optional[List[str]] = None, all_changes: bool = False) -> Dict[str, Any]:
    """
    Stage files for the next commit.
    Requires 'full' or 'unrestricted' profile.

    Parameters
    ----------
    paths : list[str], optional
        Specific file paths to stage. Relative to repo root.
    all_changes : bool
        If True, stages all changes (equivalent to git add -A).
    """
    try:
        policy_engine.require_git_stage()
        root = _repo_root()

        if all_changes:
            r = _run_git(["add", "-A"], str(root))
        elif paths:
            safe_paths: List[str] = []
            for p in paths:
                resolved = security_engine.sanitize_and_resolve_path(p)
                safe_paths.append(str(resolved.relative_to(root)))
            r = _run_git(["add"] + safe_paths, str(root))
        else:
            return {"error": "Provide paths to stage or set all_changes=True."}

        audit.log_git_op("stage", _repo_name())
        return {
            "repository": _repo_name(),
            "success": r["exit_code"] == 0,
            "stdout": r["stdout"],
            "stderr": r["stderr"],
            "exit_code": r["exit_code"],
        }
    except PolicyViolation as pv:
        audit.log_permission_denied("git_stage", "git_stage", policy_engine.profile.value)
        return {"error": f"Permission denied: {pv}"}
    except Exception as e:
        return {"error": str(e)}


def git_commit(message: str, author: Optional[str] = None) -> Dict[str, Any]:
    """
    Commit currently staged changes.
    Requires 'full' or 'unrestricted' profile.

    Parameters
    ----------
    message : str
        Commit message.
    author : str, optional
        Override author in "Name <email>" format.
    """
    try:
        policy_engine.require_git_commit()
        if not message.strip():
            return {"error": "Commit message cannot be empty."}

        root = _repo_root()
        cmd = ["commit", "-m", message]
        if author:
            cmd += ["--author", author]

        r = _run_git(cmd, str(root))
        audit.log_git_op("commit", _repo_name(), detail=message[:80])
        return {
            "repository": _repo_name(),
            "success": r["exit_code"] == 0,
            "stdout": r["stdout"],
            "stderr": r["stderr"],
            "exit_code": r["exit_code"],
        }
    except PolicyViolation as pv:
        audit.log_permission_denied("git_commit", "git_commit", policy_engine.profile.value)
        return {"error": f"Permission denied: {pv}"}
    except Exception as e:
        return {"error": str(e)}


def git_create_branch(branch_name: str, start_point: str = "HEAD") -> Dict[str, Any]:
    """
    Create a new Git branch.
    Requires 'full' or 'unrestricted' profile.
    """
    try:
        policy_engine.require_git_branch_create()
        safe_name = _sanitize_ref(branch_name)
        safe_start = _sanitize_ref(start_point)
        if not safe_name:
            return {"error": "Invalid branch name."}

        root = _repo_root()
        r = _run_git(["checkout", "-b", safe_name, safe_start], str(root))
        audit.log_git_op("create_branch", _repo_name(), detail=safe_name)
        return {
            "repository": _repo_name(),
            "branch": safe_name,
            "success": r["exit_code"] == 0,
            "stdout": r["stdout"],
            "stderr": r["stderr"],
        }
    except PolicyViolation as pv:
        return {"error": f"Permission denied: {pv}"}
    except Exception as e:
        return {"error": str(e)}


def git_switch_branch(branch_name: str) -> Dict[str, Any]:
    """Switch to an existing branch. Requires 'full' or 'unrestricted' profile."""
    try:
        policy_engine.require_git_branch_create()
        safe_name = _sanitize_ref(branch_name)
        root = _repo_root()
        r = _run_git(["checkout", safe_name], str(root))
        audit.log_git_op("switch_branch", _repo_name(), detail=safe_name)
        return {
            "repository": _repo_name(),
            "branch": safe_name,
            "success": r["exit_code"] == 0,
            "stdout": r["stdout"],
            "stderr": r["stderr"],
        }
    except PolicyViolation as pv:
        return {"error": f"Permission denied: {pv}"}
    except Exception as e:
        return {"error": str(e)}


def git_reset(mode: str = "soft", target: str = "HEAD~1") -> Dict[str, Any]:
    """
    Reset the HEAD pointer.
    'soft' preserves staged changes. 'mixed' unstages. 'hard' discards all changes.
    'hard' requires 'unrestricted' profile.
    """
    try:
        if mode == "hard":
            policy_engine.require_git_reset_hard()
        else:
            policy_engine.require_git_commit()  # reachable in full+

        safe_mode = mode if mode in {"soft", "mixed", "hard"} else "soft"
        safe_target = _sanitize_ref(target)
        root = _repo_root()
        rollback_branch = None
        checkpoint_task_id = None
        checkpoints: List[Dict[str, str]] = []
        if safe_mode == "hard":
            # Preserve the current commit and all locally modified tracked files before reset.
            current = _run_git(["rev-parse", "HEAD"], str(root))
            if current["exit_code"] != 0:
                return {"error": "Unable to resolve current HEAD; hard reset was not run."}
            rollback_branch = f"mcp-safety/reset-{uuid.uuid4().hex[:10]}"
            branch_result = _run_git(["branch", rollback_branch, current["stdout"].strip()], str(root))
            if branch_result["exit_code"] != 0:
                return {"error": f"Unable to create rollback branch; hard reset was not run: {branch_result['stderr']}"}
            changed = _run_git(["diff", "--name-only", "-z", "HEAD"], str(root))
            if changed["exit_code"] == 0 and changed["stdout"]:
                from app.core.orchestrator import checkpoint_store
                checkpoint_task_id = f"git-reset-{uuid.uuid4().hex[:10]}"
                for relative_path in changed["stdout"].split("\0"):
                    if relative_path:
                        manifest = checkpoint_store.create(checkpoint_task_id, relative_path, root)
                        checkpoints.append({"checkpoint_id": manifest["checkpoint_id"], "path": relative_path})
        r = _run_git(["reset", f"--{safe_mode}", safe_target], str(root))
        audit.log_git_op(f"reset_{safe_mode}", _repo_name(), detail=safe_target)
        return {
            "repository": _repo_name(),
            "mode": safe_mode,
            "target": safe_target,
            "success": r["exit_code"] == 0,
            "stdout": r["stdout"],
            "stderr": r["stderr"],
            "rollback_branch": rollback_branch,
            "checkpoint_task_id": checkpoint_task_id,
            "checkpoints": checkpoints,
        }
    except PolicyViolation as pv:
        return {"error": f"Permission denied: {pv}"}
    except Exception as e:
        return {"error": str(e)}


def git_worktree_add(path: str, branch: str) -> Dict[str, Any]:
    """
    Create a new Git worktree at the given path, checked out to the specified branch.
    Requires 'full' or 'unrestricted' profile. Path must remain within the repo root.
    """
    try:
        policy_engine.require_git_worktree()
        resolved = security_engine.sanitize_and_resolve_path(path)
        safe_branch = _sanitize_ref(branch)
        root = _repo_root()
        r = _run_git(["worktree", "add", str(resolved), safe_branch], str(root))
        audit.log_git_op("worktree_add", _repo_name(), detail=f"{path}@{safe_branch}")
        return {
            "repository": _repo_name(),
            "worktree_path": str(resolved),
            "branch": safe_branch,
            "success": r["exit_code"] == 0,
            "stdout": r["stdout"],
            "stderr": r["stderr"],
        }
    except PolicyViolation as pv:
        return {"error": f"Permission denied: {pv}"}
    except Exception as e:
        return {"error": str(e)}


def git_worktree_remove(path: str) -> Dict[str, Any]:
    """Remove a Git worktree. Requires 'full' or 'unrestricted' profile."""
    try:
        policy_engine.require_git_worktree()
        resolved = security_engine.sanitize_and_resolve_path(path)
        root = _repo_root()
        r = _run_git(["worktree", "remove", str(resolved)], str(root))
        audit.log_git_op("worktree_remove", _repo_name(), detail=path)
        return {"success": r["exit_code"] == 0, "stdout": r["stdout"], "stderr": r["stderr"]}
    except PolicyViolation as pv:
        return {"error": f"Permission denied: {pv}"}
    except Exception as e:
        return {"error": str(e)}


def git_push(
    remote: str = "origin",
    branch: Optional[str] = None,
    force: bool = False,
    set_upstream: bool = False,
    timeout: int = 60,
    approval_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Push only when explicitly enabled and authorized; verify the remote ref afterward.

    When MCP_GIT_PUSH_REQUIRE_APPROVAL=true, approval_id must reference an approved,
    unexpired request for the exact `git_push` operation and `remote/branch` target.
    """
    try:
        policy_engine.require_git_push()
        safe_remote = _sanitize_ref(remote) or "origin"
        if safe_remote != remote.strip():
            return {"error": "Remote contains unsupported characters."}
        root = _repo_root()
        if branch is None:
            current = _run_git(["branch", "--show-current"], str(root))
            if current["exit_code"] != 0 or not current["stdout"].strip():
                return {"error": "Could not determine the current branch; specify branch explicitly."}
            safe_branch = current["stdout"].strip()
        else:
            safe_branch = _sanitize_ref(branch)
            if (not safe_branch or safe_branch != branch.strip() or ".." in safe_branch
                    or safe_branch.startswith("-") or safe_branch.endswith("/") or "//" in safe_branch):
                return {"error": "Branch contains unsupported Git ref characters."}
        target = f"{safe_remote}/{safe_branch}"
        if settings.MCP_GIT_PUSH_REQUIRE_APPROVAL and not approval_manager.is_approved(
            approval_id, "git_push", target
        ):
            audit.log_tool("git_push", {"remote": safe_remote, "branch": safe_branch}, success=False,
                           error="Matching approved request required", repository=_repo_name(),
                           profile=policy_engine.profile.value)
            return {"error": f"An approved, unexpired request for git_push target '{target}' is required.",
                    "approval_required": True, "approval_target": target}

        args = ["push"]
        if set_upstream:
            args.append("-u")
        if force:
            if policy_engine.profile != PermissionProfile.UNRESTRICTED:
                return {"error": "Force push is only allowed in 'unrestricted' profile."}
            args.append("--force-with-lease")
        args.extend([safe_remote, f"HEAD:refs/heads/{safe_branch}"])
        pushed = _run_git(args, str(root), timeout=timeout)
        if pushed["exit_code"] != 0:
            audit.log_git_op("push_failed", _repo_name(), detail=f"{target} exit={pushed['exit_code']}")
            return {"repository": _repo_name(), "remote": safe_remote, "branch": safe_branch,
                    "success": False, "exit_code": pushed["exit_code"],
                    "stdout": pushed["stdout"], "stderr": pushed["stderr"],
                    "remote_verified": False}

        local = _run_git(["rev-parse", "HEAD"], str(root))
        remote_state = _run_git(["ls-remote", safe_remote, f"refs/heads/{safe_branch}"], str(root), timeout=timeout)
        local_sha = local["stdout"].strip()
        remote_sha = remote_state["stdout"].split()[0] if remote_state["stdout"].split() else ""
        verified = (local["exit_code"] == 0 and remote_state["exit_code"] == 0
                    and bool(local_sha) and local_sha == remote_sha)
        audit.log_git_op("push_verified" if verified else "push_verification_failed", _repo_name(),
                         detail=f"{target} force={force} verified={verified}")
        return {
            "repository": _repo_name(), "remote": safe_remote, "branch": safe_branch,
            "success": verified, "push_exit_code": pushed["exit_code"],
            "stdout": pushed["stdout"], "stderr": pushed["stderr"],
            "remote_verified": verified, "local_sha": local_sha or None,
            "remote_sha": remote_sha or None,
            "verification_error": None if verified else "Push command succeeded, but remote HEAD could not be confirmed to match local HEAD.",
        }
    except PolicyViolation as pv:
        audit.log_permission_denied("git_push", "git_push", policy_engine.profile.value)
        return {"error": f"Permission denied: {pv}"}
    except subprocess.TimeoutExpired:
        audit.log_git_op("push_timeout", _repo_name(), detail="git push or remote verification timed out")
        return {"error": f"git push or verification timed out after {timeout}s"}
    except Exception as e:
        audit.log_tool("git_push", {"remote": remote, "branch": branch}, success=False,
                       error=str(e), repository=_repo_name(), profile=policy_engine.profile.value)
        return {"error": str(e)}


def git_fetch(
    remote: str = "origin",
    prune: bool = False,
    timeout: int = 60,
) -> Dict[str, Any]:
    """
    Fetch refs and objects from a remote Git repository.
    Requires network authorization.
    """
    try:
        policy_engine.require_git_fetch()
        safe_remote = _sanitize_ref(remote) or "origin"
        args = ["fetch", safe_remote]
        if prune:
            args.append("--prune")

        root = _repo_root()
        r = _run_git(args, str(root), timeout=timeout)
        audit.log_git_op("fetch", _repo_name(), detail=safe_remote)
        return {
            "repository": _repo_name(),
            "remote": safe_remote,
            "success": r["exit_code"] == 0,
            "exit_code": r["exit_code"],
            "stdout": r["stdout"],
            "stderr": r["stderr"],
        }
    except PolicyViolation as pv:
        return {"error": f"Permission denied: {pv}"}
    except subprocess.TimeoutExpired:
        return {"error": f"git fetch timed out after {timeout}s"}
    except Exception as e:
        return {"error": str(e)}


def git_pull(
    remote: str = "origin",
    branch: Optional[str] = None,
    rebase: bool = False,
    timeout: int = 60,
) -> Dict[str, Any]:
    """
    Fetch from and integrate with another repository or local branch.
    Requires network access and working-tree modification permissions.
    """
    try:
        policy_engine.require_git_pull()
        safe_remote = _sanitize_ref(remote) or "origin"
        args = ["pull"]
        if rebase:
            args.append("--rebase")
        args.append(safe_remote)
        if branch:
            args.append(_sanitize_ref(branch))

        root = _repo_root()
        r = _run_git(args, str(root), timeout=timeout)
        audit.log_git_op("pull", _repo_name(), detail=f"{safe_remote} {branch or 'current'} rebase={rebase}")
        return {
            "repository": _repo_name(),
            "remote": safe_remote,
            "branch": branch or "current",
            "success": r["exit_code"] == 0,
            "exit_code": r["exit_code"],
            "stdout": r["stdout"],
            "stderr": r["stderr"],
        }
    except PolicyViolation as pv:
        return {"error": f"Permission denied: {pv}"}
    except subprocess.TimeoutExpired:
        return {"error": f"git pull timed out after {timeout}s"}
    except Exception as e:
        return {"error": str(e)}


def rollback_git_reset_checkpoint(
    rollback_branch: str,
    checkpoint_task_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Restore a hard-reset safety branch and any snapshotted uncommitted tracked files."""
    try:
        policy_engine.require_git_branch_create()
        safe_branch = _sanitize_ref(rollback_branch)
        if not safe_branch.startswith("mcp-safety/reset-"):
            return {"error": "Rollback is restricted to MCP safety branches created by git_reset."}
        if checkpoint_task_id and not checkpoint_task_id.startswith("git-reset-"):
            return {"error": "Invalid Git reset checkpoint identifier."}

        root = _repo_root()
        switched = _run_git(["checkout", safe_branch], str(root))
        if switched["exit_code"] != 0:
            return {"success": False, "error": switched["stderr"], "rollback_branch": safe_branch}

        restored = []
        if checkpoint_task_id:
            from app.core.orchestrator import checkpoint_store
            for manifest_path in sorted((checkpoint_store.root / checkpoint_task_id).glob("*/manifest.json")):
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                result = checkpoint_store.rollback(manifest["checkpoint_id"], checkpoint_task_id, root)
                restored.append(result["restored_path"])

        audit.log_git_op("rollback_hard_reset", _repo_name(), detail=safe_branch)
        return {"success": True, "rollback_branch": safe_branch, "restored_files": restored}
    except PolicyViolation as pv:
        return {"error": f"Permission denied: {pv}"}
    except Exception as exc:
        return {"error": str(exc)}
