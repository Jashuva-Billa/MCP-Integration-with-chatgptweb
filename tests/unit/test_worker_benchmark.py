from __future__ import annotations

import json
import subprocess
import time
import uuid

from app.config import settings
from app.core.permissions import PermissionProfile, policy_engine
from app.core.repository import repository_manager
from app.core.session import session_manager
from app.core.worker_benchmark import get_benchmark, start_benchmark
from app.core.workstreams import workstream_manager


def test_same_case_benchmark_records_worker_diff_verification_and_unknown_cost(test_environment, tmp_path, monkeypatch):
    repo = tmp_path / "benchmark-repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Benchmark Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "benchmark@example.com"], cwd=repo, check=True)
    (repo / ".gitignore").write_text(".mcp-worktrees/\n", encoding="utf-8")
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True)

    repo_name = "Benchmark" + uuid.uuid4().hex[:6]
    repository_manager.add_repository(repo_name, str(repo), "benchmark test", True)
    previous_profile = policy_engine.profile
    old_commands = settings.MCP_WORKER_COMMANDS
    old_mode = settings.MCP_WORKER_SANDBOX_MODE
    old_allowed = settings.MCP_WORKER_HOST_MODE_ALLOWED
    old_verification = settings.MCP_VERIFICATION_COMMANDS
    from app.core import worker_benchmark
    monkeypatch.setattr(worker_benchmark, "_BENCH", tmp_path / "benchmark-output")
    monkeypatch.setattr(settings, "MCP_WORKER_COMMANDS", json.dumps({
        "python-worker": ["python", "-c", "print('benchmark worker')"]
    }))
    monkeypatch.setattr(settings, "MCP_WORKER_SANDBOX_MODE", "host")
    monkeypatch.setattr(settings, "MCP_WORKER_HOST_MODE_ALLOWED", True)
    monkeypatch.setattr(settings, "MCP_VERIFICATION_COMMANDS", json.dumps([
        ["python", "-c", "print('independent verification passed')"]
    ]))
    run_id = None
    try:
        session_manager.set_active_repo_name(repo_name)
        policy_engine.set_profile(PermissionProfile.FULL)
        started = start_benchmark(
            [{"name": "baseline-smoke", "objective": "Run a harmless worker smoke test without modifying files."}],
            workers=["python-worker"], timeout_seconds=30,
        )
        run_id = started["run_id"]
        deadline = time.monotonic() + 15
        report = get_benchmark(run_id)
        while report["status"] == "running" and time.monotonic() < deadline:
            time.sleep(0.05)
            report = get_benchmark(run_id)
        assert report["status"] == "completed"
        assert report["baseline_revision"]
        assert report["summary"]["worker_runs"] == 1
        assert report["summary"]["verified_successes"] == 1
        result = report["results"][0]["workers"][0]
        assert result["success"] is True
        assert result["verification"]["passed"] is True
        assert result["cost_usd"] is None
        assert "diff" in result and "log_path" in result
        workstream_manager.remove(result["workstream_id"])
    finally:
        session_manager.set_active_repo_name("Repo_A")
        repository_manager.remove_repository(repo_name)
        policy_engine.set_profile(previous_profile)
        settings.MCP_WORKER_COMMANDS = old_commands
        settings.MCP_WORKER_SANDBOX_MODE = old_mode
        settings.MCP_WORKER_HOST_MODE_ALLOWED = old_allowed
        settings.MCP_VERIFICATION_COMMANDS = old_verification
