import os
from pathlib import Path

BASE_DIR = Path(r"C:\Development\chatgpt-mcp-server")
BASE_DIR.mkdir(parents=True, exist_ok=True)

files = {}

# 1. requirements.txt
files["requirements.txt"] = """mcp>=1.3.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
pyyaml>=6.0.0
uvicorn>=0.30.0
starlette>=0.38.0
python-dotenv>=1.0.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
"""

# 2. .gitignore
files[".gitignore"] = """__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
.env
.venv/
venv/
.pytest_cache/
.coverage
htmlcov/
"""

# 3. .env.example
files[".env.example"] = """MCP_HOST=127.0.0.1
MCP_PORT=8000

# Optional Bearer Token for remote access authentication (Leave blank for unauthenticated local testing)
AUTH_TOKEN=

# Operational & Security Limits
MAX_FILE_SIZE_BYTES=2097152
MAX_COMMAND_OUTPUT_BYTES=102400
COMMAND_TIMEOUT_SECONDS=120
"""

# 4. config/repositories.yaml
files["config/repositories.yaml"] = """repositories:
  interview-copilot:
    path: 'C:/Users/Jashuva/Desktop/interview-copilot'
    description: 'Real-time AI voice copilot workspace'
  AI_jobs_apply:
    path: 'C:/Development/AI_jobs_apply'
    description: 'Job application automation workspace'
  agentic-sdlc:
    path: 'C:/Development/agentic-sdlc'
    description: 'Multi-agent autonomous SDLC workspace'
"""

# 5. server/__init__.py
files["server/__init__.py"] = ""

# 6. server/config.py
files["server/config.py"] = '''import os
import yaml
from pathlib import Path
from typing import Dict, List, Set, Any
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    MCP_HOST: str = "127.0.0.1"
    MCP_PORT: int = 8000
    AUTH_TOKEN: str = ""
    
    REPOSITORIES_CONFIG_PATH: str = str(
        Path(__file__).resolve().parent.parent / "config" / "repositories.yaml"
    )

    MAX_FILE_SIZE_BYTES: int = 2 * 1024 * 1024  # 2MB
    MAX_COMMAND_OUTPUT_BYTES: int = 100 * 1024   # 100KB
    COMMAND_TIMEOUT_SECONDS: int = 120

    BLOCKED_PATTERNS: List[str] = [
        ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx",
        "credentials.json", "secrets.json", "id_rsa*", "id_ed25519*",
        "*.keystore", "*.jks", "*.token", "*.p8", "*credential*.json"
    ]

    ALLOWED_COMMAND_BINARIES: Set[str] = {
        "python", "python3", "pytest", "pip", "npm", "node", "npx",
        "git", "uv", "ruff", "mypy", "flake8", "black", "isort",
        "cargo", "go", "dir", "echo", "where"
    }

    BLOCKED_COMMANDS: List[str] = [
        "format", "shutdown", "diskpart", "rm -rf", "del /s", "rmdir /s",
        "git reset --hard", "git clean -fd", "git push", "git commit",
        "reg", "powershell -enc", "curl", "wget"
    ]

    def load_repositories(self) -> Dict[str, Dict[str, Any]]:
        config_file = Path(self.REPOSITORIES_CONFIG_PATH)
        if not config_file.exists():
            return {}
        with open(config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return data.get("repositories", {})

    def save_repositories(self, repos: Dict[str, Dict[str, Any]]) -> None:
        config_file = Path(self.REPOSITORIES_CONFIG_PATH)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.safe_dump({"repositories": repos}, f, default_flow_style=False)

config = AppConfig()
'''

# 7. server/session.py
files["server/session.py"] = '''import logging
import threading
from pathlib import Path
from typing import Dict, Optional, Tuple
from server.config import config

logger = logging.getLogger("mcp_server.session")

class SessionManager:
    """Manages active workspace selection per MCP session to guarantee session isolation."""
    def __init__(self):
        self._session_workspaces: Dict[str, str] = {}
        self._default_workspace: Optional[str] = None
        self._lock = threading.Lock()
        repos = config.load_repositories()
        if repos:
            self._default_workspace = next(iter(repos.keys()))

    def get_active_repo_name(self, session_id: Optional[str] = None) -> Optional[str]:
        with self._lock:
            if session_id and session_id in self._session_workspaces:
                return self._session_workspaces[session_id]
            return self._default_workspace

    def set_active_repo_name(self, repo_name: str, session_id: Optional[str] = None) -> Tuple[bool, str]:
        repos = config.load_repositories()
        if repo_name not in repos:
            available = ", ".join(repos.keys()) if repos else "None"
            return False, f"Repository '{repo_name}' not found. Available: [{available}]"

        repo_path = Path(repos[repo_name]["path"]).resolve()
        if not repo_path.exists() or not repo_path.is_dir():
            return False, f"Configured path for '{repo_name}' does not exist: {repo_path}"

        with self._lock:
            if session_id:
                self._session_workspaces[session_id] = repo_name
            self._default_workspace = repo_name
            
        logger.info(f"Session [{session_id or 'default'}] active workspace switched to '{repo_name}' -> {repo_path}")
        return True, f"Active repository set to '{repo_name}' ({repo_path})"

    def get_active_repo_path(self, session_id: Optional[str] = None) -> Path:
        active_name = self.get_active_repo_name(session_id)
        if not active_name:
            raise RuntimeError("No active repository selected. Please call select_repository() first.")
        repos = config.load_repositories()
        if active_name not in repos:
            raise RuntimeError(f"Active repository '{active_name}' not found in registry.")
        path = Path(repos[active_name]["path"]).resolve()
        if not path.exists() or not path.is_dir():
            raise RuntimeError(f"Active repository directory does not exist: {path}")
        return path

session_manager = SessionManager()
'''

# 8. server/security.py
files["server/security.py"] = '''import fnmatch
import logging
import shlex
from pathlib import Path
from typing import Tuple, List, Optional
from server.config import config
from server.session import session_manager

logger = logging.getLogger("mcp_server.security")

class SecurityError(Exception):
    pass

def sanitize_and_resolve_path(relative_or_absolute_path: str, session_id: Optional[str] = None) -> Path:
    """
    Sanitizes, canonicalizes, and verifies that the given path is strictly within the active repository boundary.
    Blocks path traversal, absolute external escapes, symlink escapes, and secret files.
    """
    repo_root = session_manager.get_active_repo_path(session_id)
    raw_path_str = str(relative_or_absolute_path).strip()
    
    if raw_path_str.startswith(("\\\\", "//")):
        raise SecurityError("UNC network paths are prohibited.")

    target_path = Path(raw_path_str)
    if not target_path.is_absolute():
        target_path = repo_root / target_path

    try:
        resolved_path = target_path.resolve(strict=False)
    except Exception as e:
        raise SecurityError(f"Path resolution error: {e}")

    try:
        resolved_path.relative_to(repo_root)
    except ValueError:
        logger.error(f"Path escape attempt: {resolved_path} outside {repo_root}")
        raise SecurityError(f"Access Denied: Path escapes active repository boundary ({repo_root.name}).")

    # Check symlink target
    if resolved_path.is_symlink():
        symlink_target = resolved_path.resolve()
        try:
            symlink_target.relative_to(repo_root)
        except ValueError:
            raise SecurityError(f"Access Denied: Symlink points outside active repository ({symlink_target}).")

    # Blocked secret filename / pattern check
    filename = resolved_path.name
    for pattern in config.BLOCKED_PATTERNS:
        if fnmatch.fnmatch(filename.lower(), pattern.lower()) or fnmatch.fnmatch(resolved_path.name.lower(), pattern.lower()):
            logger.warning(f"Blocked secret access to '{filename}' matching pattern '{pattern}'")
            raise SecurityError(f"Access Denied: Access to sensitive file '{filename}' is prohibited.")

    return resolved_path

def validate_command_security(command: str) -> Tuple[str, List[str]]:
    """
    Validates terminal command string against security blocklist and allowed execution rules.
    """
    normalized_cmd = command.strip().lower()
    if not normalized_cmd:
        raise SecurityError("Command cannot be empty.")

    for blocked in config.BLOCKED_COMMANDS:
        if blocked.lower() in normalized_cmd:
            raise SecurityError(f"Command execution blocked: '{blocked}' is forbidden.")

    try:
        args = shlex.split(command, posix=False)
    except Exception as e:
        raise SecurityError(f"Invalid command syntax: {e}")

    if not args:
        raise SecurityError("Command is empty.")

    binary = Path(args[0]).name.lower()
    if binary.endswith(".exe"):
        binary = binary[:-4]

    if binary not in config.ALLOWED_COMMAND_BINARIES:
        raise SecurityError(
            f"Binary '{binary}' is not allowed. Permitted: {', '.join(sorted(config.ALLOWED_COMMAND_BINARIES))}"
        )

    return binary, args
'''

# 9. tools/__init__.py
files["tools/__init__.py"] = ""

# 10. tools/workspace.py
files["tools/workspace.py"] = '''import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from server.config import config
from server.session import session_manager

def list_repositories() -> Dict[str, Any]:
    """
    List all registered repositories available for MCP operations, their configured paths, and active status.
    ChatGPT should call this first to discover available workspaces.
    """
    repos = config.load_repositories()
    active = session_manager.get_active_repo_name()
    return {
        "active_repository": active,
        "total_configured": len(repos),
        "repositories": [
            {
                "name": name,
                "path": data.get("path"),
                "description": data.get("description", ""),
                "is_active": (name == active),
                "exists_on_disk": Path(data.get("path", "")).exists()
            }
            for name, data in repos.items()
        ]
    }

def select_repository(repository_name: str) -> Dict[str, Any]:
    """
    Select the active workspace repository for subsequent MCP operations.
    All filesystem, search, terminal, and Git operations will operate strictly inside this repository until changed.
    """
    success, message = session_manager.set_active_repo_name(repository_name)
    return {
        "success": success,
        "message": message,
        "active_repository": session_manager.get_active_repo_name()
    }

def get_current_repository() -> Dict[str, Any]:
    """
    Get metadata, absolute root path, and active Git branch of the currently selected repository.
    """
    active_name = session_manager.get_active_repo_name()
    if not active_name:
        return {"error": "No repository currently selected. Call select_repository() first."}

    repo_path = session_manager.get_active_repo_path()
    branch = "unknown"
    try:
        res = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=5
        )
        if res.returncode == 0 and res.stdout.strip():
            branch = res.stdout.strip()
    except Exception:
        pass

    return {
        "repository_name": active_name,
        "absolute_path": str(repo_path),
        "git_branch": branch
    }

def add_repository(name: str, path: str, description: str = "") -> Dict[str, Any]:
    """
    Add a new local repository path to the MCP server workspace registry in repositories.yaml.
    Does not modify any application code.
    """
    resolved = Path(path).resolve()
    if not resolved.exists() or not resolved.is_dir():
        return {"error": f"Path '{path}' does not exist or is not a valid directory on disk."}

    repos = config.load_repositories()
    repos[name] = {"path": str(resolved), "description": description or f"Repository at {resolved}"}
    config.save_repositories(repos)
    return {"success": True, "message": f"Repository '{name}' added successfully at {resolved}."}

def remove_repository(name: str) -> Dict[str, Any]:
    """
    Remove a repository from the MCP workspace registry.
    SAFETY GUARANTEE: This tool ONLY removes the registry entry in repositories.yaml. It NEVER deletes or modifies the physical repository on disk.
    """
    repos = config.load_repositories()
    if name not in repos:
        return {"error": f"Repository '{name}' not found in registry."}

    del repos[name]
    config.save_repositories(repos)
    return {"success": True, "message": f"Repository '{name}' removed from MCP registry. Physical files were untouched."}
'''

# 11. tools/filesystem.py
files["tools/filesystem.py"] = '''import os
from pathlib import Path
from typing import Dict, Any, Optional
from server.config import config
from server.session import session_manager
from server.security import sanitize_and_resolve_path, SecurityError

def list_files(path: str = ".", recursive: bool = False, max_results: int = 200) -> Dict[str, Any]:
    """
    List files and directories in the active repository at the specified relative path.
    Automatically filters build artifacts and secret files.
    """
    try:
        repo_root = session_manager.get_active_repo_path()
        target_dir = sanitize_and_resolve_path(path)
        if not target_dir.is_dir():
            return {"error": f"'{path}' is not a directory."}

        results = []
        ignored = {".git", "__pycache__", "node_modules", "venv", ".venv", ".pytest_cache", "dist", "build", "target"}

        if recursive:
            for root, dirs, files in os.walk(target_dir):
                dirs[:] = [d for d in dirs if d not in ignored]
                for f in files:
                    try:
                        resolved = sanitize_and_resolve_path(str(Path(root) / f))
                        rel = resolved.relative_to(repo_root)
                        results.append({
                            "path": str(rel).replace("\\\\", "/"),
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
                    resolved = sanitize_and_resolve_path(str(item))
                    rel = resolved.relative_to(repo_root)
                    results.append({
                        "path": str(rel).replace("\\\\", "/"),
                        "type": "directory" if resolved.is_dir() else "file",
                        "size_bytes": resolved.stat().st_size if resolved.is_file() else 0
                    })
                except SecurityError:
                    continue
                if len(results) >= max_results:
                    break

        return {
            "repository": session_manager.get_active_repo_name(),
            "base_directory": str(target_dir.relative_to(repo_root)).replace("\\\\", "/"),
            "count": len(results),
            "entries": results
        }
    except Exception as e:
        return {"error": str(e)}

def read_file(path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> Dict[str, Any]:
    """
    Read content of a source file inside the active repository.
    Path must be relative to the active repository root. Secret files (.env, *.key) are strictly blocked.
    """
    try:
        resolved = sanitize_and_resolve_path(path)
        if not resolved.is_file():
            return {"error": f"File '{path}' does not exist or is a directory."}

        if resolved.stat().st_size > config.MAX_FILE_SIZE_BYTES:
            return {"error": f"File exceeds maximum read size of {config.MAX_FILE_SIZE_BYTES} bytes."}

        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total_lines = len(lines)
        if start_line is not None or end_line is not None:
            s = max(1, start_line or 1)
            e = min(total_lines, end_line or total_lines)
            return {
                "file_path": str(resolved.relative_to(session_manager.get_active_repo_path())).replace("\\\\", "/"),
                "start_line": s,
                "end_line": e,
                "total_lines": total_lines,
                "content": "".join(lines[s - 1:e])
            }

        return {
            "file_path": str(resolved.relative_to(session_manager.get_active_repo_path())).replace("\\\\", "/"),
            "total_lines": total_lines,
            "content": "".join(lines)
        }
    except Exception as e:
        return {"error": str(e)}

def write_file(path: str, content: str, overwrite: bool = True) -> Dict[str, Any]:
    """
    Write or update a file in the active repository. Modifies the actual file on disk so changes are directly visible in VS Code.
    Automatically creates parent directories if needed.
    """
    try:
        resolved = sanitize_and_resolve_path(path)
        if resolved.exists() and not overwrite:
            return {"error": f"File '{path}' already exists and overwrite is False."}

        if len(content.encode("utf-8")) > config.MAX_FILE_SIZE_BYTES:
            return {"error": f"Content exceeds max limit of {config.MAX_FILE_SIZE_BYTES} bytes."}

        resolved.parent.mkdir(parents=True, exist_ok=True)
        with open(resolved, "w", encoding="utf-8", newline="\\n") as f:
            f.write(content)

        return {
            "success": True,
            "file_path": str(resolved.relative_to(session_manager.get_active_repo_path())).replace("\\\\", "/"),
            "bytes_written": len(content.encode("utf-8"))
        }
    except Exception as e:
        return {"error": str(e)}

def create_directory(path: str) -> Dict[str, Any]:
    """
    Create a new directory (and any necessary parent directories) inside the active repository.
    """
    try:
        resolved = sanitize_and_resolve_path(path)
        resolved.mkdir(parents=True, exist_ok=True)
        return {
            "success": True,
            "directory_path": str(resolved.relative_to(session_manager.get_active_repo_path())).replace("\\\\", "/")
        }
    except Exception as e:
        return {"error": str(e)}

def delete_file(path: str) -> Dict[str, Any]:
    """
    Delete a specific file inside the active repository. Rejects directory deletion for safety.
    """
    try:
        resolved = sanitize_and_resolve_path(path)
        if not resolved.is_file():
            return {"error": f"File '{path}' not found or is a directory."}
        resolved.unlink()
        return {
            "success": True,
            "deleted_file": str(resolved.relative_to(session_manager.get_active_repo_path())).replace("\\\\", "/")
        }
    except Exception as e:
        return {"error": str(e)}
'''

# 12. tools/search.py
files["tools/search.py"] = '''import os
import fnmatch
from pathlib import Path
from typing import Dict, Any
from server.config import config
from server.session import session_manager
from server.security import sanitize_and_resolve_path

def search_code(query: str, path: str = ".", max_results: int = 50) -> Dict[str, Any]:
    """
    Search for text, function names, or regex strings inside files in the active repository.
    Skips ignored build directories, virtual environments, binaries, and sensitive files.
    """
    try:
        repo_root = session_manager.get_active_repo_path()
        target_dir = sanitize_and_resolve_path(path)
        matches = []
        ignored = {".git", "__pycache__", "node_modules", "venv", ".venv", ".venv-mcp", ".pytest_cache", "dist", "build", "coverage", "target"}

        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in ignored]
            for filename in files:
                file_full = Path(root) / filename
                try:
                    resolved = sanitize_and_resolve_path(str(file_full))
                    if resolved.stat().st_size > config.MAX_FILE_SIZE_BYTES:
                        continue

                    # Check for binary file by reading first block
                    with open(resolved, "rb") as bf:
                        sample = bf.read(1024)
                        if b"\\0" in sample:
                            continue

                    with open(resolved, "r", encoding="utf-8", errors="ignore") as f:
                        for idx, line in enumerate(f, start=1):
                            if query.lower() in line.lower():
                                matches.append({
                                    "file": str(resolved.relative_to(repo_root)).replace("\\\\", "/"),
                                    "line": idx,
                                    "snippet": line.strip()
                                })
                                if len(matches) >= max_results:
                                    break
                except Exception:
                    continue
                if len(matches) >= max_results:
                    break
            if len(matches) >= max_results:
                break

        return {
            "repository": session_manager.get_active_repo_name(),
            "query": query,
            "total_matches": len(matches),
            "results": matches
        }
    except Exception as e:
        return {"error": str(e)}
'''

# 13. tools/terminal.py
files["tools/terminal.py"] = '''import subprocess
from typing import Dict, Any
from server.config import config
from server.session import session_manager
from server.security import validate_command_security, SecurityError

def run_command(command: str, timeout: int = 120) -> Dict[str, Any]:
    """
    Run a development command (e.g. pytest, python, npm test, git status) strictly with working directory set to the active repository.
    Guarded by command security filter, execution timeout, and output capping.
    """
    try:
        validate_command_security(command)
        repo_root = session_manager.get_active_repo_path()

        effective_timeout = min(timeout, config.COMMAND_TIMEOUT_SECONDS)

        process = subprocess.Popen(
            command,
            cwd=str(repo_root),
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace"
        )

        try:
            stdout, stderr = process.communicate(timeout=effective_timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            return {
                "error": f"Command timed out after {effective_timeout}s.",
                "stdout": stdout[:config.MAX_COMMAND_OUTPUT_BYTES],
                "stderr": stderr[:config.MAX_COMMAND_OUTPUT_BYTES],
                "exit_code": -1
            }

        return {
            "repository": session_manager.get_active_repo_name(),
            "command": command,
            "exit_code": process.returncode,
            "stdout": stdout[:config.MAX_COMMAND_OUTPUT_BYTES],
            "stderr": stderr[:config.MAX_COMMAND_OUTPUT_BYTES]
        }
    except SecurityError as se:
        return {"error": f"Security Violation: {se}"}
    except Exception as e:
        return {"error": str(e)}
'''

# 14. tools/git.py
files["tools/git.py"] = '''import subprocess
from typing import Dict, Any, Optional
from server.session import session_manager
from server.security import sanitize_and_resolve_path

def git_status() -> Dict[str, Any]:
    """
    Inspect the working directory git status of the active repository (staged, modified, and untracked files).
    """
    try:
        repo_root = session_manager.get_active_repo_path()
        res = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10
        )
        return {
            "repository": session_manager.get_active_repo_name(),
            "status_output": res.stdout,
            "stderr": res.stderr,
            "exit_code": res.returncode
        }
    except Exception as e:
        return {"error": str(e)}

def git_diff(file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    View uncommitted git diff in the active repository to inspect modifications made by ChatGPT.
    """
    try:
        repo_root = session_manager.get_active_repo_path()
        cmd = ["git", "diff"]
        if file_path:
            resolved = sanitize_and_resolve_path(file_path)
            cmd.append(str(resolved.relative_to(repo_root)))

        res = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=15
        )
        return {
            "repository": session_manager.get_active_repo_name(),
            "diff": res.stdout,
            "exit_code": res.returncode
        }
    except Exception as e:
        return {"error": str(e)}

def git_branch() -> Dict[str, Any]:
    """
    Inspect active branch and available branches in the active repository.
    """
    try:
        repo_root = session_manager.get_active_repo_path()
        res = subprocess.run(
            ["git", "branch", "-a"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10
        )
        return {
            "repository": session_manager.get_active_repo_name(),
            "branches": res.stdout,
            "exit_code": res.returncode
        }
    except Exception as e:
        return {"error": str(e)}
'''

# 15. server/main.py
files["server/main.py"] = '''import logging
import sys
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from mcp.server.fastmcp import FastMCP
from server.config import config
from tools import workspace, filesystem, search, terminal, git

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("mcp_server")

# FastMCP application instance
mcp = FastMCP(
    name="Multi-Repo-Code-Agent-MCP",
    host=config.MCP_HOST,
    port=config.MCP_PORT
)

# 1. Register Workspace Management Tools
mcp.tool()(workspace.list_repositories)
mcp.tool()(workspace.select_repository)
mcp.tool()(workspace.get_current_repository)
mcp.tool()(workspace.add_repository)
mcp.tool()(workspace.remove_repository)

# 2. Register Filesystem Tools
mcp.tool()(filesystem.list_files)
mcp.tool()(filesystem.read_file)
mcp.tool()(filesystem.write_file)
mcp.tool()(filesystem.create_directory)
mcp.tool()(filesystem.delete_file)

# 3. Register Code Search Tool
mcp.tool()(search.search_code)

# 4. Register Terminal Execution Tool
mcp.tool()(terminal.run_command)

# 5. Register Git Inspection Tools
mcp.tool()(git.git_status)
mcp.tool()(git.git_diff)
mcp.tool()(git.git_branch)

class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow health checks without auth
        if request.url.path in ["/health", "/"]:
            return await call_next(request)

        if config.AUTH_TOKEN:
            auth_header = request.headers.get("Authorization", "")
            expected = f"Bearer {config.AUTH_TOKEN}"
            if not auth_header or auth_header.strip() != expected:
                logger.warning(f"Unauthorized request rejected from {request.client.host if request.client else 'unknown'}")
                return JSONResponse({"error": "Unauthorized. Invalid or missing Bearer token."}, status_code=401)

        return await call_next(request)

def start_server():
    logger.info("=" * 70)
    logger.info("Standalone Multi-Repository MCP Server Initializing")
    logger.info(f"Host: {config.MCP_HOST}:{config.MCP_PORT}")
    logger.info(f"Streamable HTTP & SSE Endpoint: http://{config.MCP_HOST}:{config.MCP_PORT}/sse")
    logger.info(f"Authentication: {'ENABLED (Bearer Token required)' if config.AUTH_TOKEN else 'DISABLED (Local Dev Mode)'}")
    logger.info("=" * 70)
    mcp.run(transport="sse")

if __name__ == "__main__":
    start_server()
'''

# 16. run_server.py
files["run_server.py"] = '''import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from server.main import start_server

if __name__ == "__main__":
    start_server()
'''

# Write all files
for rel_path, content in files.items():
    dest = BASE_DIR / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created: {dest}")

print("All server files successfully created.")
