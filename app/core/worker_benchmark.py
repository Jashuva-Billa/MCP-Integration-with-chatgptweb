"""Same-case benchmark runner for configured local coding-agent CLIs."""
from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.session import session_manager
from app.core.verification import verify_repository
from app.core.worker_runtime import worker_runtime

_ROOT = Path(__file__).resolve().parents[2]
_BENCH = _ROOT / "runtime" / "worker_benchmarks"
_LOCK = threading.RLock()
_THREADS: dict[str, threading.Thread] = {}


def _read() -> list[dict[str, Any]]:
    path = _BENCH / "runs.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save(rows: list[dict[str, Any]]) -> None:
    _BENCH.mkdir(parents=True, exist_ok=True)
    path = _BENCH / "runs.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def _update(run_id: str, **values: Any) -> None:
    with _LOCK:
        rows = _read()
        row = next((item for item in rows if item["run_id"] == run_id), None)
        if row:
            row.update(values, updated_at=datetime.now(timezone.utc).isoformat())
            _save(rows)


def start_benchmark(cases: list[dict[str, Any]], workers: list[str] | None = None,
                    timeout_seconds: int | None = None) -> dict[str, Any]:
    if not cases or len(cases) > 20:
        raise ValueError("Provide 1-20 benchmark cases")
    if any(not isinstance(case, dict) or not str(case.get("objective", "")).strip() for case in cases):
        raise ValueError("Every benchmark case must contain a non-empty objective")
    configured_timeout = timeout_seconds if timeout_seconds is not None else getattr(settings, "MCP_WORKER_TIMEOUT_SECONDS", 1800)
    timeout_seconds = max(30, min(int(configured_timeout), 7200))
    root = Path(session_manager.get_active_repo_path()).resolve()
    import subprocess
    baseline = subprocess.run(["git", "status", "--porcelain"], cwd=str(root), capture_output=True, text=True, timeout=10)
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root), capture_output=True, text=True, timeout=10)
    if baseline.returncode or baseline.stdout.strip():
        raise ValueError("Benchmark requires a clean working tree so all workers start from the same baseline")
    if revision.returncode:
        raise ValueError("Could not resolve benchmark baseline revision")
    run_id = uuid.uuid4().hex[:12]
    row = {"run_id": run_id, "repository": session_manager.get_active_repo_name(),
           "repository_root": str(root), "baseline_revision": revision.stdout.strip(),
           "cases": cases, "workers": workers or [], "status": "running", "results": [],
           "created_at": datetime.now(timezone.utc).isoformat()}
    with _LOCK:
        rows = _read()
        rows.append(row)
        _save(rows)
    thread = threading.Thread(target=_run, args=(run_id, cases, workers, timeout_seconds, str(root), row["repository"], row["baseline_revision"]), daemon=True,
                              name=f"mcp-benchmark-{run_id}")
    _THREADS[run_id] = thread
    thread.start()
    return {"run_id": run_id, "status": "running", "baseline_revision": row["baseline_revision"],
            "cases": len(cases), "workers": workers or [], "message": "Benchmark started; poll get_worker_benchmark."}


def _run(run_id: str, cases: list[dict[str, Any]], workers: list[str] | None, timeout_seconds: int,
         repository_root: str, repository_name: str, baseline_revision: str) -> None:
    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases, 1):
        case_id = f"b{run_id[:8]}c{index}"
        started = time.perf_counter()
        try:
            job = worker_runtime.start(case_id, str(case["objective"]), workers, timeout_seconds,
                                       repository_root=repository_root, repository_name=repository_name,
                                       expected_base_revision=baseline_revision)
            deadline = time.monotonic() + max(60, min(timeout_seconds + 60, 7260))
            while time.monotonic() < deadline:
                state = worker_runtime.get(job["job_id"])
                if state.get("status") not in {"running", "cancelling"}:
                    break
                time.sleep(0.5)
            else:
                worker_runtime.cancel(job["job_id"])
                state = worker_runtime.get(job["job_id"])
            worker_results = []
            for item in state.get("results", []):
                workstream_id = item.get("workstream_id")
                evidence = None
                if item.get("status") == "completed" and item.get("path") and Path(item["path"]).is_dir():
                    try:
                        evidence = verify_repository(item["path"], task_id=f"{case_id}-{item.get('worker','worker')}",
                                                     timeout_seconds=timeout_seconds)
                    except Exception as exc:
                        evidence = {"passed": False, "error": str(exc)[:1000]}
                worker_results.append({
                    "agent": item.get("worker"), "status": item.get("status"),
                    "success": item.get("status") == "completed" and bool(evidence and evidence.get("passed")),
                    "latency_seconds": item.get("duration_seconds"), "cost_usd": None,
                    "exit_code": item.get("exit_code"), "workstream_id": workstream_id,
                    "branch": item.get("branch"), "path": item.get("path"),
                    "changed_files": item.get("changed_files", ""), "diff": item.get("diff", ""),
                    "log_path": item.get("log_path"), "output_tail": item.get("output_tail", ""),
                    "verification": evidence,
                })
            results.append({"case_name": str(case.get("name") or f"case-{index}"),
                            "objective": case["objective"], "job_id": job["job_id"],
                            "status": state.get("status"), "latency_seconds": round(time.perf_counter()-started, 3),
                            "workers": worker_results})
        except Exception as exc:
            results.append({"case_name": str(case.get("name") or f"case-{index}"), "status": "failed",
                            "error": str(exc)[:2000], "latency_seconds": round(time.perf_counter()-started, 3)})
        _update(run_id, results=results)
    successful = sum(1 for case in results for worker in case.get("workers", []) if worker.get("success"))
    total = sum(len(case.get("workers", [])) for case in results)
    _update(run_id, status="completed", results=results,
            summary={"cases": len(cases), "worker_runs": total, "verified_successes": successful,
                     "success_rate": round(successful/total, 4) if total else 0.0,
                     "cost_note": "Cost is null unless a provider/CLI exposes reliable cost metadata.",
                     "fairness_note": "All workers start from the same clean base revision in separate worktrees; no worker branch is auto-merged."},
            completed_at=datetime.now(timezone.utc).isoformat())


def get_benchmark(run_id: str) -> dict[str, Any]:
    rows = _read()
    row = next((item for item in rows if item.get("run_id") == run_id), None)
    if row is None:
        raise ValueError("benchmark run not found")
    if row.get("status") == "running" and run_id not in _THREADS:
        row.update({"status": "interrupted", "recovery_note": "Server restarted; rerun this benchmark to continue."})
        _save(rows)
    return row


def list_benchmarks(limit: int = 50) -> dict[str, Any]:
    rows = _read()
    changed = False
    for row in rows:
        if row.get("status") == "running" and row.get("run_id") not in _THREADS:
            row.update({"status": "interrupted", "recovery_note": "Server restarted; rerun this benchmark to continue."})
            changed = True
    if changed:
        _save(rows)
    return {"total": len(rows), "runs": list(reversed(rows[-max(1, min(limit, 200)):]))}
