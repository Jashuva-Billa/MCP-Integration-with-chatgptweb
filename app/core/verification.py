"""Independent, evidence-producing test and lint verification."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.audit import audit

_SECRET_PATTERNS = [
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[A-Za-z0-9._~+/-]+=*"),
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)(\s*[=:]\s*)[^\s,;]+"),
    re.compile(r"\b(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
]


def _redact(text: str) -> str:
    text = _SECRET_PATTERNS[0].sub(r"\1[REDACTED]", text)
    text = _SECRET_PATTERNS[1].sub(r"\1\2[REDACTED]", text)
    return _SECRET_PATTERNS[2].sub("[REDACTED_TOKEN]", text)


def _safe_environment() -> dict[str, str]:
    keep = {"PATH", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "SYSTEMROOT",
            "WINDIR", "TEMP", "TMP", "TMPDIR", "PATHEXT", "SYSTEMDRIVE"}
    return {key: value for key, value in os.environ.items() if key.upper() in keep}


def _configured_commands() -> list[list[str]]:
    raw = getattr(settings, "MCP_VERIFICATION_COMMANDS", "") or os.getenv("MCP_VERIFICATION_COMMANDS", "")
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("MCP_VERIFICATION_COMMANDS must be a JSON array of argv arrays") from exc
        if not isinstance(data, list) or not data:
            raise ValueError("MCP_VERIFICATION_COMMANDS must be a non-empty JSON array")
        commands = data
    else:
        commands = [["python", "-m", "pytest", "-q"]]
    result: list[list[str]] = []
    for command in commands:
        if not isinstance(command, list) or not command or not all(isinstance(arg, str) for arg in command):
            raise ValueError("Each verification command must be an argv array")
        if Path(command[0]).name.lower() not in {"python", "python3", "ruff", "pytest", "mypy", "flake8"}:
            raise ValueError(f"Verification executable is not allowlisted: {command[0]}")
        result.append(command)
    return result


def _revision(root: Path) -> str | None:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root), capture_output=True,
                            text=True, timeout=10, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def _working_tree_fingerprint(root: Path) -> str | None:
    """Hash tracked and non-ignored untracked file contents, not just Git HEAD."""
    listing = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=str(root), capture_output=True, timeout=15, check=False,
    )
    if listing.returncode != 0:
        return None
    digest = hashlib.sha256()
    for raw_path in sorted(filter(None, listing.stdout.split(b"\0"))):
        relative = os.fsdecode(raw_path)
        path = root / relative
        digest.update(raw_path)
        digest.update(b"\0")
        try:
            if path.is_symlink():
                digest.update(b"SYMLINK\0")
                digest.update(os.fsencode(os.readlink(path)))
            elif path.is_file():
                digest.update(b"FILE\0")
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
            else:
                # Preserve deletions and tracked paths that are no longer regular files.
                digest.update(b"MISSING_OR_NONFILE\0")
        except OSError:
            return None
        digest.update(b"\0")
    return digest.hexdigest()


def verify_repository(root: Path | str, task_id: str = "", timeout_seconds: int = 600) -> dict[str, Any]:
    """Run trusted configured checks in a fresh process, ignoring worker-reported test claims."""
    repo = Path(root).resolve(strict=True)
    if not repo.is_dir():
        raise ValueError("Verification root must be a directory")
    timeout_seconds = max(10, min(int(timeout_seconds), 1800))
    custom_commands = bool(getattr(settings, "MCP_VERIFICATION_COMMANDS", "") or os.getenv("MCP_VERIFICATION_COMMANDS", ""))
    commands = _configured_commands()
    lint_not_applicable = False
    if not custom_commands:
        status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=str(repo),
                                capture_output=True, text=True, timeout=10, check=False)
        changed_python = []
        if status.returncode == 0:
            for line in status.stdout.splitlines():
                relative = line[3:].strip().strip(chr(34)) if len(line) > 3 else ""
                if relative.lower().endswith(".py") and relative and ".." not in Path(relative).parts:
                    changed_python.append(relative)
        if changed_python:
            commands.append(["ruff", "check", *sorted(set(changed_python))])
        else:
            lint_not_applicable = True
    env = _safe_environment()
    revision_before = _revision(repo)
    tree_before = _working_tree_fingerprint(repo)
    records: list[dict[str, Any]] = []
    started_all = time.perf_counter()
    for argv in commands:
        executable = argv[0]
        if not shutil.which(executable, path=env.get("PATH")):
            records.append({"command": argv, "status": "unavailable", "passed": False,
                            "exit_code": None, "error": f"Verification executable not found: {executable}"})
            continue
        started = time.perf_counter()
        try:
            completed = subprocess.run(argv, cwd=str(repo), env=env, capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", timeout=timeout_seconds,
                                       check=False, shell=False)
            records.append({"command": argv, "status": "passed" if completed.returncode == 0 else "failed",
                            "passed": completed.returncode == 0, "exit_code": completed.returncode,
                            "duration_seconds": round(time.perf_counter() - started, 3),
                            "stdout": _redact(completed.stdout[-12000:]), "stderr": _redact(completed.stderr[-12000:])})
        except subprocess.TimeoutExpired as exc:
            records.append({"command": argv, "status": "timed_out", "passed": False, "exit_code": None,
                            "duration_seconds": round(time.perf_counter() - started, 3),
                            "stdout": _redact(str(exc.stdout or "")[-4000:]), "stderr": _redact(str(exc.stderr or "")[-4000:])})
        except OSError as exc:
            records.append({"command": argv, "status": "error", "passed": False, "exit_code": None,
                            "error": str(exc)[:1000]})
    if lint_not_applicable:
        records.append({"command": ["ruff", "check"], "status": "skipped", "passed": True,
                        "reason": "No changed Python files were detected; Python lint is not applicable."})
    revision_after = _revision(repo)
    tree_after = _working_tree_fingerprint(repo)
    revision_stable = revision_before is not None and revision_before == revision_after
    working_tree_stable = tree_before is not None and tree_before == tree_after
    passed = bool(records) and all(item.get("passed") is True for item in records)
    evidence = {
        "evidence_id": hashlib.sha256(f"{task_id}|{revision_before}|{time.time_ns()}".encode()).hexdigest()[:16],
        "task_id": task_id, "repository_root": str(repo), "revision_before": revision_before,
        "revision_after": revision_after, "revision_stable": revision_stable,
        "working_tree_stable": working_tree_stable,
        "working_tree_fingerprint_before": tree_before, "working_tree_fingerprint_after": tree_after,
        "passed": passed and revision_stable and working_tree_stable, "checks": records,
        "duration_seconds": round(time.perf_counter() - started_all, 3),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "verification_source": "independent subprocesses; worker claims are not used",
    }
    evidence["passed"] = bool(evidence["passed"] and evidence["revision_stable"])
    evidence_dir = Path(__file__).resolve().parents[2] / "runtime" / "verification"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    with (evidence_dir / "evidence.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(evidence, ensure_ascii=False) + "\n")
    audit.log_task_event(task_id or "verification", "independent_verification_passed" if evidence["passed"] else "independent_verification_failed",
                         detail=f"evidence={evidence['evidence_id']};checks={sum(bool(x.get('passed')) for x in records)}/{len(records)}")
    return evidence
