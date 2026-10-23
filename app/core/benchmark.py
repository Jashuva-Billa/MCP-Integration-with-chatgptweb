"""Repeatable coding-task benchmark and provider-comparison reports."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.core.orchestrator import orchestrator
from app.core.session import session_manager
from app.tools.terminal import run_command

_BENCH_DIR = Path(__file__).resolve().parents[2] / "runtime" / "benchmarks"
_BENCH_FILE = _BENCH_DIR / "runs.jsonl"


def _append(record: dict[str, Any]) -> None:
    _BENCH_DIR.mkdir(parents=True, exist_ok=True)
    with _BENCH_FILE.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def run_coding_benchmark(
    cases: list[dict[str, Any]],
    max_steps: int = 25,
    max_repair_attempts: int = 3,
    include_parallel_reviews: bool = False,
    external_results: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Run cases against the configured provider and optionally compare external agent results.

    Each case: {name, objective, requirements?, plan_steps?, baseline_test_command?,
    test_command?}. External results should use {agent, case_name, success, regression?,
    repair_attempts?, tool_failures?, latency_seconds?, cost_usd?}.
    """
    if not cases:
        return {"error": "Provide at least one benchmark case."}
    if len(cases) > 50:
        return {"error": "At most 50 benchmark cases can run per invocation."}
    repo = session_manager.get_active_repo_name() or "unknown"
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + str(time.time_ns())[-6:]
    records: list[dict[str, Any]] = []
    for case in cases:
        name = str(case.get("name", "unnamed"))[:120]
        objective = str(case.get("objective", "")).strip()
        if not objective:
            records.append({"case_name": name, "success": False, "error": "objective is required"})
            continue
        baseline_command = case.get("baseline_test_command")
        baseline = run_command(str(baseline_command)) if baseline_command else None
        baseline_passed = baseline.get("exit_code") == 0 if baseline else None
        started = time.perf_counter()
        result = orchestrator.run(
            objective=objective,
            requirements=list(case.get("requirements") or []),
            plan_steps=list(case.get("plan_steps") or []),
            max_steps=max_steps,
            max_repair_attempts=max_repair_attempts,
            run_parallel_reviews=include_parallel_reviews,
        )
        final_command = case.get("test_command")
        final_test = run_command(str(final_command)) if final_command else None
        final_passed = final_test.get("exit_code") == 0 if final_test else None
        metrics = result.get("metrics") or {}
        record = {
            "run_id": run_id, "agent": "MCP autonomous orchestrator", "case_name": name,
            "repository": repo, "objective": objective, "success": bool(result.get("verified")) and final_passed is not False,
            "status": result.get("status"), "regression": bool(baseline_passed and final_passed is False),
            "baseline_test_passed": baseline_passed, "final_test_passed": final_passed,
            "repair_attempts": metrics.get("repair_attempts", 0),
            "tool_failures": metrics.get("tool_failures", 0),
            "latency_seconds": round(time.perf_counter() - started, 4),
            "model_latency_seconds": metrics.get("latency_seconds", 0),
            "prompt_tokens": metrics.get("prompt_tokens", 0),
            "completion_tokens": metrics.get("completion_tokens", 0),
            "cost_usd": metrics.get("cost_usd"), "task_id": result.get("task_id"),
            "error": result.get("error"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        records.append(record)
        _append(record)

    local = _aggregate("MCP autonomous orchestrator", records)
    comparisons = [local]
    if external_results:
        normalized_external = []
        for item in external_results:
            external = {**item, "run_id": run_id,
                        "agent": str(item.get("agent", "external")),
                        "case_name": str(item.get("case_name", "unnamed")),
                        "timestamp": item.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                        "repository": repo, "external_result": True}
            normalized_external.append(external)
            _append(external)
        names = sorted({str(item["agent"]) for item in normalized_external})
        for agent_name in names:
            comparisons.append(_aggregate(agent_name, [x for x in normalized_external if x["agent"] == agent_name]))
    return {"run_id": run_id, "repository": repo, "case_count": len(cases),
            "results": records, "comparison": comparisons,
            "note": "Cost is null unless supplied by a provider. For fair Claude Code comparisons, run the same cases and record its outcomes in external_results."}


def _aggregate(agent: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    if not total:
        return {"agent": agent, "cases": 0}
    return {
        "agent": agent, "cases": total,
        "success_rate": round(sum(bool(r.get("success")) for r in records) / total, 4),
        "regression_rate": round(sum(bool(r.get("regression")) for r in records) / total, 4),
        "mean_repair_attempts": round(sum(float(r.get("repair_attempts") or 0) for r in records) / total, 3),
        "mean_tool_failures": round(sum(float(r.get("tool_failures") or 0) for r in records) / total, 3),
        "mean_latency_seconds": round(sum(float(r.get("latency_seconds") or 0) for r in records) / total, 3),
        "known_cost_usd": round(sum(float(r.get("cost_usd") or 0) for r in records), 6)
            if all(r.get("cost_usd") is not None for r in records) else None,
    }


def get_benchmark_report(limit: int = 100) -> dict[str, Any]:
    if not _BENCH_FILE.is_file():
        return {"total_runs": 0, "records": [], "summary": []}
    rows = []
    for line in _BENCH_FILE.read_text(encoding="utf-8").splitlines()[-max(1, min(limit, 1000)):]:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row.get("agent", "unknown")), []).append(row)
    summaries = [_aggregate(name, items) for name, items in sorted(groups.items())]
    return {"total_runs": len(rows), "records": rows, "summary": summaries}


def record_external_benchmark_result(
    case_name: str,
    agent_name: str,
    success: bool,
    baseline_test_passed: Optional[bool] = None,
    final_test_passed: Optional[bool] = None,
    repair_attempts: int = 0,
    tool_failures: int = 0,
    latency_seconds: float = 0.0,
    cost_usd: Optional[float] = None,
    repository_revision: Optional[str] = None,
    notes: str = "",
) -> dict[str, Any]:
    """Record a ChatGPT Web or Claude Code run without requiring an LLM API."""
    if not case_name.strip() or not agent_name.strip():
        return {"error": "case_name and agent_name must not be empty."}
    if repair_attempts < 0 or tool_failures < 0 or latency_seconds < 0:
        return {"error": "repair_attempts, tool_failures, and latency_seconds must be non-negative."}
    if cost_usd is not None and cost_usd < 0:
        return {"error": "cost_usd must be non-negative or null."}
    record = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + str(time.time_ns())[-6:],
        "agent": agent_name.strip(), "case_name": case_name.strip(),
        "repository": session_manager.get_active_repo_name() or "unknown",
        "repository_revision": repository_revision,
        "success": bool(success),
        "baseline_test_passed": baseline_test_passed,
        "final_test_passed": final_test_passed,
        "regression": bool(baseline_test_passed is True and final_test_passed is False),
        "repair_attempts": repair_attempts, "tool_failures": tool_failures,
        "latency_seconds": round(float(latency_seconds), 4), "cost_usd": cost_usd,
        "notes": notes[:2000], "external_result": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _append(record)
    return {"success": True, "record": record,
            "note": "Use the same case, repository revision, and test commands for each agent. Cost remains unknown unless you supply it."}
