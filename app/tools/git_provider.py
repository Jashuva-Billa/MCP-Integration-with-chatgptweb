"""Read-only Git hosting / CI/CD intelligence for GitHub.

Uses the GitHub REST API via stdlib urllib; tokens are read only from environment
settings and are never returned. No mutation endpoints are exposed here.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from app.core.permissions import policy_engine

_API = "https://api.github.com"
_OWNER_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _request(path: str, params: Optional[dict] = None) -> Dict[str, Any]:
    """Perform a bounded, authenticated GitHub API GET; never expose credentials."""
    policy_engine.require_network("GitHub API read")
    # Per-user OS keyring token is preferred; legacy server token remains a fallback.
    from app.tools.github_auth import get_access_token
    token = get_access_token()
    if not token:
        return {"success": False, "error": "GitHub token is not configured. Set MCP_GITHUB_TOKEN or GITHUB_TOKEN."}
    url = _API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "MCP-Coding-Tool",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read(2_000_000).decode("utf-8"))
            return {"success": True, "data": data, "status_code": response.status}
    except urllib.error.HTTPError as exc:
        # Do not return request headers, token, or raw exception details.
        message = {401: "GitHub authentication failed", 403: "GitHub denied access or rate limit reached", 404: "GitHub resource not found or not accessible"}.get(exc.code, f"GitHub API returned HTTP {exc.code}")
        return {"success": False, "status_code": exc.code, "error": message}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {"success": False, "error": f"GitHub API request failed: {type(exc).__name__}"}


def _repo(owner_repo: str) -> Optional[str]:
    value = owner_repo.strip()
    if not _OWNER_REPO.fullmatch(value) or ".." in value:
        return None
    from app.tools.github_auth import get_allowed_repositories
    allowed = get_allowed_repositories()
    # Fail closed: remote API access requires an explicit repository allowlist.
    if not allowed or value.lower() not in allowed:
        return None
    return value


def github_repo_overview(owner_repo: str) -> Dict[str, Any]:
    """Read repository metadata, default branch, and latest commit."""
    repo = _repo(owner_repo)
    if not repo:
        return {"success": False, "error": "Repository must be OWNER/REPOSITORY and allowed by MCP_GITHUB_ALLOWED_REPOS."}
    result = _request(f"/repos/{repo}")
    if not result.get("success"):
        return result
    d = result["data"]
    return {"success": True, "repository": repo, "name": d.get("full_name"), "private": d.get("private"), "default_branch": d.get("default_branch"), "html_url": d.get("html_url"), "updated_at": d.get("updated_at"), "archived": d.get("archived"), "open_issues_count": d.get("open_issues_count")}


def github_commit_history(owner_repo: str, branch: Optional[str] = None, per_page: int = 20, page: int = 1) -> Dict[str, Any]:
    """Read remote commit history; paginate explicitly (maximum 100 per page)."""
    repo = _repo(owner_repo)
    if not repo:
        return {"success": False, "error": "Repository must be OWNER/REPOSITORY and allowed by MCP_GITHUB_ALLOWED_REPOS."}
    params = {"per_page": max(1, min(int(per_page), 100)), "page": max(1, int(page))}
    if branch:
        params["sha"] = branch
    result = _request(f"/repos/{repo}/commits", params)
    if not result.get("success"):
        return result
    commits = result["data"]
    return {"success": True, "repository": repo, "page": params["page"], "per_page": params["per_page"], "commits": [{"sha": c.get("sha"), "url": c.get("html_url"), "message": (c.get("commit") or {}).get("message"), "author": ((c.get("commit") or {}).get("author") or {}).get("name"), "date": ((c.get("commit") or {}).get("author") or {}).get("date")} for c in commits]}


def github_pull_requests(owner_repo: str, state: str = "open", per_page: int = 20, page: int = 1) -> Dict[str, Any]:
    """List pull requests and merge/check summary metadata (read-only)."""
    repo = _repo(owner_repo)
    if not repo:
        return {"success": False, "error": "Repository must be OWNER/REPOSITORY and allowed by MCP_GITHUB_ALLOWED_REPOS."}
    if state not in {"open", "closed", "all"}:
        return {"success": False, "error": "state must be open, closed, or all."}
    result = _request(f"/repos/{repo}/pulls", {"state": state, "per_page": max(1, min(int(per_page), 100)), "page": max(1, int(page)), "sort": "updated", "direction": "desc"})
    if not result.get("success"):
        return result
    return {"success": True, "repository": repo, "pull_requests": [{"number": p.get("number"), "title": p.get("title"), "state": p.get("state"), "draft": p.get("draft"), "url": p.get("html_url"), "head_branch": (p.get("head") or {}).get("ref"), "head_sha": (p.get("head") or {}).get("sha"), "base_branch": (p.get("base") or {}).get("ref"), "mergeable": p.get("mergeable"), "updated_at": p.get("updated_at")} for p in result["data"]]}


def github_workflow_runs(owner_repo: str, branch: Optional[str] = None, per_page: int = 20, page: int = 1) -> Dict[str, Any]:
    """Read GitHub Actions workflow run status and identify commits/workflows."""
    repo = _repo(owner_repo)
    if not repo:
        return {"success": False, "error": "Repository must be OWNER/REPOSITORY and allowed by MCP_GITHUB_ALLOWED_REPOS."}
    params = {"per_page": max(1, min(int(per_page), 100)), "page": max(1, int(page))}
    if branch:
        params["branch"] = branch
    result = _request(f"/repos/{repo}/actions/runs", params)
    if not result.get("success"):
        return result
    data = result["data"]
    return {"success": True, "repository": repo, "total_count": data.get("total_count"), "workflow_runs": [{"id": r.get("id"), "name": r.get("name"), "workflow_id": r.get("workflow_id"), "event": r.get("event"), "status": r.get("status"), "conclusion": r.get("conclusion"), "branch": r.get("head_branch"), "commit_sha": r.get("head_sha"), "url": r.get("html_url"), "run_started_at": r.get("run_started_at"), "updated_at": r.get("updated_at")} for r in data.get("workflow_runs", [])]}


def github_workflow_jobs(owner_repo: str, run_id: int, per_page: int = 50, page: int = 1) -> Dict[str, Any]:
    """Read job-level status for a workflow run; GitHub may require separate log access for full logs."""
    repo = _repo(owner_repo)
    if not repo or int(run_id) <= 0:
        return {"success": False, "error": "Provide an allowed OWNER/REPOSITORY and positive run_id."}
    result = _request(f"/repos/{repo}/actions/runs/{int(run_id)}/jobs", {"per_page": max(1, min(int(per_page), 100)), "page": max(1, int(page))})
    if not result.get("success"):
        return result
    data = result["data"]
    return {"success": True, "repository": repo, "run_id": int(run_id), "total_count": data.get("total_count"), "jobs": [{"id": j.get("id"), "name": j.get("name"), "status": j.get("status"), "conclusion": j.get("conclusion"), "started_at": j.get("started_at"), "completed_at": j.get("completed_at"), "html_url": j.get("html_url"), "steps": [{"name": s.get("name"), "status": s.get("status"), "conclusion": s.get("conclusion"), "number": s.get("number")} for s in j.get("steps", [])]} for j in data.get("jobs", [])]}


def github_deployments(owner_repo: str, environment: Optional[str] = None, per_page: int = 20, page: int = 1) -> Dict[str, Any]:
    """Read deployment history and associated commit/environment metadata."""
    repo = _repo(owner_repo)
    if not repo:
        return {"success": False, "error": "Repository must be OWNER/REPOSITORY and allowed by MCP_GITHUB_ALLOWED_REPOS."}
    params = {"per_page": max(1, min(int(per_page), 100)), "page": max(1, int(page))}
    if environment:
        params["environment"] = environment
    result = _request(f"/repos/{repo}/deployments", params)
    if not result.get("success"):
        return result
    rows = []
    for d in result["data"]:
        status = _request(f"/repos/{repo}/deployments/{int(d.get('id', 0))}/statuses", {"per_page": 1}) if d.get("id") else {"success": False}
        latest = status.get("data", [{}])[0] if status.get("success") and status.get("data") else {}
        rows.append({"id": d.get("id"), "environment": d.get("environment"), "state": latest.get("state", "unknown"), "description": latest.get("description"), "url": latest.get("environment_url") or latest.get("target_url"), "sha": d.get("sha"), "ref": d.get("ref"), "created_at": d.get("created_at"), "updated_at": latest.get("updated_at")})
    return {"success": True, "repository": repo, "deployments": rows}
