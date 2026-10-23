"""Configurable subprocess workers with isolated Git worktrees and cancellation."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.audit import audit
from app.core.workstreams import workstream_manager

_ROOT = Path(__file__).resolve().parents[2]
_RUNTIME = _ROOT / "runtime" / "workers"
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")
_SECRET_PATTERNS = [
    (re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[A-Za-z0-9._~+/-]+=*"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)(\s*[=:]\s*)[^\s,;]+"), r"\1\2[REDACTED]"),
    (re.compile(r"\b(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"), "[REDACTED_TOKEN]"),
]


def _redact(value: str) -> str:
    for pattern, replacement in _SECRET_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_env() -> dict[str, str]:
    """Pass only process essentials; never forward API keys or arbitrary secrets."""
    allowed = {"PATH", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "SYSTEMROOT",
               "WINDIR", "TEMP", "TMP", "TMPDIR", "PATHEXT", "SYSTEMDRIVE"}
    return {key: value for key, value in os.environ.items() if key.upper() in allowed}


class WorkerRuntimeManager:
    """Runs configured coding CLIs as separate processes in isolated worktrees."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._pool = ThreadPoolExecutor(max_workers=max(1, min(8, int(getattr(settings, "MCP_WORKER_MAX_CONCURRENCY", 3)))))
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._container_names: dict[str, str] = {}
        self._futures: dict[str, Any] = {}
        self._cancelled: set[str] = set()
        _RUNTIME.mkdir(parents=True, exist_ok=True)
        self._recover_interrupted_jobs()

    @staticmethod
    def _commands() -> dict[str, list[str]]:
        raw = getattr(settings, "MCP_WORKER_COMMANDS", "") or os.getenv("MCP_WORKER_COMMANDS", "")
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("MCP_WORKER_COMMANDS must be a JSON object mapping worker names to argv arrays") from exc
        if not isinstance(data, dict):
            raise ValueError("MCP_WORKER_COMMANDS must be a JSON object")
        result: dict[str, list[str]] = {}
        for name, argv in data.items():
            if not isinstance(name, str) or not _SAFE_NAME.fullmatch(name):
                raise ValueError("Worker names must use safe letters, digits, underscores, or hyphens")
            if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) for arg in argv):
                raise ValueError(f"Worker command for {name} must be a non-empty argv array")
            if Path(argv[0]).name.lower() in {"sh", "bash", "cmd", "cmd.exe", "powershell", "pwsh"}:
                raise ValueError("Shell interpreters are not accepted as worker executables; configure the coding CLI directly.")
            result[name] = argv
        return result

    def _read(self) -> list[dict[str, Any]]:
        path = _RUNTIME / "jobs.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _save(self, rows: list[dict[str, Any]]) -> None:
        path = _RUNTIME / "jobs.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(path)

    def _recover_interrupted_jobs(self) -> None:
        """Mark persisted processes as interrupted after a server restart; never pretend they are still running."""
        with self._lock:
            rows = self._read()
            changed = False
            for row in rows:
                if row.get("status") in {"running", "cancelling"}:
                    row.update({"status": "interrupted", "completed_at": _now(),
                                "recovery_note": "Server restarted; worker process state cannot be resumed automatically. Start a new job from the recorded baseline."})
                    changed = True
            if changed:
                self._save(rows)

    def _update(self, job_id: str, **values: Any) -> dict[str, Any]:
        with self._lock:
            rows = self._read()
            row = next((item for item in rows if item.get("job_id") == job_id), None)
            if row is None:
                raise ValueError("worker job not found")
            row.update(values, updated_at=_now())
            self._save(rows)
            return row

    def start(self, task_id: str, objective: str, workers: list[str] | None = None,
              timeout_seconds: int | None = None, repository_root: str | None = None,
              repository_name: str | None = None, expected_base_revision: str | None = None) -> dict[str, Any]:
        if not _SAFE_NAME.fullmatch(task_id or ""):
            raise ValueError("task_id must use 1-40 safe letters, digits, underscores, or hyphens")
        if not objective.strip():
            raise ValueError("objective is required")
        configured_timeout = timeout_seconds if timeout_seconds is not None else getattr(settings, "MCP_WORKER_TIMEOUT_SECONDS", 1800)
        timeout_seconds = max(30, min(int(configured_timeout), 7200))
        configured = self._commands()
        selected = workers or list(configured)
        selected = list(dict.fromkeys(selected))
        if not selected:
            raise RuntimeError("No coding worker commands configured. Set MCP_WORKER_COMMANDS with argv arrays for installed/authenticated CLIs.")
        missing = [name for name in selected if name not in configured]
        if missing:
            raise ValueError(f"Worker(s) are not configured: {', '.join(missing)}")
        if len(selected) > int(getattr(settings, "MCP_WORKER_MAX_CONCURRENCY", 3)):
            raise ValueError("Requested worker count exceeds MCP_WORKER_MAX_CONCURRENCY")
        from app.core.session import session_manager
        root = Path(repository_root or session_manager.get_active_repo_path()).resolve(strict=True)
        repo_name = repository_name or session_manager.get_active_repo_name()
        status_check = subprocess.run(["git", "status", "--porcelain"], cwd=str(root), capture_output=True, text=True, timeout=10, check=False)
        revision_check = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root), capture_output=True, text=True, timeout=10, check=False)
        if status_check.returncode != 0 or revision_check.returncode != 0:
            raise RuntimeError("Worker runtime requires a valid Git repository.")
        if status_check.stdout.strip():
            raise RuntimeError("Worker runtime requires a clean working tree so workers share a reproducible baseline.")
        base_revision = revision_check.stdout.strip()
        if expected_base_revision and base_revision != expected_base_revision:
            raise RuntimeError("Repository HEAD changed during benchmark; refusing to run against a different baseline.")
        from app.core.task_state import TaskPhase, task_manager
        linked_task = task_manager.get_task(task_id)
        if linked_task and linked_task.repository_root and Path(linked_task.repository_root).resolve() != root:
            raise ValueError("Active repository differs from the linked task repository.")
        if linked_task and linked_task.phase == TaskPhase.COMPLETED:
            raise ValueError("Cannot start coding workers for a completed task; create a new task or resume explicitly.")
        if linked_task and linked_task.phase in {TaskPhase.APPROVAL, TaskPhase.MERGING}:
            raise ValueError(f"Cannot start coding workers while task is in {linked_task.phase.value} phase.")
        job_id = uuid.uuid4().hex[:12]
        row = {"job_id": job_id, "task_id": task_id, "objective": objective[:8000],
               "repository": repo_name, "repository_root": str(root), "base_revision": base_revision,
               "workers": selected, "status": "running", "created_at": _now(), "updated_at": _now(),
               "results": [], "synthesis": None}
        with self._lock:
            rows = self._read()
            rows.append(row)
            self._save(rows)
        try:
            from app.core.task_state import TaskPhase, TaskStatus, task_manager
            task = task_manager.get_task(task_id)
            if task:
                if task.phase in {TaskPhase.PLANNING, TaskPhase.FAILED, TaskPhase.CANCELLED, TaskPhase.TESTING, TaskPhase.REVIEW}:
                    task_manager.transition_phase(task_id, TaskPhase.EXECUTION)
                task_manager.update_status(task_id, TaskStatus.RUNNING)
        except Exception as exc:
            audit.log_task_event(task_id, "worker_task_phase_update_failed", detail=str(exc)[:200])
        future = self._pool.submit(self._run_job, job_id, objective, selected, configured, timeout_seconds,
                                  str(root), repo_name, base_revision)
        with self._lock:
            self._futures[job_id] = future
        audit.log_task_event(task_id, "worker_job_started", detail=f"job={job_id};workers={','.join(selected)}")
        return {"job_id": job_id, "status": "running", "workers": selected,
                "message": "Worker job started asynchronously. Poll get_worker_job for results."}

    def _run_job(self, job_id: str, objective: str, selected: list[str],
                 commands: dict[str, list[str]], timeout_seconds: int,
                 repository_root: str, repository_name: str, base_revision: str) -> None:
        def run_one(name: str) -> dict[str, Any]:
            if job_id in self._cancelled:
                return {"worker": name, "status": "cancelled"}
            workstream = None
            process = None
            started = time.perf_counter()
            try:
                workstream = workstream_manager.create(job_id, name, base_ref=base_revision,
                                                        repository_root=repository_root, repository_name=repository_name,
                                                        parent_task_id=self.get(job_id).get("task_id"))
                path = Path(workstream["path"]).resolve()
                prompt = (
                    "You are an independent coding worker. Implement the assigned task in the current working tree. "
                    "Inspect first, make focused changes, run relevant tests, and do not commit or push. "
                    "Do not access files outside this worktree. Report files changed, commands/tests run, and any blockers.\n\n"
                    f"Task: {objective}\n\nWorktree: {path}"
                )
                argv = [arg.replace("{prompt}", prompt) for arg in commands[name]]
                sandbox_mode = str(getattr(settings, "MCP_WORKER_SANDBOX_MODE", "docker")).lower()
                if sandbox_mode == "docker":
                    if not shutil.which("docker"):
                        return {"worker": name, "status": "unavailable", "error": "Docker is required by MCP_WORKER_SANDBOX_MODE=docker.",
                                "workstream_id": workstream["id"], "path": str(path)}
                    image = str(getattr(settings, "MCP_WORKER_SANDBOX_IMAGE", "")).strip()
                    if not image:
                        return {"worker": name, "status": "unavailable", "error": "MCP_WORKER_SANDBOX_IMAGE is required.",
                                "workstream_id": workstream["id"], "path": str(path)}
                    network_mode = str(getattr(settings, "MCP_WORKER_NETWORK_MODE", "none")).lower()
                    if network_mode not in {"none", "bridge"}:
                        return {"worker": name, "status": "failed", "error": "MCP_WORKER_NETWORK_MODE must be none or bridge."}
                    container_name = f"mcpw-{job_id}-{name}"[:63]
                    self._container_names[f"{job_id}:{name}"] = container_name
                    docker_argv = ["docker", "run", "--rm", "--name", container_name,
                                   "--network", network_mode, "--memory=4g", "--cpus=2",
                                   "--pids-limit=256", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                                   "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=1g",
                                   "--tmpfs", "/root:rw,nosuid,size=256m", "--tmpfs", "/home/worker:rw,nosuid,size=256m",
                                   "--mount", f"type=bind,source={path},target=/workspace", "-w", "/workspace",
                                   "-e", f"MCP_WORKER_NAME={name}", "-e", f"MCP_WORKER_TASK_ID={job_id}"]
                    mounts_raw = str(getattr(settings, "MCP_WORKER_CREDENTIAL_MOUNTS", "") or "").strip()
                    if mounts_raw:
                        try:
                            mounts = json.loads(mounts_raw)
                        except json.JSONDecodeError as exc:
                            raise ValueError("MCP_WORKER_CREDENTIAL_MOUNTS must be a JSON array") from exc
                        if not isinstance(mounts, list):
                            raise ValueError("MCP_WORKER_CREDENTIAL_MOUNTS must be a JSON array")
                        for mount in mounts:
                            if not isinstance(mount, dict) or not isinstance(mount.get("source"), str) or not isinstance(mount.get("target"), str):
                                raise ValueError("Each credential mount needs source and target strings")
                            source = Path(mount["source"]).expanduser().resolve(strict=True)
                            repo_root = Path(repository_root).resolve()
                            home = Path.home().resolve()
                            if source == repo_root or repo_root in source.parents:
                                raise ValueError("Credential mounts must not point inside the repository")
                            if source == home or home not in source.parents:
                                raise ValueError("Credential mount sources must be narrowly scoped paths under the current user home")
                            target = mount["target"]
                            allowed_targets = {"/root/.codex", "/root/.claude", "/root/.cursor",
                                                "/home/worker/.codex", "/home/worker/.claude", "/home/worker/.cursor"}
                            if target not in allowed_targets:
                                raise ValueError("Credential mount target must be one exact Codex, Claude, or Cursor config directory")
                            docker_argv.extend(["--mount", f"type=bind,source={source},target={target},readonly"])
                    argv = docker_argv + [image] + argv
                elif sandbox_mode == "host":
                    if not bool(getattr(settings, "MCP_WORKER_HOST_MODE_ALLOWED", False)):
                        return {"worker": name, "status": "blocked", "error": "Host execution is disabled. Set MCP_WORKER_HOST_MODE_ALLOWED=true only for a trusted local development machine.",
                                "workstream_id": workstream["id"], "path": str(path)}
                    if not argv or not shutil.which(argv[0]):
                        return {"worker": name, "status": "unavailable", "error": f"Configured executable not found: {argv[0] if argv else 'unknown'}",
                                "workstream_id": workstream["id"], "path": str(path)}
                else:
                    return {"worker": name, "status": "failed", "error": "MCP_WORKER_SANDBOX_MODE must be docker or host."}
                log_dir = _RUNTIME / job_id
                log_dir.mkdir(parents=True, exist_ok=True)
                log_path = log_dir / f"{name}.log"
                env = _safe_env()
                env["MCP_WORKER_NAME"] = name
                env["MCP_WORKER_TASK_ID"] = job_id
                if job_id in self._cancelled:
                    return {"worker": name, "status": "cancelled", "workstream_id": workstream["id"], "path": str(path)}
                process = subprocess.Popen(argv, cwd=str(path), env=env, stdin=subprocess.DEVNULL,
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                           encoding="utf-8", errors="replace", shell=False)
                with self._lock:
                    self._processes[f"{job_id}:{name}"] = process
                if job_id in self._cancelled and process.poll() is None:
                    process.terminate()
                try:
                    output, _ = process.communicate(timeout=timeout_seconds)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        output, _ = process.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        output, _ = process.communicate()
                    status = "timed_out"
                else:
                    status = "completed" if process.returncode == 0 else "failed"
                if job_id in self._cancelled:
                    status = "cancelled"
                output = _redact(output or "")
                log_path.write_text(output[-200000:], encoding="utf-8")
                changed = subprocess.run(["git", "status", "--short"], cwd=str(path), capture_output=True,
                                         text=True, timeout=15, check=False).stdout
                diff = _redact(subprocess.run(["git", "diff", "--no-ext-diff", "--", "."], cwd=str(path),
                                      capture_output=True, text=True, timeout=30, check=False).stdout)
                result = {"worker": name, "status": status, "exit_code": process.returncode,
                          "duration_seconds": round(time.perf_counter() - started, 3),
                          "workstream_id": workstream["id"], "path": str(path), "branch": workstream["branch"],
                          "log_path": str(log_path), "output_tail": output[-6000:],
                          "changed_files": changed[:12000], "diff": diff[:100000]}
                audit.log_task_event(job_id, "worker_finished", detail=f"worker={name};status={status};exit={process.returncode}")
                return result
            except Exception as exc:
                return {"worker": name, "status": "failed", "error": str(exc)[:1000],
                        "duration_seconds": round(time.perf_counter() - started, 3),
                        "workstream_id": (workstream or {}).get("id")}
            finally:
                with self._lock:
                    self._processes.pop(f"{job_id}:{name}", None)
                    self._container_names.pop(f"{job_id}:{name}", None)

        results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=len(selected), thread_name_prefix="mcp-code-worker") as pool:
            futures = [pool.submit(run_one, name) for name in selected]
            for future in futures:
                try:
                    results.append(future.result())
                except Exception as exc:
                    results.append({"status": "failed", "error": str(exc)[:1000]})
        successful = [item for item in results if item.get("status") == "completed"]
        synthesis = {
            "summary": f"{len(successful)} of {len(results)} coding workers completed successfully.",
            "worker_results": [{"worker": item.get("worker"), "status": item.get("status"),
                                "changed_files": item.get("changed_files", ""), "output_summary": item.get("output_tail", "")[-2500:],
                                "error": item.get("error")} for item in results],
            "merge_policy": "No automatic merge. Review each diff, run independent verification, and request exact-target merge approval.",
            "synthesis_mode": "structured_fallback",
        }
        try:
            from app.core.orchestrator import OpenAICompatibleProvider
            provider = OpenAICompatibleProvider(timeout=60)
            if bool(getattr(settings, "MCP_WORKER_SYNTHESIS_ENABLED", False)) and provider.model:
                synthesis_result = provider.complete([
                    {"role": "system", "content": "Synthesize independent coding-worker results. Return JSON with summary, consensus, disagreements, risks, and recommended_next_steps. Do not claim tests passed unless independent evidence exists."},
                    {"role": "user", "content": json.dumps({"objective": objective, "workers": synthesis["worker_results"]}, ensure_ascii=False)[:18000]},
                ], role="worker_synthesis")
                synthesis["model_synthesis"] = synthesis_result.get("content")
                synthesis["synthesis_model"] = synthesis_result.get("model")
                synthesis["synthesis_cost_usd"] = synthesis_result.get("cost_usd")
                synthesis["synthesis_mode"] = "configured_model"
        except Exception as exc:
            synthesis["synthesis_note"] = f"Model synthesis unavailable; structured worker results retained ({type(exc).__name__})."
        status = "cancelled" if job_id in self._cancelled else (
            "completed" if results and all(item.get("status") == "completed" for item in results)
            else "partial" if successful else "failed"
        )
        self._update(job_id, status=status, results=results, synthesis=synthesis, completed_at=_now())
        linked_task_id = self.get(job_id).get("task_id", "")
        try:
            from app.core.task_state import TaskPhase, task_manager
            task = task_manager.get_task(linked_task_id)
            if task:
                if status == "cancelled":
                    if task.phase not in {TaskPhase.COMPLETED, TaskPhase.CANCELLED, TaskPhase.FAILED}:
                        task_manager.transition_phase(linked_task_id, TaskPhase.CANCELLED)
                    task_manager.cancel_task(linked_task_id)
                elif task.phase == TaskPhase.EXECUTION:
                    task_manager.transition_phase(linked_task_id, TaskPhase.REVIEW)
                elif task.phase == TaskPhase.TESTING:
                    task_manager.transition_phase(linked_task_id, TaskPhase.REVIEW)
        except Exception as exc:
            audit.log_task_event(linked_task_id or job_id, "worker_task_phase_update_failed", detail=str(exc)[:200])
        audit.log_task_event(job_id, "worker_job_finished", detail=f"status={status};successful={len(successful)}/{len(results)}")

    def get(self, job_id: str) -> dict[str, Any]:
        row = next((item for item in self._read() if item.get("job_id") == job_id), None)
        if row is None:
            raise ValueError("worker job not found")
        return row

    def list(self, task_id: str | None = None) -> list[dict[str, Any]]:
        rows = self._read()
        return [row for row in reversed(rows) if task_id is None or row.get("task_id") == task_id]

    def cancel(self, job_id: str) -> dict[str, Any]:
        row = self.get(job_id)
        if row.get("status") not in {"running", "cancelling"}:
            raise ValueError(f"Cannot cancel worker job in status {row.get('status')}")
        self._cancelled.add(job_id)
        self._update(job_id, status="cancelling", cancellation_requested_at=_now())
        with self._lock:
            processes = [(key, process) for key, process in self._processes.items() if key.startswith(job_id + ":")]
            containers = [name for key, name in self._container_names.items() if key.startswith(job_id + ":")]
        for container in containers:
            if shutil.which("docker"):
                try:
                    subprocess.run(["docker", "stop", "--time", "3", container], capture_output=True,
                                   text=True, timeout=8, check=False)
                except (OSError, subprocess.TimeoutExpired):
                    pass
        for _, process in processes:
            if process.poll() is None:
                process.terminate()
        audit.log_task_event(job_id, "worker_cancel_requested")
        return {"job_id": job_id, "status": "cancelling", "terminated_processes": len(processes)}


worker_runtime = WorkerRuntimeManager()
