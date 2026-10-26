"""Interactive local GitHub device authorization and per-machine repository selection.

The OAuth client ID is public application configuration. User access tokens are kept
in the OS credential store via keyring, never in the repository or .env file.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.permissions import policy_engine

_GITHUB = "https://github.com"
_API = "https://api.github.com"
_SERVICE = "mcp-coding-tool-github"
_ACCOUNT = "local-user"
_OWNER_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_PENDING: dict[str, Any] = {}
_SELECTION_PATH = Path(__file__).resolve().parents[2] / "runtime" / "github_auth" / "selected_repositories.json"


def _client_id() -> str:
    value = os.getenv("MCP_GITHUB_CLIENT_ID", "").strip()
    if value:
        return value
    try:
        from dotenv import dotenv_values
        return str(dotenv_values(Path.cwd() / ".env").get("MCP_GITHUB_CLIENT_ID") or "").strip()
    except Exception:
        return ""


def _keyring():
    try:
        import keyring
        return keyring
    except ImportError:
        return None


def _request_json(url: str, payload: dict, *, bearer: str = "") -> dict:
    policy_engine.require_network("GitHub authorization")
    body = urllib.parse.urlencode(payload).encode("utf-8")
    headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded", "User-Agent": "MCP-Coding-Tool"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read(1_000_000).decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        try:
            data = json.loads(exc.read(100_000).decode("utf-8"))
        except Exception:
            data = {}
        return {"error": data.get("error", f"http_{exc.code}"), "error_description": data.get("error_description", "GitHub authorization request failed")}
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {"error": "network_error", "error_description": f"GitHub request failed ({type(exc).__name__})."}


def _load_selected() -> list[str]:
    try:
        data = json.loads(_SELECTION_PATH.read_text(encoding="utf-8"))
        return sorted({str(x) for x in data.get("repositories", []) if isinstance(x, str) and _OWNER_REPO.fullmatch(x)})
    except (OSError, ValueError, AttributeError):
        return []


def _save_selected(repositories: list[str]) -> None:
    _SELECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _SELECTION_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps({"repositories": sorted(set(repositories))}, indent=2), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(_SELECTION_PATH)
    try:
        os.chmod(_SELECTION_PATH.parent, 0o700)
    except OSError:
        pass


def get_access_token() -> str:
    """Return the user token from OS credential storage, falling back to legacy admin config."""
    kr = _keyring()
    if kr is not None:
        try:
            stored = kr.get_password(_SERVICE, _ACCOUNT) or ""
            if stored:
                return stored
        except Exception:
            pass
    return (getattr(settings, "MCP_GITHUB_TOKEN", "") or os.getenv("GITHUB_TOKEN", "")).strip()


def get_allowed_repositories() -> set[str]:
    """Explicit local selections take precedence; legacy env allowlist remains supported."""
    if _SELECTION_PATH.exists():
        return {x.lower() for x in _load_selected()}
    configured = getattr(settings, "MCP_GITHUB_ALLOWED_REPOS", "") or ""
    return {x.strip().lower() for x in configured.split(",") if x.strip()}


def github_connect_start() -> dict[str, Any]:
    """Start GitHub Device Flow; open the returned URL and enter the one-time code."""
    client_id = _client_id()
    if not client_id:
        return {"success": False, "error": "GitHub app client ID is not configured. Set MCP_GITHUB_CLIENT_ID once in the local server environment."}
    if _keyring() is None:
        return {"success": False, "error": "OS credential-store support is unavailable. Install dependencies with `pip install -r requirements.txt` (keyring is required)."}
    result = _request_json(f"{_GITHUB}/login/device/code", {"client_id": client_id, "scope": "repo read:org"})
    if result.get("error") or not result.get("device_code"):
        return {"success": False, "error": result.get("error_description", "Could not start GitHub device authorization."), "error_code": result.get("error")}
    _PENDING.clear()
    _PENDING.update({"device_code": result["device_code"], "interval": max(5, int(result.get("interval", 5))), "expires_in": int(result.get("expires_in", 900)), "client_id": client_id})
    return {"success": True, "verification_uri": result.get("verification_uri", f"{_GITHUB}/login/device"), "user_code": result.get("user_code"), "expires_in_seconds": _PENDING["expires_in"], "poll_interval_seconds": _PENDING["interval"], "instructions": "Open verification_uri, enter user_code, approve access, then call github_connect_complete. Never share the user code."}


def github_connect_complete() -> dict[str, Any]:
    """Poll the device flow once and securely persist the approved token in OS keyring."""
    if not _PENDING.get("device_code"):
        return {"success": False, "error": "No pending GitHub authorization. Call github_connect_start first."}
    kr = _keyring()
    if kr is None:
        return {"success": False, "error": "OS credential-store support is unavailable; install requirements and restart."}
    result = _request_json(f"{_GITHUB}/login/oauth/access_token", {"client_id": _PENDING["client_id"], "device_code": _PENDING["device_code"], "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
    error = result.get("error")
    if error == "authorization_pending":
        return {"success": False, "pending": True, "retry_after_seconds": _PENDING["interval"], "message": "Authorization is still pending. Approve it in your browser, then call this tool again."}
    if error == "slow_down":
        _PENDING["interval"] += 5
        return {"success": False, "pending": True, "retry_after_seconds": _PENDING["interval"], "message": "GitHub requested slower polling. Wait, then call this tool again."}
    if error:
        _PENDING.clear()
        return {"success": False, "error": result.get("error_description", "GitHub authorization failed."), "error_code": error}
    token = result.get("access_token", "")
    if not token:
        return {"success": False, "error": "GitHub did not return an access token."}
    try:
        kr.set_password(_SERVICE, _ACCOUNT, token)
    except Exception as exc:
        return {"success": False, "error": f"Could not store token in the OS credential store ({type(exc).__name__}). No token was returned."}
    _PENDING.clear()
    return {"success": True, "message": "GitHub connected. Access token stored in the OS credential store.", "next_step": "Call github_list_available_repositories, then github_select_repositories."}


def _github_get(path: str, token: str, params: dict | None = None) -> tuple[int, Any]:
    policy_engine.require_network("GitHub API read")
    url = _API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "MCP-Coding-Tool"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.status, json.loads(response.read(2_000_000).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return 0, {}


def github_connection_status() -> dict[str, Any]:
    """Show whether GitHub is connected without revealing any credentials."""
    token = get_access_token()
    if not token:
        return {"connected": False, "selected_repository_count": len(_load_selected()), "next_step": "Call github_connect_start."}
    status, user = _github_get("/user", token)
    if status != 200:
        return {"connected": False, "error": "Stored GitHub credential is invalid or unavailable. Reconnect with github_connect_start."}
    return {"connected": True, "login": user.get("login"), "selected_repositories": _load_selected(), "credential_store": "OS keyring" if not (getattr(settings, "MCP_GITHUB_TOKEN", "") or os.getenv("GITHUB_TOKEN", "")).strip() else "environment configuration"}


def github_list_available_repositories(per_page: int = 100, page: int = 1) -> dict[str, Any]:
    """List repositories visible to the connected user for explicit selection."""
    token = get_access_token()
    if not token:
        return {"success": False, "error": "GitHub is not connected. Call github_connect_start and github_connect_complete first."}
    per_page = max(1, min(int(per_page), 100))
    page = max(1, int(page))
    status, data = _github_get("/user/repos", token, {"visibility": "all", "affiliation": "owner,collaborator,organization_member", "sort": "updated", "per_page": per_page, "page": page})
    if status != 200 or not isinstance(data, list):
        return {"success": False, "error": "Could not list repositories. Check OAuth permissions and organization SSO authorization."}
    selected = get_allowed_repositories()
    return {"success": True, "page": page, "per_page": per_page, "repositories": [{"full_name": r.get("full_name"), "private": r.get("private"), "description": r.get("description"), "default_branch": r.get("default_branch"), "html_url": r.get("html_url"), "selected": str(r.get("full_name", "")).lower() in selected, "permissions": {k: bool(v) for k, v in (r.get("permissions") or {}).items() if k in {"admin", "maintain", "push", "triage", "pull"}}} for r in data]}


def github_select_repositories(repositories: list[str]) -> dict[str, Any]:
    """Replace the local allowlist with selected repositories after validating GitHub visibility."""
    token = get_access_token()
    if not token:
        return {"success": False, "error": "GitHub is not connected. Call github_connect_start and github_connect_complete first."}
    if not isinstance(repositories, list) or len(repositories) > 500:
        return {"success": False, "error": "repositories must be a list containing at most 500 OWNER/REPOSITORY names."}
    requested = sorted({str(x).strip() for x in repositories})
    if any(not _OWNER_REPO.fullmatch(x) or ".." in x for x in requested):
        return {"success": False, "error": "Each repository must use OWNER/REPOSITORY format."}
    # Validate every requested repository against the authenticated account before granting local access.
    for repo in requested:
        status, data = _github_get(f"/repos/{repo}", token)
        if status != 200 or str(data.get("full_name", "")).lower() != repo.lower():
            return {"success": False, "error": f"Repository '{repo}' is not accessible to the connected GitHub account; no changes were saved."}
    _save_selected(requested)
    return {"success": True, "selected_repositories": requested, "count": len(requested), "message": "Local repository selection saved. GitHub API tools will be restricted to these repositories."}


def github_disconnect() -> dict[str, Any]:
    """Delete the locally stored credential and repository selection; does not revoke OAuth at GitHub."""
    kr = _keyring()
    if kr is not None:
        try:
            kr.delete_password(_SERVICE, _ACCOUNT)
        except Exception:
            pass
    _PENDING.clear()
    _save_selected([])
    return {"success": True, "message": "Local GitHub credential and repository selection cleared. To revoke the OAuth grant too, remove the app in GitHub Settings → Applications."}
