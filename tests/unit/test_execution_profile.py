"""Tests for the configurable autonomy/execution profile."""
import json

import pytest

from app.core.execution_profile import ExecutionProfileManager
from app.tools import agent


def test_default_profile_matches_requested_configuration(tmp_path):
    manager = ExecutionProfileManager(tmp_path / "profile.json")
    profile = manager.get()
    assert profile["autonomy"] == "maximum"
    assert profile["auto_skill_selection"] is True
    assert profile["self_healing"] is True
    assert profile["parallel_agents"] is True
    assert profile["git_delivery"] == "requested"
    assert profile["destructive_policy"] == "checkpoint"
    assert profile["parallel_agent_runtime_available"] is True
    assert profile["isolated_worktree_agent_runtime_available"] is False


def test_profile_updates_are_persistent_and_partial(tmp_path):
    path = tmp_path / "profile.json"
    manager = ExecutionProfileManager(path)
    updated = manager.update({"max_repair_attempts": 7, "parallel_workstream_limit": 4})
    assert updated["max_repair_attempts"] == 7
    assert updated["parallel_workstream_limit"] == 4
    assert updated["autonomy"] == "maximum"
    assert json.loads(path.read_text(encoding="utf-8"))["max_repair_attempts"] == 7

    reloaded = ExecutionProfileManager(path)
    assert reloaded.get()["max_repair_attempts"] == 7
    assert reloaded.get()["parallel_workstream_limit"] == 4


@pytest.mark.parametrize("updates", [
    {"autonomy": "godmode"},
    {"git_delivery": "always"},
    {"destructive_policy": "ignore"},
    {"self_healing": "yes"},
    {"max_repair_attempts": 100},
    {"parallel_workstream_limit": 0},
    {"unknown_option": True},
])
def test_invalid_profile_updates_are_rejected(tmp_path, updates):
    manager = ExecutionProfileManager(tmp_path / "profile.json")
    with pytest.raises(ValueError):
        manager.update(updates)


def test_workflow_includes_execution_profile_and_checkpoint_policy():
    result = agent.prepare_task_workflow(
        "Implement autonomous execution profile with tests, checkpoint risky changes, and repair failures"
    )
    assert result["execution_profile"]["autonomy"] == "maximum"
    assert any("checkpoint" in step for step in result["execution_protocol"])
    assert any("repair" in step for step in result["execution_protocol"])
