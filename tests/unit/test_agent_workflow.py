"""
Tests for strengthened agent workflow: plan repair attempts and task verification.
"""
from app.tools import agent
from app.core.session import session_manager


def test_plan_repair_attempt():
    task = agent.create_task(
        objective="Fix authentication token expiry",
        requirements=["Refresh token automatically"],
        plan_steps=["Inspect token expiry", "Implement refresh", "Run tests"],
        max_repair_attempts=2,
    )
    task_id = task["task_id"]

    # 1. Plan repair attempt 1
    repair1 = agent.plan_repair_attempt(
        task_id=task_id,
        failing_command="pytest tests/unit/test_auth.py",
        root_cause="Token expiration timestamp was in local time instead of UTC",
        proposed_fix="Use datetime.now(timezone.utc)",
        files_to_modify=["app/auth/auth.py"],
    )
    assert repair1["repair_attempt"] == 1
    assert repair1["status"] == "repairing"
    assert repair1["exceeded"] is False

    # Check task state updated
    t_state = agent.get_task(task_id)
    assert t_state["status"] == "repairing"
    assert "app/auth/auth.py" in t_state["files_modified"]

    # 2. Plan repair attempt 2
    repair2 = agent.plan_repair_attempt(
        task_id=task_id,
        failing_command="pytest tests/unit/test_auth.py",
        root_cause="Edge case on empty token",
        proposed_fix="Add validation for empty string",
    )
    assert repair2["repair_attempt"] == 2
    assert repair2["exceeded"] is False

    # 3. Plan repair attempt 3 (exceeds max_repair_attempts=2)
    repair3 = agent.plan_repair_attempt(
        task_id=task_id,
        failing_command="pytest tests/unit/test_auth.py",
        root_cause="Another failure",
        proposed_fix="Try again",
    )
    assert repair3["repair_attempt"] == 3
    assert repair3["exceeded"] is True
    assert repair3["status"] == "failed"


def test_verify_task(test_environment, monkeypatch):
    from app.core import verification
    monkeypatch.setattr(verification, "verify_repository", lambda root, task_id, timeout_seconds=600: {
        "passed": True, "evidence_id": "verify-task-evidence", "checks": [], "revision_stable": True
    })
    session_manager.set_active_repo_name("Repo_A")
    task = agent.create_task(
        objective="Implement calculator function",
        plan_steps=["Write test", "Implement code"],
    )
    task_id = task["task_id"]

    # Mark all steps done
    agent.update_task_step(task_id, step_index=1, status="done")
    agent.update_task_step(task_id, step_index=2, status="done")

    # Mock terminal.run_command to simulate passing tests
    from app.tools import terminal
    def mock_run_command(cmd, timeout=120, working_directory=None, env_vars=None):
        return {"exit_code": 0, "stdout": "2 passed", "stderr": "", "duration_seconds": 0.2}

    monkeypatch.setattr(terminal, "run_command", mock_run_command)

    ver = agent.verify_task(task_id=task_id, test_command="pytest", auto_complete=True)
    assert ver["verified"] is True
    assert ver["tests_passed"] is True
    assert len(ver["incomplete_steps"]) == 0
    assert ver["status"] == "completed"

    final_task = agent.get_task(task_id)
    assert final_task["final_verified"] is True
    assert final_task["status"] == "completed"
