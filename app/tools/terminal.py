"""
Full Command Execution Engine
==============================
Supports a wide range of development tools. Policy-gated based on the
active permission profile. Captures stdout, stderr, exit code, and duration.

Safety
- In SAFE/FULL mode, enforces the allowlist from the active profile.
- In UNRESTRICTED mode, executes arbitrary commands (explicitly opt-in only).
- Never invokes a system shell (shell=False) in any mode.
- Command string is tokenized with shlex; shell operators are rejected in non-unrestricted modes.
- Secrets in output are redacted before being returned.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.audit import audit
from app.core.permissions import PermissionProfile, PolicyViolation, policy_engine
from app.core.security import SecurityError, security_engine
from app.core.session import session_manager


# ---------------------------------------------------------------------------
# Secret redaction pattern applied to all command output
# ---------------------------------------------------------------------------
_REDACT_RE = re.compile(
    r"(token|password|secret|key|auth|credential|passwd|apikey|api_key)"
    r"(\s*[=:]\s*)([^\s\n]+)",
    re.IGNORECASE,
)


def _redact_output(text: str) -> str:
    return _REDACT_RE.sub(lambda m: m.group(1) + m.group(2) + "[REDACTED]", text)


# ---------------------------------------------------------------------------
# Core execution helper
# ---------------------------------------------------------------------------

def _terminate_process_tree(proc: subprocess.Popen) -> None:
    """Ensure process and all child processes are killed cleanly upon timeout."""
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True,
                check=False,
            )
        else:
            proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def diagnose_command_failure(
    command: str,
    exit_code: int,
    stdout: str,
    stderr: str,
    timed_out: bool,
) -> Dict[str, Any]:
    """
    Analyze command execution failure to provide actionable diagnostics
    and remediation steps for the autonomous agent.
    """
    combined = f"{stdout}\n{stderr}".lower()

    if timed_out:
        return {
            "category": "TIMEOUT",
            "summary": "Command exceeded wall-clock timeout limit.",
            "suggested_action": "Increase timeout parameter or inspect if process is waiting on interactive user input.",
        }

    # Python import/module errors
    if "modulenotfounderror" in combined or "no module named" in combined:
        match = re.search(r"no module named ['\"]([^'\"]+)['\"]", combined)
        pkg = match.group(1) if match else "missing package"
        return {
            "category": "MISSING_DEPENDENCY",
            "summary": f"Python module missing: '{pkg}'.",
            "suggested_action": f"Run install_dependencies(manager='pip', package='{pkg}') or install from requirements.txt.",
        }

    # Node/NPM module errors
    if "cannot find module" in combined or "err_module_not_found" in combined:
        return {
            "category": "MISSING_DEPENDENCY",
            "summary": "Node.js dependency not found.",
            "suggested_action": "Run install_dependencies(manager='npm') to install package dependencies.",
        }

    # Command / binary not found
    if "is not recognized as an internal or external command" in combined or "command not found" in combined:
        binary = command.split()[0] if command.split() else "command"
        return {
            "category": "COMMAND_NOT_FOUND",
            "summary": f"Executable '{binary}' is not installed or not in PATH.",
            "suggested_action": f"Verify binary is installed in virtualenv/PATH or check active permission profile.",
        }

    # Syntax errors
    if "syntaxerror" in combined or "parse error" in combined or "invalid syntax" in combined:
        return {
            "category": "SYNTAX_ERROR",
            "summary": "Source code syntax error detected.",
            "suggested_action": "Inspect stack trace line number and use replace_in_file to correct syntax.",
        }

    # Git conflicts
    if "merge conflict" in combined or "automatic merge failed" in combined:
        return {
            "category": "GIT_CONFLICT",
            "summary": "Git merge conflict encountered.",
            "suggested_action": "Inspect git_status and git_diff, manually resolve conflict markers, and git_stage the files.",
        }

    # Test failures
    if "assertionerror" in combined or "failures" in combined or "test failed" in combined or "failed" in stdout.lower() or "pytest" in command.lower():
        return {
            "category": "TEST_FAILURE",
            "summary": "One or more assertions failed during test execution.",
            "suggested_action": "Review failure trace, inspect implementation in active workspace, and repair failing assertions.",
        }

    # Permission errors
    if "permission denied" in combined or "access is denied" in combined or "eacces" in combined:
        return {
            "category": "PERMISSION_DENIED",
            "summary": "Filesystem or process access denied by OS.",
            "suggested_action": "Check file permissions and ensure file is not locked by another process.",
        }

    # Port conflicts
    if "address already in use" in combined or "eaddrinuse" in combined or "10048" in combined:
        return {
            "category": "PORT_IN_USE",
            "summary": "Network port is already bound by another process.",
            "suggested_action": "Select a different port or terminate the conflicting process.",
        }

    return {
        "category": "GENERAL_ERROR",
        "summary": f"Command exited with non-zero exit code ({exit_code}).",
        "suggested_action": "Review stdout and stderr output for specific error messages.",
    }


def _run_process(
    args: List[str],
    cwd: str,
    timeout: int,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Execute args as a subprocess and capture structured output."""
    start = time.perf_counter()
    effective_env = {**os.environ, **(env or {})}

    process = subprocess.Popen(
        args,
        cwd=cwd,
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        env=effective_env,
    )

    try:
        stdout, stderr = process.communicate(timeout=timeout)
        exit_code = process.returncode
        timed_out = False
    except subprocess.TimeoutExpired:
        _terminate_process_tree(process)
        stdout, stderr = process.communicate()
        exit_code = -1
        timed_out = True

    duration = round(time.perf_counter() - start, 3)
    max_bytes = settings.MAX_COMMAND_OUTPUT_BYTES

    raw_stdout = _redact_output(stdout)
    raw_stderr = _redact_output(stderr)
    stdout_truncated = len(raw_stdout) > max_bytes
    stderr_truncated = len(raw_stderr) > max_bytes

    trimmed_stdout = raw_stdout[:max_bytes]
    trimmed_stderr = raw_stderr[:max_bytes]

    diagnostics = None
    if exit_code != 0 or timed_out:
        cmd_str = " ".join(args)
        diagnostics = diagnose_command_failure(cmd_str, exit_code, trimmed_stdout, trimmed_stderr, timed_out)

    res = {
        "exit_code": exit_code,
        "duration_seconds": duration,
        "timed_out": timed_out,
        "stdout": trimmed_stdout,
        "stderr": trimmed_stderr,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
        "output_bytes": len(trimmed_stdout) + len(trimmed_stderr),
    }
    if diagnostics:
        res["diagnostics"] = diagnostics
    return res


# ---------------------------------------------------------------------------
# Public tool: run_command (upgraded)
# ---------------------------------------------------------------------------

def run_command(
    command: str,
    timeout: int = 120,
    working_directory: Optional[str] = None,
    env_vars: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Execute an approved development command in the active repository.

    In SAFE/FULL profiles, only allowlisted binaries are permitted.
    In UNRESTRICTED profile, any command may be run — use with caution.

    Parameters
    ----------
    command : str
        The command string to execute (tokenized with shlex; no shell operators).
    timeout : int
        Maximum wall-clock seconds. Capped by the active profile's limit.
    working_directory : str, optional
        Sub-path within the active repo to run from. Defaults to repo root.
    env_vars : dict, optional
        Additional environment variables merged into the process environment.
    """
    try:
        policy_engine.require_cmd_execute()

        repo_root = session_manager.get_active_repo_path()
        effective_timeout = policy_engine.effective_timeout(min(timeout, settings.COMMAND_TIMEOUT_SECONDS))

        allowed = policy_engine.effective_allowed_binaries()  # None = unrestricted

        normalized = command.strip()
        if not normalized:
            return {"error": "Command string cannot be empty."}

        # Tokenize
        try:
            args = shlex.split(normalized, posix=True)
        except ValueError as exc:
            return {"error": f"Invalid command syntax: {exc}"}

        if not args:
            return {"error": "Command is empty after parsing."}

        binary_name = Path(args[0]).name.lower()
        if binary_name.endswith(".exe"):
            binary_name = binary_name[:-4]

        # Allowlist check (skipped in unrestricted mode)
        if allowed is not None and binary_name not in allowed:
            return {
                "error": (
                    f"Binary '{binary_name}' is not in the allowed list for profile "
                    f"'{policy_engine.profile.value}'. "
                    f"Allowed: [{', '.join(sorted(allowed))}]"
                )
            }

        # Shell operator check (always enforced except unrestricted)
        if policy_engine.profile != PermissionProfile.UNRESTRICTED:
            try:
                security_engine.validate_command_security(command)
            except SecurityError as se:
                return {"error": f"Security Violation: {se}"}

        # Resolve working directory
        if working_directory:
            try:
                cwd = str(security_engine.sanitize_and_resolve_path(working_directory))
            except SecurityError as se:
                return {"error": f"Security Violation in working_directory: {se}"}
        else:
            cwd = str(repo_root)

        result = _run_process(args, cwd, effective_timeout, env_vars)
        audit.log_command(command, result["exit_code"], result["duration_seconds"], session_manager.get_active_repo_name() or "")

        return {
            "repository": session_manager.get_active_repo_name(),
            "command": command,
            "working_directory": cwd,
            "profile": policy_engine.profile.value,
            **result,
        }

    except PolicyViolation as pv:
        audit.log_permission_denied("run_command", "cmd_execute", policy_engine.profile.value)
        return {"error": f"Permission denied: {pv}"}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Convenience wrappers used by the autonomous loop
# ---------------------------------------------------------------------------

def run_tests(
    test_path: str = ".",
    framework: str = "pytest",
    extra_args: Optional[str] = None,
    timeout: int = 300,
) -> Dict[str, Any]:
    """
    Run the test suite for the active repository.

    Parameters
    ----------
    test_path : str
        Relative path to a test file or directory.
    framework : str
        Test runner: pytest, jest, mocha, vitest, cargo, go, mvn.
    extra_args : str, optional
        Additional arguments appended to the test command.
    timeout : int
        Wall-clock timeout in seconds.
    """
    RUNNERS: Dict[str, str] = {
        "pytest": "pytest",
        "jest": "npx jest",
        "mocha": "npx mocha",
        "vitest": "npx vitest run",
        "cargo": "cargo test",
        "go": "go test ./...",
        "mvn": "mvn test",
        "gradle": "gradle test",
    }
    base = RUNNERS.get(framework.lower())
    if not base:
        return {"error": f"Unknown test framework '{framework}'. Supported: {list(RUNNERS.keys())}"}

    cmd = f"{base} {test_path}"
    if extra_args:
        cmd += f" {extra_args}"
    return run_command(cmd.strip(), timeout=timeout)


def install_dependencies(
    manager: str = "pip",
    requirements_file: Optional[str] = None,
    package: Optional[str] = None,
    timeout: int = 300,
) -> Dict[str, Any]:
    """
    Install project dependencies using the specified package manager.
    Requires 'full' or 'unrestricted' profile.

    Parameters
    ----------
    manager : str
        Package manager: pip, npm, yarn, pnpm, cargo, poetry, uv.
    requirements_file : str, optional
        Path to requirements file (pip -r <file> or npm install from dir).
    package : str, optional
        Specific package to install.
    """
    try:
        policy_engine.require_cmd_install()
    except PolicyViolation as pv:
        return {"error": f"Permission denied: {pv}"}

    INSTALL_CMDS: Dict[str, str] = {
        "pip": "pip install",
        "npm": "npm install",
        "yarn": "yarn add",
        "pnpm": "pnpm add",
        "cargo": "cargo add",
        "poetry": "poetry add",
        "uv": "uv pip install",
    }
    base = INSTALL_CMDS.get(manager.lower())
    if not base:
        return {"error": f"Unknown package manager '{manager}'. Supported: {list(INSTALL_CMDS.keys())}"}

    if requirements_file:
        if manager == "pip":
            cmd = f"pip install -r {requirements_file}"
        elif manager in {"npm", "yarn", "pnpm"}:
            cmd = f"{manager} install"
        else:
            cmd = f"{base} -r {requirements_file}"
    elif package:
        cmd = f"{base} {package}"
    else:
        # Default: install from lock/requirements
        if manager == "pip":
            cmd = "pip install -r requirements.txt"
        elif manager == "npm":
            cmd = "npm install"
        elif manager in {"yarn", "pnpm"}:
            cmd = f"{manager} install"
        else:
            cmd = base

    return run_command(cmd, timeout=timeout)
