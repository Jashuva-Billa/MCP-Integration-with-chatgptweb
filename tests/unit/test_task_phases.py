import pytest

from app.core.approvals import approval_manager
from app.core.task_state import TaskPhase, task_manager
from app.tools import agent


def test_task_phase_transitions_persist_and_reject_invalid_jumps(test_environment):
    task = task_manager.create_task("Exercise explicit phases", plan_steps=["plan", "implement", "test"])
    task_id = task.id
    assert task.phase == TaskPhase.PLANNING
    task_manager.transition_phase(task_id, TaskPhase.EXECUTION)
    task_manager.transition_phase(task_id, TaskPhase.TESTING)
    task_manager.transition_phase(task_id, TaskPhase.REVIEW, "evidence-123")
    refreshed = task_manager.get_task(task_id)
    assert refreshed.phase == TaskPhase.REVIEW
    assert refreshed.verification_evidence_id == "evidence-123"
    with pytest.raises(ValueError, match="Invalid task phase transition"):
        task_manager.transition_phase(task_id, TaskPhase.PLANNING)
    with pytest.raises(ValueError, match="Completion requires final_verified"):
        task_manager.transition_phase(task_id, TaskPhase.COMPLETED, "evidence-123")


def test_approval_resolution_updates_linked_task_phase(test_environment, tmp_path, monkeypatch):
    monkeypatch.setattr(approval_manager, "path", tmp_path / "approvals.json")
    task = task_manager.create_task("Approve a merge", plan_steps=["implement"])
    task_manager.transition_phase(task.id, TaskPhase.EXECUTION)
    task_manager.transition_phase(task.id, TaskPhase.TESTING)
    task_manager.transition_phase(task.id, TaskPhase.REVIEW, "review-evidence")
    requested = agent.request_approval("git_merge", "feature->main", "merge review", task_id=task.id)
    assert requested["success"] is True
    resolved = agent.resolve_approval(requested["approval"]["id"], "approved", "test-user")
    assert resolved["success"] is True
    assert task_manager.get_task(task.id).phase == TaskPhase.APPROVAL
