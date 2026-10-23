"""
Agent tools: permissions, profiles, skills, hooks, persistent tasks, and autonomous orchestration.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.audit import audit
from app.core.approvals import approval_manager
from app.core.execution_profile import execution_profile
from app.core.hooks import hooks_engine
from app.core.permissions import PermissionProfile, policy_engine
from app.core.skills import skills_engine
from app.core.task_state import TaskPhase, TaskStatus, TestRun, task_manager


def _verification_root(task_id: str = "") -> Path:
    from app.core.session import session_manager
    active_root = Path(session_manager.get_active_repo_path()).resolve(strict=True)
    task = task_manager.get_task(task_id) if task_id else None
    if task and task.repository_root:
        recorded_root = Path(task.repository_root).resolve(strict=True)
        if active_root != recorded_root:
            raise ValueError("Active repository differs from the task's recorded repository. Re-select the original repository before continuing.")
        return recorded_root
    return active_root


def get_permission_profile() -> Dict[str, Any]:
    return {
        "permission_profile": policy_engine.describe(),
        "note": "Permissions remain the enforcement layer; autonomy settings do not bypass them.",
    }


def set_permission_profile(profile: str) -> Dict[str, Any]:
    try:
        selected = PermissionProfile(profile.lower())
        policy_engine.set_profile(selected)
        audit.log_tool("set_permission_profile", {"profile": profile}, success=True)
        result = {"success": True, "active_profile": selected.value, "capabilities": policy_engine.describe()}
        if selected == PermissionProfile.UNRESTRICTED:
            result["warning"] = "UNRESTRICTED mode permits arbitrary commands and broad filesystem operations. Do not expose this server publicly."
        return result
    except ValueError:
        return {"error": f"Unknown profile '{profile}'. Valid: safe, full, trusted_admin, unrestricted."}


def get_execution_profile() -> Dict[str, Any]:
    return {"execution_profile": execution_profile.get()}


def configure_execution_profile(
    autonomy: Optional[str] = None, auto_skill_selection: Optional[bool] = None,
    self_healing: Optional[bool] = None, parallel_agents: Optional[bool] = None,
    git_delivery: Optional[str] = None, destructive_policy: Optional[str] = None,
    max_repair_attempts: Optional[int] = None, parallel_workstream_limit: Optional[int] = None,
) -> Dict[str, Any]:
    updates = {k: v for k, v in locals().items() if v is not None}
    try:
        profile = execution_profile.update(updates)
        audit.log_tool("configure_execution_profile", updates, success=True)
        return {"success": True, "execution_profile": profile}
    except ValueError as exc:
        return {"error": str(exc)}


def prepare_task_workflow(task: str, file_paths: Optional[List[str]] = None) -> Dict[str, Any]:
    profile = execution_profile.get()
    selected = skills_engine.select_for_task(task, file_paths or []) if profile["auto_skill_selection"] else []
    powers = [
        {"name": "repository_intelligence", "reason": "Inspect repository structure, history, symbols, and existing changes before editing."},
        {"name": "safe_editing", "reason": "Use precise edits and create recoverable checkpoints before modifications."},
        {"name": "test_and_diagnose", "reason": "Run focused tests, diagnose failures, and repair within a bounded budget."},
        {"name": "security_controls", "reason": "Respect permission policy, secret protections, and destructive-operation safeguards."},
        {"name": "parallel_review", "reason": "Run independent security, code, and test reviews concurrently when a model provider is configured."},
    ]
    protocol = [
        "Inspect repository state and relevant source files before making changes.",
        f"Create a checkpoint before each orchestrator-managed file edit (policy: {profile['destructive_policy']}).",
        f"Run validation hooks and relevant tests after changes; allow at most {profile['max_repair_attempts']} repair attempts.",
        "Inspect the resulting diff and report any failed acceptance criteria explicitly.",
        "Never commit or push unless requested; permission policy is authoritative.",
    ]
    if profile["parallel_agents"]:
        protocol.append(f"Run up to {profile['parallel_workstream_limit']} independent review workstreams concurrently when provider configuration is available.")
    return {
        "task": task, "selected_skills": selected, "selected_superpowers": powers,
        "execution_protocol": protocol, "execution_profile": profile,
    }


def list_skills(tag: Optional[str] = None) -> Dict[str, Any]:
    skills = skills_engine.list_skills(tag=tag)
    return {"total": len(skills), "skills": skills, "usage": "Call get_skill(name=<name>) to read full instructions."}


def get_skill(name: str) -> Dict[str, Any]:
    content = skills_engine.get_skill_content(name)
    if content is None:
        return {"error": f"Skill '{name}' not found.", "available": [s["name"] for s in skills_engine.list_skills()]}
    skill = skills_engine.get_skill(name)
    return {"name": name, "description": skill.description if skill else "", "content": content}


def reload_skills() -> Dict[str, Any]:
    skills_engine.reload()
    skills = skills_engine.list_skills()
    return {"success": True, "total_skills": len(skills), "skills": skills}


def list_hooks() -> Dict[str, Any]:
    hooks = hooks_engine.list_hooks()
    return {"total": len(hooks), "hooks": hooks}


def fire_hook(event: str, context: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    try:
        results = hooks_engine.fire(event, context or {})
        return {"event": event, "hooks_fired": len(results), "results": results}
    except Exception as exc:
        return {"event": event, "hooks_fired": 0, "error": str(exc)}


def create_task(objective: str, requirements: Optional[List[str]] = None,
                plan_steps: Optional[List[str]] = None, max_repair_attempts: int = 5) -> Dict[str, Any]:
    task = task_manager.create_task(objective, requirements, plan_steps, max_repair_attempts)
    audit.log_task_event(task.id, "created", detail=objective[:100])
    return {"task_id": task.id, "objective": task.objective, "status": task.status.value,
            "repository": task.repository, "branch": task.branch,
            "plan": [{"index": s.index, "description": s.description} for s in task.plan],
            "instructions": f"Use update_task_step(task_id='{task.id}', step_index=N, status='done') as steps complete."}


def get_task(task_id: str) -> Dict[str, Any]:
    task = task_manager.get_task(task_id)
    if not task:
        return {"error": f"Task '{task_id}' not found."}
    return {
        "id": task.id, "objective": task.objective, "requirements": task.requirements,
        "status": task.status.value, "phase": task.phase.value,
        "verification_evidence_id": task.verification_evidence_id,
        "repository": task.repository, "repository_root": task.repository_root,
        "branch": task.branch, "profile": task.profile,
        "plan": [{"index": s.index, "description": s.description, "status": s.status, "result": s.result} for s in task.plan],
        "files_inspected": task.files_inspected, "files_modified": task.files_modified,
        "commands_executed": task.commands_executed[-10:],
        "test_runs": [{"command": t.command, "passed": t.passed, "exit_code": t.exit_code, "timestamp": t.timestamp} for t in task.test_runs[-5:]],
        "repair_attempts": task.repair_attempts, "max_repair_attempts": task.max_repair_attempts,
        "outstanding_issues": task.outstanding_issues, "final_verified": task.final_verified,
        "created_at": task.created_at, "updated_at": task.updated_at, "error": task.error,
        "checkpoints": [{"id": c.id, "description": c.description, "timestamp": c.timestamp} for c in task.checkpoints],
    }


def list_tasks(status_filter: Optional[str] = None) -> Dict[str, Any]:
    tasks = task_manager.list_tasks(status_filter=status_filter)
    return {"total": len(tasks), "tasks": tasks}


def request_approval(operation: str, target: str, details: str = "", ttl_minutes: int = 60,
                    task_id: Optional[str] = None) -> Dict[str, Any]:
    """Create a time-limited approval request for a specific privileged action, target, and optional task."""
    try:
        if task_id:
            linked_task = task_manager.get_task(task_id)
            if not linked_task:
                return {"error": f"Task '{task_id}' not found."}
            if linked_task.phase != TaskPhase.REVIEW:
                return {"error": "Linked task must be in review phase before requesting privileged approval."}
        return {"success": True, "approval": approval_manager.request(operation, target, details, ttl_minutes, task_id)}
    except ValueError as exc:
        return {"error": str(exc)}


def resolve_approval(approval_id: str, decision: str, resolved_by: str = "user") -> Dict[str, Any]:
    """Approve or deny a pending action; decisions are persisted, audited, and linked to task phase."""
    try:
        approval = approval_manager.resolve(approval_id, decision, resolved_by)
        task_id = approval.get("task_id")
        task = task_manager.get_task(task_id) if task_id else None
        if task:
            if decision == "approved" and task.phase == TaskPhase.REVIEW:
                task_manager.transition_phase(task_id, TaskPhase.APPROVAL)
            elif decision == "denied" and task.phase == TaskPhase.APPROVAL:
                task_manager.transition_phase(task_id, TaskPhase.REVIEW)
        return {"success": True, "approval": approval,
                "task_phase": task_manager.get_task(task_id).phase.value if task_id and task_manager.get_task(task_id) else None}
    except (ValueError, RuntimeError) as exc:
        return {"error": str(exc)}


def list_approvals(status_filter: Optional[str] = None) -> Dict[str, Any]:
    if status_filter and status_filter not in {"pending", "approved", "denied", "expired", "consumed"}:
        return {"error": "status_filter must be pending, approved, denied, expired, or consumed."}
    rows = approval_manager.list(status_filter)
    return {"total": len(rows), "approvals": rows}


def create_parallel_workstream(task_id: str, worker_name: str, base_ref: str = "HEAD") -> Dict[str, Any]:
    """Create an isolated Git worktree for a separately operated worker/client."""
    from app.core.workstreams import workstream_manager
    try:
        return {"success": True, "workstream": workstream_manager.create(task_id, worker_name, base_ref),
                "important_boundary": "This provisions an isolated worktree; it does not spawn a separate ChatGPT Web session. Connect an independent coding worker to the returned path."}
    except Exception as exc:
        return {"error": str(exc)}


def list_parallel_workstreams(task_id: Optional[str] = None) -> Dict[str, Any]:
    from app.core.workstreams import workstream_manager
    rows = workstream_manager.list(task_id)
    return {"total": len(rows), "workstreams": rows}


def validate_parallel_workstream(workstream_id: str, test_command: str) -> Dict[str, Any]:
    from app.core.workstreams import workstream_manager
    try:
        return {"success": True, **workstream_manager.validate(workstream_id, test_command)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def merge_parallel_workstream(workstream_id: str, target_branch: str, test_command: str, approval_id: str) -> Dict[str, Any]:
    from app.core.workstreams import workstream_manager
    try:
        return workstream_manager.merge(workstream_id, target_branch, test_command, approval_id)
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def remove_parallel_workstream(workstream_id: str) -> Dict[str, Any]:
    from app.core.workstreams import workstream_manager
    try:
        return workstream_manager.remove(workstream_id)
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def update_task_step(task_id: str, step_index: int, status: str, result: Optional[str] = None) -> Dict[str, Any]:
    task = task_manager.get_task(task_id)
    if not task:
        return {"error": f"Task '{task_id}' not found."}
    if status not in {"running", "done", "failed", "skipped"}:
        return {"error": "status must be running, done, failed, or skipped."}
    task_manager.mark_step(task_id, step_index, status, result)
    audit.log_task_event(task_id, f"step_{step_index}_{status}", detail=result)
    return {"success": True, "task_id": task_id, "step": step_index, "status": status}


def complete_task(task_id: str, verified: bool = True, summary: Optional[str] = None) -> Dict[str, Any]:
    task = task_manager.get_task(task_id)
    if not task:
        return {"error": f"Task '{task_id}' not found."}
    if task.phase == TaskPhase.COMPLETED:
        return {"success": bool(task.final_verified), "task_id": task_id, "verified": task.final_verified,
                "phase": task.phase.value, "verification_evidence_id": task.verification_evidence_id,
                "message": "Task is already completed; create a new task for additional changes."}
    evidence = None
    if verified:
        incomplete = [step.index for step in task.plan if step.status != "done"]
        passing_test = any(run.passed for run in task.test_runs)
        if incomplete or not passing_test:
            return {
                "success": False, "task_id": task_id, "verified": False,
                "incomplete_steps": incomplete, "passing_test_recorded": passing_test,
                "error": "Cannot mark verified: every plan step and a passing recorded test are required before independent verification.",
            }
        try:
            from app.core.verification import verify_repository
            policy_engine.require_cmd_execute()
            evidence = verify_repository(_verification_root(task_id), task_id)
        except Exception as exc:
            return {"success": False, "task_id": task_id, "verified": False,
                    "error": f"Independent verification could not run: {exc}"}
        if not evidence.get("passed"):
            task_manager.set_verified(task_id, False)
            task_manager.update_status(task_id, TaskStatus.REPAIRING)
            return {"success": False, "task_id": task_id, "verified": False,
                    "verification_evidence": evidence,
                    "error": "Independent tests/linters did not pass; task remains incomplete."}
        current = task_manager.get_task(task_id)
        if current and current.phase == TaskPhase.PLANNING:
            task_manager.transition_phase(task_id, TaskPhase.EXECUTION)
            task_manager.transition_phase(task_id, TaskPhase.TESTING)
            task_manager.transition_phase(task_id, TaskPhase.REVIEW, evidence["evidence_id"])
        elif current and current.phase == TaskPhase.EXECUTION:
            task_manager.transition_phase(task_id, TaskPhase.TESTING)
            task_manager.transition_phase(task_id, TaskPhase.REVIEW, evidence["evidence_id"])
        elif current and current.phase == TaskPhase.TESTING:
            task_manager.transition_phase(task_id, TaskPhase.REVIEW, evidence["evidence_id"])
        elif current and current.phase == TaskPhase.REVIEW:
            task_manager.transition_phase(task_id, TaskPhase.REVIEW, evidence["evidence_id"])
        elif current and current.phase in {TaskPhase.APPROVAL, TaskPhase.MERGING}:
            return {"success": False, "task_id": task_id, "verified": False,
                    "error": "Task is in approval/merge phase and cannot bypass that workflow."}
    task_manager.set_verified(task_id, verified)
    if verified:
        task_manager.transition_phase(task_id, TaskPhase.COMPLETED, evidence["evidence_id"] if evidence else None)
    else:
        task_manager.transition_phase(task_id, TaskPhase.FAILED)
    task_manager.update_status(task_id, TaskStatus.COMPLETED if verified else TaskStatus.FAILED)
    if summary and not verified:
        task_manager.add_issue(task_id, f"[SUMMARY] {summary}")
    try:
        hooks_engine.fire("after_task_complete", {"task_id": task_id, "verified": verified})
    except Exception as exc:
        audit.log_task_event(task_id, "completion_hook_failed", detail=str(exc))
    audit.log_task_event(task_id, "completed", detail=f"verified={verified};evidence={evidence.get('evidence_id') if evidence else 'none'}")
    return {"success": True, "task_id": task_id, "verified": verified, "summary": summary,
            "phase": task_manager.get_task(task_id).phase.value,
            "verification_evidence_id": evidence.get("evidence_id") if evidence else None}


def add_task_issue(task_id: str, issue: str) -> Dict[str, Any]:
    if not task_manager.get_task(task_id):
        return {"error": f"Task '{task_id}' not found."}
    task_manager.add_issue(task_id, issue)
    return {"success": True, "task_id": task_id, "issue": issue}


def record_test_result(task_id: str, command: str, exit_code: int, duration_seconds: float,
                       stdout: str = "", stderr: str = "") -> Dict[str, Any]:
    task = task_manager.get_task(task_id)
    if not task:
        return {"error": f"Task '{task_id}' not found."}
    task_manager.record_test_run(task_id, TestRun(command=command, exit_code=exit_code,
        duration_seconds=duration_seconds, passed=exit_code == 0, stdout=stdout[:3000], stderr=stderr[:3000]))
    if exit_code == 0:
        task_manager.update_status(task_id, TaskStatus.RUNNING)
    elif task.repair_attempts < task.max_repair_attempts:
        task_manager.update_status(task_id, TaskStatus.REPAIRING)
    else:
        task_manager.fail_task(task_id, f"Max repair attempts ({task.max_repair_attempts}) reached.")
    return {"task_id": task_id, "test_passed": exit_code == 0,
            "repair_attempts": (task_manager.get_task(task_id).repair_attempts if task_manager.get_task(task_id) else 0)}


def plan_repair_attempt(task_id: str, failing_command: str, root_cause: str, proposed_fix: str,
                        files_to_modify: Optional[List[str]] = None) -> Dict[str, Any]:
    task = task_manager.get_task(task_id)
    if not task:
        return {"error": f"Task '{task_id}' not found."}
    attempt = task_manager.increment_repair(task_id)
    task_manager.update_status(task_id, TaskStatus.REPAIRING)
    note = f"[REPAIR ATTEMPT #{attempt}] Failing: {failing_command} | Cause: {root_cause} | Fix: {proposed_fix}"
    task_manager.add_issue(task_id, note)
    for path in files_to_modify or []:
        task_manager.record_file_modified(task_id, path)
    audit.log_task_event(task_id, "repair_planned", detail=f"attempt={attempt} cause={root_cause[:80]}")
    exceeded = attempt > task.max_repair_attempts
    if exceeded:
        task_manager.fail_task(task_id, f"Maximum repair attempts ({task.max_repair_attempts}) exceeded.")
    return {"task_id": task_id, "repair_attempt": attempt, "max_repair_attempts": task.max_repair_attempts,
            "exceeded": exceeded, "status": "failed" if exceeded else "repairing",
            "guidance": "Stop and ask user for guidance." if exceeded else f"Proceed with planned fix #{attempt}. Run tests and record_test_result afterwards."}


def verify_task(task_id: str, test_command: Optional[str] = None, auto_complete: bool = True) -> Dict[str, Any]:
    """Run independent configured tests and linters; only the resulting evidence can verify completion."""
    task = task_manager.get_task(task_id)
    if not task:
        return {"error": f"Task '{task_id}' not found."}
    if task.phase == TaskPhase.COMPLETED:
        return {"task_id": task_id, "verified": task.final_verified, "phase": task.phase.value,
                "error": "Task is already completed; create a new task for additional changes."}
    evidence = run_independent_verification(task_id)
    refreshed = task_manager.get_task(task_id)
    incomplete = [step for step in (refreshed.plan if refreshed else []) if step.status != "done"]
    for check in evidence.get("checks", []):
        if isinstance(check, dict):
            task_manager.record_test_run(task_id, TestRun(
                command=" ".join(check.get("command", [])), exit_code=check.get("exit_code", -1) if check.get("exit_code") is not None else -1,
                duration_seconds=check.get("duration_seconds", 0.0), passed=bool(check.get("passed")),
                stdout=str(check.get("stdout", ""))[:3000], stderr=str(check.get("stderr", ""))[:3000]))
    passed = bool(evidence.get("passed"))
    all_verified = passed and not incomplete
    if all_verified and auto_complete:
        current = task_manager.get_task(task_id)
        if current and current.phase == TaskPhase.REVIEW:
            task_manager.set_verified(task_id, True)
            task_manager.transition_phase(task_id, TaskPhase.COMPLETED, evidence.get("evidence_id"))
            task_manager.update_status(task_id, TaskStatus.COMPLETED)
            audit.log_task_event(task_id, "verified_complete", detail=f"evidence={evidence.get('evidence_id')}")
    elif not passed:
        task_manager.set_verified(task_id, False)
        task_manager.update_status(task_id, TaskStatus.REPAIRING)
    from app.tools.git import git_status
    git_state = git_status()
    return {"task_id": task_id, "verified": all_verified, "tests_passed": passed,
            "incomplete_steps": [{"index": step.index, "description": step.description} for step in incomplete],
            "verification_evidence": evidence, "verification_evidence_id": evidence.get("evidence_id"),
            "git_status": {"modified_files": git_state.get("modified", []),
                           "untracked_files": git_state.get("untracked", []), "is_clean": git_state.get("clean", False)},
            "status": task_manager.get_task(task_id).status.value if task_manager.get_task(task_id) else "unknown",
            "phase": task_manager.get_task(task_id).phase.value if task_manager.get_task(task_id) else "unknown"}


def run_autonomous_task(objective: str, requirements: Optional[List[str]] = None,
                        plan_steps: Optional[List[str]] = None, max_steps: int = 30,
                        max_repair_attempts: Optional[int] = None, task_id: Optional[str] = None,
                        run_parallel_reviews: bool = True) -> Dict[str, Any]:
    """Start/resume a ChatGPT Web-driven autonomous task; no separate LLM API key is required."""
    try:
        if task_id:
            task = task_manager.get_task(task_id)
            if not task:
                return {"error": f"Task '{task_id}' not found."}
            return {
                "task_id": task.id, "status": task.status.value, "objective": task.objective,
                "requirements": task.requirements,
                "plan": [{"index": step.index, "description": step.description, "status": step.status,
                          "result": step.result} for step in task.plan],
                "files_inspected": task.files_inspected, "files_modified": task.files_modified,
                "commands_executed": task.commands_executed,
                "test_runs": [run.__dict__ for run in task.test_runs],
                "repair_attempts": task.repair_attempts, "max_repair_attempts": task.max_repair_attempts,
                "outstanding_issues": task.outstanding_issues, "final_verified": task.final_verified,
                "next_action": "Continue reasoning in ChatGPT Web and call the registered MCP tools. Update progress with record_chatgpt_task_progress.",
            }
        return start_chatgpt_coding_task(
            objective, requirements, plan_steps, max_repair_attempts or 5
        )
    except Exception as exc:
        audit.log_tool("run_autonomous_task", {"objective": objective[:100]}, success=False, error=str(exc))
        return {"error": str(exc)}


def rollback_task_checkpoint(task_id: str, checkpoint_id: str) -> Dict[str, Any]:
    """Restore a file to its exact pre-edit snapshot."""
    from pathlib import Path
    from app.core.orchestrator import checkpoint_store
    try:
        policy_engine.require_fs_write()
        root = Path(__import__("app.core.session", fromlist=["session_manager"]).session_manager.get_active_repo_path()).resolve()
        result = checkpoint_store.rollback(checkpoint_id, task_id, root)
        audit.log_task_event(task_id, "checkpoint_rollback", detail=checkpoint_id)
        return {"success": True, **result}
    except Exception as exc:
        return {"error": str(exc)}


def run_coding_benchmark(cases_json: str, max_steps: int = 25, max_repair_attempts: int = 3,
                         include_parallel_reviews: bool = False,
                         external_results_json: Optional[str] = None) -> Dict[str, Any]:
    """Run repeatable coding cases and optionally compare external agent outcomes."""
    from app.core.benchmark import run_coding_benchmark as run_benchmark
    try:
        cases = json.loads(cases_json)
        if not isinstance(cases, list):
            return {"error": "cases_json must decode to a JSON array."}
        external = json.loads(external_results_json) if external_results_json else None
        if external is not None and not isinstance(external, list):
            return {"error": "external_results_json must decode to a JSON array."}
        return run_benchmark(cases, max_steps, max_repair_attempts, include_parallel_reviews, external)
    except Exception as exc:
        return {"error": str(exc)}


def get_benchmark_report(limit: int = 100) -> Dict[str, Any]:
    from app.core.benchmark import get_benchmark_report as report
    return report(limit)


def start_chatgpt_coding_task(
    objective: str,
    requirements: Optional[List[str]] = None,
    plan_steps: Optional[List[str]] = None,
    max_repair_attempts: int = 5,
) -> Dict[str, Any]:
    """Start a persistent coding task driven by the connected ChatGPT Web model; no LLM API key is required."""
    if not objective.strip():
        return {"error": "objective must not be empty."}
    profile = execution_profile.get()
    workflow = prepare_task_workflow(objective)
    steps = plan_steps or [
        "Inspect repository state and relevant implementation",
        "Implement the requested changes with checkpoints",
        "Run focused tests and repair failures",
        "Review the diff, security implications, and acceptance criteria",
    ]
    task = task_manager.create_task(objective, requirements or [], steps, max_repair_attempts)
    task_manager.update_status(task.id, TaskStatus.RUNNING)
    task_manager.transition_phase(task.id, TaskPhase.EXECUTION)
    try:
        hooks_engine.fire("before_task_start", {"task_id": task.id, "objective": objective})
    except Exception as exc:
        task_manager.fail_task(task.id, f"Start hook rejected task: {exc}")
        return {"error": str(exc), "task_id": task.id, "status": "failed"}

    audit.log_task_event(task.id, "chatgpt_web_task_started", detail=f"steps={len(steps)}")
    return {
        "task_id": task.id,
        "status": "running",
        "objective": objective,
        "requirements": requirements or [],
        "plan": [{"index": step.index, "description": step.description, "status": step.status} for step in task.plan],
        "selected_skills": workflow["selected_skills"],
        "selected_superpowers": workflow["selected_superpowers"],
        "execution_profile": profile,
        "model_provider": "connected ChatGPT Web session",
        "api_key_required": False,
        "next_actions": [
            "Use the registered repository/file/search tools to inspect the current state before editing.",
            "Update task progress after each meaningful step using record_chatgpt_task_progress.",
            "Use the existing checkpointed filesystem tools for every mutation; do not bypass permission policy.",
            "Run focused tests after edits and record their real exit codes.",
            "Use finish_chatgpt_coding_task only after reviewing the diff and satisfying all requirements.",
        ],
        "important_boundary": "The MCP server stores state and executes tools. ChatGPT Web performs reasoning by calling these MCP tools; the server cannot start a separate ChatGPT Web model session itself.",
    }


def record_chatgpt_task_progress(
    task_id: str,
    step_index: int,
    status: str,
    result: str,
    files_modified: Optional[List[str]] = None,
    test_command: Optional[str] = None,
    test_exit_code: Optional[int] = None,
    test_stdout: str = "",
    test_stderr: str = "",
    repair_note: Optional[str] = None,
) -> Dict[str, Any]:
    """Persist progress made by ChatGPT Web, including test results and bounded repair attempts."""
    task = task_manager.get_task(task_id)
    if not task:
        return {"error": f"Task '{task_id}' not found."}
    if status not in {"pending", "running", "done", "failed", "skipped"}:
        return {"error": "status must be pending, running, done, failed, or skipped."}
    if not any(step.index == step_index for step in task.plan):
        return {"error": f"Plan step {step_index} does not exist."}

    task_manager.mark_step(task_id, step_index, status, result[:3000])
    for path in files_modified or []:
        task_manager.record_file_modified(task_id, path)
    refreshed_phase = task_manager.get_task(task_id)
    if files_modified and refreshed_phase and refreshed_phase.phase in {TaskPhase.TESTING, TaskPhase.REVIEW}:
        task_manager.transition_phase(task_id, TaskPhase.EXECUTION)
    if test_command is not None and test_exit_code is not None:
        task_manager.record_test_run(task_id, TestRun(
            command=test_command, exit_code=test_exit_code, duration_seconds=0.0,
            passed=test_exit_code == 0, stdout=test_stdout[:3000], stderr=test_stderr[:3000],
        ))
        task_manager.record_command(task_id, test_command)
        phase_task = task_manager.get_task(task_id)
        if phase_task and phase_task.phase == TaskPhase.EXECUTION:
            task_manager.transition_phase(task_id, TaskPhase.TESTING)
        elif phase_task and phase_task.phase == TaskPhase.REVIEW:
            task_manager.transition_phase(task_id, TaskPhase.TESTING)
        if test_exit_code != 0:
            task_manager.update_status(task_id, TaskStatus.REPAIRING)
            if repair_note:
                repair = task_manager.increment_repair(task_id)
                task_manager.add_issue(task_id, f"[CHATGPT WEB REPAIR #{repair}] {repair_note[:1500]}")
            refreshed = task_manager.get_task(task_id)
            if refreshed and refreshed.repair_attempts >= refreshed.max_repair_attempts:
                task_manager.fail_task(task_id, f"Maximum repair attempts ({refreshed.max_repair_attempts}) reached.")
        else:
            task_manager.update_status(task_id, TaskStatus.RUNNING)
    audit.log_task_event(task_id, "chatgpt_web_progress", detail=f"step={step_index};status={status}")
    current = task_manager.get_task(task_id)
    return {
        "success": True, "task_id": task_id, "step_index": step_index,
        "status": current.status.value if current else "unknown",
        "repair_attempts": current.repair_attempts if current else 0,
        "max_repair_attempts": current.max_repair_attempts if current else 0,
        "plan": [{"index": step.index, "description": step.description, "status": step.status} for step in current.plan] if current else [],
        "outstanding_issues": current.outstanding_issues if current else [],
    }


def finish_chatgpt_coding_task(
    task_id: str,
    summary: str,
    verification_command: str = "pytest -q",
) -> Dict[str, Any]:
    """Run final verification and complete a ChatGPT Web-driven task only when the plan and tests pass."""
    task = task_manager.get_task(task_id)
    if not task:
        return {"error": f"Task '{task_id}' not found."}
    if task.phase == TaskPhase.COMPLETED:
        return {"success": bool(task.final_verified), "task_id": task_id, "status": task.status.value,
                "verified": task.final_verified, "phase": task.phase.value,
                "verification_evidence_id": task.verification_evidence_id,
                "message": "Task is already completed; create a new task for additional changes."}
    if task.status == TaskStatus.FAILED:
        return {"success": False, "task_id": task_id, "status": "failed",
                "error": task.error or "Task has failed; inspect issues before retrying."}
    try:
        _verification_root(task_id)
    except Exception as exc:
        return {"success": False, "task_id": task_id, "error": str(exc)}
    incomplete = [step.index for step in task.plan if step.status != "done"]
    from app.tools.terminal import run_command
    verification = run_command(verification_command)
    command_passed = verification.get("exit_code") == 0
    task_manager.record_test_run(task_id, TestRun(
        command=verification_command, exit_code=verification.get("exit_code", -1),
        duration_seconds=verification.get("duration_seconds", 0.0), passed=command_passed,
        stdout=str(verification.get("stdout", ""))[:3000], stderr=str(verification.get("stderr", ""))[:3000],
    ))
    independent = None
    if command_passed and not incomplete:
        try:
            from app.core.verification import verify_repository
            independent = verify_repository(_verification_root(task_id), task_id)
        except Exception as exc:
            independent = {"passed": False, "error": str(exc)}
    passed = command_passed and bool(independent and independent.get("passed"))
    if incomplete or not passed:
        task_manager.set_verified(task_id, False)
        task_manager.update_status(task_id, TaskStatus.REPAIRING if not passed else TaskStatus.RUNNING)
        audit.log_task_event(task_id, "chatgpt_web_finish_rejected", detail=f"incomplete={incomplete};tests_passed={passed}")
        return {
            "success": False, "task_id": task_id, "status": task_manager.get_task(task_id).status.value,
            "verified": False, "incomplete_steps": incomplete, "tests_passed": passed,
            "verification_command": verification_command,
            "independent_verification": independent,
            "stdout": str(verification.get("stdout", ""))[-3000:],
            "stderr": str(verification.get("stderr", ""))[-3000:],
            "instruction": "Repair failures or mark each plan step done with evidence, then rerun final verification.",
        }
    current = task_manager.get_task(task_id)
    if current and current.phase == TaskPhase.PLANNING:
        task_manager.transition_phase(task_id, TaskPhase.EXECUTION)
        task_manager.transition_phase(task_id, TaskPhase.TESTING)
        task_manager.transition_phase(task_id, TaskPhase.REVIEW, independent["evidence_id"])
    elif current and current.phase == TaskPhase.EXECUTION:
        task_manager.transition_phase(task_id, TaskPhase.TESTING)
        task_manager.transition_phase(task_id, TaskPhase.REVIEW, independent["evidence_id"])
    elif current and current.phase == TaskPhase.TESTING:
        task_manager.transition_phase(task_id, TaskPhase.REVIEW, independent["evidence_id"])
    elif current and current.phase == TaskPhase.REVIEW:
        task_manager.transition_phase(task_id, TaskPhase.REVIEW, independent["evidence_id"])
    elif current and current.phase in {TaskPhase.APPROVAL, TaskPhase.MERGING}:
        return {"success": False, "task_id": task_id, "verified": False,
                "error": "Task is in approval/merge phase and cannot bypass that workflow."}
    task_manager.set_verified(task_id, True)
    task_manager.transition_phase(task_id, TaskPhase.COMPLETED, independent["evidence_id"])
    task_manager.update_status(task_id, TaskStatus.COMPLETED)
    audit.log_task_event(task_id, "chatgpt_web_task_completed", detail=summary[:1000])
    try:
        hooks_engine.fire("after_task_complete", {"task_id": task_id, "verified": True})
    except Exception as exc:
        audit.log_task_event(task_id, "completion_hook_failed", detail=str(exc))
    return {
        "success": True, "task_id": task_id, "status": "completed", "verified": True,
        "summary": summary, "verification_command": verification_command,
        "tests_passed": True, "independent_verification": independent,
        "verification_evidence_id": independent.get("evidence_id"),
        "phase": task_manager.get_task(task_id).phase.value,
        "stdout": str(verification.get("stdout", ""))[-3000:],
        "stderr": str(verification.get("stderr", ""))[-3000:],
        "files_modified": task_manager.get_task(task_id).files_modified,
    }


def record_chatgpt_benchmark_result(
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
) -> Dict[str, Any]:
    """Record a completed ChatGPT Web or Claude Code benchmark without calling an LLM API."""
    from app.core.benchmark import record_external_benchmark_result
    return record_external_benchmark_result(
        case_name, agent_name, success, baseline_test_passed, final_test_passed,
        repair_attempts, tool_failures, latency_seconds, cost_usd, repository_revision, notes,
    )


def start_coding_workers(task_id: str, objective: str, workers: Optional[List[str]] = None,
                         timeout_seconds: Optional[int] = None) -> Dict[str, Any]:
    """Start independent configured coding CLIs concurrently, each in its own Git worktree."""
    from app.core.worker_runtime import worker_runtime
    try:
        return worker_runtime.start(task_id, objective, workers, timeout_seconds)
    except Exception as exc:
        return {"error": str(exc)}


def get_coding_worker_job(job_id: str) -> Dict[str, Any]:
    from app.core.worker_runtime import worker_runtime
    try:
        return worker_runtime.get(job_id)
    except Exception as exc:
        return {"error": str(exc)}


def list_coding_worker_jobs(task_id: Optional[str] = None) -> Dict[str, Any]:
    from app.core.worker_runtime import worker_runtime
    rows = worker_runtime.list(task_id)
    return {"total": len(rows), "jobs": rows}


def cancel_coding_worker_job(job_id: str) -> Dict[str, Any]:
    from app.core.worker_runtime import worker_runtime
    try:
        return worker_runtime.cancel(job_id)
    except Exception as exc:
        return {"error": str(exc)}


def run_independent_verification(task_id: str = "", timeout_seconds: int = 600) -> Dict[str, Any]:
    """Run configured tests and linters independently of coding-worker claims."""
    from app.core.verification import verify_repository
    try:
        policy_engine.require_cmd_execute()
        root = _verification_root(task_id)
        evidence = verify_repository(root, task_id, timeout_seconds)
        if task_id:
            task = task_manager.get_task(task_id)
            if task:
                if task.phase == TaskPhase.PLANNING:
                    task_manager.transition_phase(task_id, TaskPhase.EXECUTION)
                    task_manager.transition_phase(task_id, TaskPhase.TESTING)
                    if evidence.get("passed"):
                        task_manager.transition_phase(task_id, TaskPhase.REVIEW, evidence["evidence_id"])
                elif task.phase == TaskPhase.EXECUTION:
                    task_manager.transition_phase(task_id, TaskPhase.TESTING)
                    if evidence.get("passed"):
                        task_manager.transition_phase(task_id, TaskPhase.REVIEW, evidence["evidence_id"])
                elif task.phase == TaskPhase.TESTING:
                    if evidence.get("passed"):
                        task_manager.transition_phase(task_id, TaskPhase.REVIEW, evidence["evidence_id"])
                elif task.phase == TaskPhase.REVIEW:
                    if evidence.get("passed"):
                        task_manager.transition_phase(task_id, TaskPhase.REVIEW, evidence["evidence_id"])
                    else:
                        task_manager.transition_phase(task_id, TaskPhase.TESTING)
                if not evidence.get("passed") and task.phase != TaskPhase.COMPLETED:
                    task_manager.set_verified(task_id, False)
                    task_manager.update_status(task_id, TaskStatus.REPAIRING)
        return evidence
    except Exception as exc:
        return {"passed": False, "error": str(exc)}


def transition_task_phase(task_id: str, phase: str, evidence_id: Optional[str] = None) -> Dict[str, Any]:
    """Move a task through the explicit planning/execution/testing/review/approval/merge state machine."""
    try:
        selected = TaskPhase(phase)
        task_manager.transition_phase(task_id, selected, evidence_id)
        audit.log_task_event(task_id, "phase_transition", detail=f"phase={selected.value};evidence={evidence_id or ''}")
        return {"success": True, "task_id": task_id, "phase": selected.value,
                "verification_evidence_id": task_manager.get_task(task_id).verification_evidence_id}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def start_worker_benchmark(cases_json: str, workers: Optional[List[str]] = None,
                           timeout_seconds: Optional[int] = None) -> Dict[str, Any]:
    """Run identical cases against configured coding CLIs on the same clean baseline revision."""
    from app.core.worker_benchmark import start_benchmark
    try:
        cases = json.loads(cases_json)
        if not isinstance(cases, list):
            return {"error": "cases_json must decode to a JSON array."}
        return start_benchmark(cases, workers, timeout_seconds)
    except Exception as exc:
        return {"error": str(exc)}


def get_worker_benchmark(run_id: str) -> Dict[str, Any]:
    from app.core.worker_benchmark import get_benchmark
    try:
        return get_benchmark(run_id)
    except Exception as exc:
        return {"error": str(exc)}


def list_worker_benchmarks(limit: int = 50) -> Dict[str, Any]:
    from app.core.worker_benchmark import list_benchmarks
    return list_benchmarks(limit)
