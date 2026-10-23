"""
Tests for agent tools: permissions, skills, hooks, and task management.
"""
from app.tools import agent
from app.core.permissions import PermissionProfile, policy_engine


def test_permission_profile_tools():
    # Check default describe
    info = agent.get_permission_profile()
    assert "permission_profile" in info
    assert "profile" in info["permission_profile"]

    # Switch to full
    res = agent.set_permission_profile("full")
    assert res["success"] is True
    assert res["active_profile"] == "full"
    assert policy_engine.profile == PermissionProfile.FULL

    # Switch to unrestricted
    res = agent.set_permission_profile("unrestricted")
    assert res["success"] is True
    assert "warning" in res

    # Switch back to safe
    res = agent.set_permission_profile("safe")
    assert res["success"] is True
    assert res["active_profile"] == "safe"

    # Invalid profile
    err = agent.set_permission_profile("invalid_xyz")
    assert "error" in err


def test_skills_tools():
    skills_list = agent.list_skills()
    assert "skills" in skills_list
    assert skills_list["total"] >= 1

    # Get skill content
    skill_name = skills_list["skills"][0]["name"]
    skill_info = agent.get_skill(skill_name)
    assert skill_info["name"] == skill_name
    assert "content" in skill_info

    # Non-existent skill
    missing = agent.get_skill("non_existent_skill_xyz")
    assert "error" in missing
    assert "available" in missing

    # Reload skills
    reload_res = agent.reload_skills()
    assert reload_res["success"] is True
    assert reload_res["total_skills"] >= 1


def test_prepare_task_workflow_selects_skills_and_superpowers():
    result = agent.prepare_task_workflow(
        "Debug the MCP server authentication bug, add regression tests, and inspect the git diff",
        ["app/main.py", "tests/unit/test_auth.py"],
    )
    assert result["selected_skills"]
    names = {item["name"] for item in result["selected_skills"]}
    assert "security-review" in names
    assert "testing-tdd" in names
    powers = {item["name"] for item in result["selected_superpowers"]}
    assert {"repository_intelligence", "safe_editing", "test_and_diagnose", "security_controls"} <= powers
    assert result["execution_protocol"]


def test_hooks_tools():
    hooks = agent.list_hooks()
    assert "hooks" in hooks
    assert "total" in hooks

    # Fire a non-existent or empty hook event gracefully
    res = agent.fire_hook("after_task_complete", {"task_id": "test-123"})
    assert "hooks_fired" in res
    assert res["event"] == "after_task_complete"


def test_task_state_lifecycle():
    # 1. Create task
    task = agent.create_task(
        objective="Refactor auth middleware to support bearer tokens",
        requirements=["Pass all unit tests", "Do not break existing sessions"],
        plan_steps=["Analyze codebase", "Update middleware", "Run tests"],
        max_repair_attempts=3,
    )
    assert "task_id" in task
    assert task["objective"] == "Refactor auth middleware to support bearer tokens"
    assert len(task["plan"]) == 3
    task_id = task["task_id"]

    # 2. Get task
    fetched = agent.get_task(task_id)
    assert fetched["id"] == task_id
    assert fetched["status"] == "pending"

    # 3. List tasks
    all_tasks = agent.list_tasks()
    assert all_tasks["total"] >= 1
    assert any(t["id"] == task_id for t in all_tasks["tasks"])

    # 4. Update task step
    step_res = agent.update_task_step(task_id, step_index=1, status="done", result="Analysis completed")
    assert step_res["success"] is True

    # 5. Record test result
    test_res = agent.record_test_result(
        task_id=task_id,
        command="pytest tests/unit/test_auth.py",
        exit_code=0,
        duration_seconds=0.45,
        stdout="All tests passed",
    )
    assert test_res["test_passed"] is True
    assert test_res["task_id"] == task_id

    # 6. Add task issue
    issue_res = agent.add_task_issue(task_id, "Edge case: empty authorization header")
    assert issue_res["success"] is True
    assert issue_res["issue"] == "Edge case: empty authorization header"

    # 7. Complete task
    comp_res = agent.complete_task(task_id, verified=True)
    assert comp_res["success"] is True
    assert comp_res["verified"] is True

    # 8. Verify final task state
    final_task = agent.get_task(task_id)
    assert final_task["status"] == "completed"
    assert final_task["final_verified"] is True
    assert len(final_task["outstanding_issues"]) == 1


def test_chatgpt_web_task_needs_no_api_provider():
    result = agent.start_chatgpt_coding_task(
        objective="Inspect the parser and add a regression test",
        requirements=["The parser regression is covered"],
        plan_steps=["Inspect parser", "Implement regression test", "Run tests", "Review diff"],
        max_repair_attempts=2,
    )
    assert result["task_id"]
    assert result["api_key_required"] is False
    assert result["model_provider"] == "connected ChatGPT Web session"
    assert len(result["plan"]) == 4
    assert "ChatGPT Web performs reasoning" in result["important_boundary"]


def test_chatgpt_web_progress_persists_test_failures_and_repairs():
    started = agent.start_chatgpt_coding_task(
        objective="Fix a regression", plan_steps=["Inspect", "Fix", "Test"], max_repair_attempts=2
    )
    task_id = started["task_id"]
    result = agent.record_chatgpt_task_progress(
        task_id, step_index=1, status="done", result="Inspected failing test",
        test_command="pytest tests/unit/test_parser.py -q", test_exit_code=1,
        test_stdout="1 failed", repair_note="Parser rejects empty token",
    )
    assert result["success"] is True
    assert result["status"] == "repairing"
    assert result["repair_attempts"] == 1
    assert agent.get_task(task_id)["test_runs"][-1]["passed"] is False


def test_chatgpt_web_finish_requires_completed_plan_and_passing_tests(monkeypatch):
    from app.tools import terminal

    started = agent.start_chatgpt_coding_task(
        objective="Fix a regression", plan_steps=["Inspect", "Fix", "Test"]
    )
    task_id = started["task_id"]
    for index in (1, 2, 3):
        agent.record_chatgpt_task_progress(task_id, index, "done", f"Step {index} completed")

    monkeypatch.setattr(terminal, "run_command", lambda command: {
        "exit_code": 0, "stdout": "3 passed", "stderr": "", "duration_seconds": 0.1
    })
    result = agent.finish_chatgpt_coding_task(task_id, "Fixed and tested", "pytest -q")
    assert result["success"] is True
    assert result["verified"] is True
    assert agent.get_task(task_id)["status"] == "completed"
