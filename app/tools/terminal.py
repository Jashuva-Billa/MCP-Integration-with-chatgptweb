import subprocess
import time
from typing import Dict, Any
from app.config import settings
from app.core.session import session_manager
from app.core.security import security_engine, SecurityError

def run_command(command: str, timeout: int = 120) -> Dict[str, Any]:
    """Run one allowlisted executable in the active repository, without invoking a shell."""
    try:
        _binary, args = security_engine.validate_command_security(command)
        repo_root = session_manager.get_active_repo_path()
        effective_timeout = min(timeout, settings.COMMAND_TIMEOUT_SECONDS)
        start_time = time.time()
        try:
            process = subprocess.Popen(
                args,
                cwd=str(repo_root),
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
            )
            stdout, stderr = process.communicate(timeout=effective_timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            return {
                "error": f"Command timed out after {effective_timeout}s.",
                "repository": session_manager.get_active_repo_name(),
                "command": command,
                "exit_code": -1,
                "duration_seconds": round(time.time() - start_time, 2),
                "stdout": stdout[:settings.MAX_COMMAND_OUTPUT_BYTES],
                "stderr": stderr[:settings.MAX_COMMAND_OUTPUT_BYTES],
            }
        return {
            "repository": session_manager.get_active_repo_name(),
            "command": command,
            "exit_code": process.returncode,
            "duration_seconds": round(time.time() - start_time, 2),
            "stdout": stdout[:settings.MAX_COMMAND_OUTPUT_BYTES],
            "stderr": stderr[:settings.MAX_COMMAND_OUTPUT_BYTES],
        }
    except SecurityError as se:
        return {"error": f"Security Violation: {se}"}
    except Exception as e:
        return {"error": str(e)}
