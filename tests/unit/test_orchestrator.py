"""Tests for the model-driven orchestration loop and checkpoint recovery."""
from app.core import orchestrator as orchestration_module
from app.core.orchestrator import AutonomousOrchestrator, CheckpointStore
from app.core.session import session_manager


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def complete(self, messages, *, role="orchestrator"):
        self.calls += 1
        value = self.responses.pop(0)
        return {"content": value, "latency_seconds": 0.01, "prompt_tokens": 10,
                "completion_tokens": 5, "model": "fake-model"}


def test_checkpoint_restores_existing_and_new_files(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "a.py"
    target.write_text("before", encoding="utf-8")
    store = CheckpointStore(tmp_path / "checkpoints")

    first = store.create("task1", "a.py", repo)
    target.write_text("after", encoding="utf-8")
    restored = store.rollback(first["checkpoint_id"], "task1", repo)
    assert target.read_text(encoding="utf-8") == "before"
    assert restored["restored_existing_file"] is True

    second = store.create("task1", "new.py", repo)
    (repo / "new.py").write_text("created", encoding="utf-8")
    store.rollback(second["checkpoint_id"], "task1", repo)
    assert not (repo / "new.py").exists()

    directory = repo / "folder"
    directory.mkdir()
    (directory / "keep.txt").write_text("keep", encoding="utf-8")
    third = store.create("task1", "folder", repo)
    import shutil
    shutil.rmtree(directory)
    store.rollback(third["checkpoint_id"], "task1", repo)
    assert (directory / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_checkpoint_refuses_cross_repository_rollback(tmp_path):
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    (repo_a / "same.txt").write_text("original", encoding="utf-8")
    (repo_b / "same.txt").write_text("do not overwrite", encoding="utf-8")
    store = CheckpointStore(tmp_path / "checkpoints")
    checkpoint = store.create("task-cross-root", "same.txt", repo_a)
    try:
        store.rollback(checkpoint["checkpoint_id"], "task-cross-root", repo_b)
    except ValueError as exc:
        assert "active repository root" in str(exc)
    else:
        raise AssertionError("cross-repository checkpoint rollback must be rejected")
    assert (repo_b / "same.txt").read_text(encoding="utf-8") == "do not overwrite"


def test_orchestrator_runs_actions_and_finishes(test_environment, tmp_path, monkeypatch):
    from app.core import verification
    monkeypatch.setattr(verification, "verify_repository", lambda root, task_id: {
        "passed": True, "evidence_id": "orchestrator-evidence", "checks": [], "revision_stable": True
    })
    repo = test_environment["repo_a"]
    session_manager.set_active_repo_name("Repo_A")
    (repo / "src" / "hello.py").write_text("print('old')\n", encoding="utf-8")
    store = CheckpointStore(tmp_path / "checkpoints")
    monkeypatch.setattr(orchestration_module, "checkpoint_store", store)

    def write_file(path, content):
        manifest = store.create("fake-task", path, repo)
        (repo / path).write_text(content, encoding="utf-8")
        return {"success": True, "file_path": path, "checkpoint_id": manifest["checkpoint_id"],
                "checkpoint_task_id": "fake-task"}

    monkeypatch.setattr(orchestration_module, "_tool_actions", lambda: {
        "read_file": lambda path: {"content": "print('old')\n"},
        "write_file": write_file,
        "run_tests": lambda **kwargs: {"exit_code": 0, "stdout": "2 passed", "stderr": "", "duration_seconds": 0.1},
        "run_command": lambda **kwargs: {"exit_code": 0, "stdout": "ok", "stderr": "", "duration_seconds": 0.1},
        "search_code": lambda **kwargs: {"results": []},
        "git_status": lambda **kwargs: {"clean": False},
        "git_diff": lambda **kwargs: {"diff": ""},
    })
    provider = FakeProvider([
        {"action": "read_file", "args": {"path": "src/hello.py"}, "note": "inspect"},
        {"action": "write_file", "args": {"path": "src/hello.py", "content": "print('new')\n"}, "note": "implement"},
        {"action": "run_tests", "args": {"test_path": "tests", "framework": "pytest"}, "note": "validate"},
        {"action": "finish", "args": {}, "acceptance_met": True, "summary": "implemented and tested"},
    ])
    result = AutonomousOrchestrator(provider).run(
        "Update hello", requirements=["file updated"], max_steps=5, run_parallel_reviews=False,
    )
    assert result["status"] == "completed"
    assert result["verified"] is True
    assert result["metrics"]["steps"] == 4
    assert (repo / "src" / "hello.py").read_text(encoding="utf-8") == "print('new')\n"
    assert result["trace"][1]["checkpoint_id"]
    assert provider.calls == 4


def test_provider_fails_closed_when_unconfigured(monkeypatch):
    from app.core.orchestrator import OpenAICompatibleProvider, ProviderError
    monkeypatch.delenv("MCP_LLM_API_KEY", raising=False)
    monkeypatch.delenv("MCP_LLM_MODEL", raising=False)
    try:
        OpenAICompatibleProvider().complete([{"role": "user", "content": "hello"}])
    except ProviderError as exc:
        assert "MCP_LLM_API_KEY" in str(exc)
    else:
        raise AssertionError("Unconfigured provider should fail closed")


def test_filesystem_mutation_returns_rollback_checkpoint(test_environment):
    from app.tools import filesystem, agent
    repo = test_environment["repo_a"]
    session_manager.set_active_repo_name("Repo_A")
    target = repo / "src" / "recovery.txt"
    target.write_text("original", encoding="utf-8")

    result = filesystem.write_file("src/recovery.txt", "changed")
    assert result["success"] is True
    assert target.read_text(encoding="utf-8") == "changed"
    rolled = agent.rollback_task_checkpoint(result["checkpoint_task_id"], result["checkpoint_id"])
    assert rolled["success"] is True
    assert target.read_text(encoding="utf-8") == "original"


def test_aborting_validation_hook_rolls_back_mutation(test_environment, monkeypatch):
    from app.core.hooks import hooks_engine
    from app.tools import filesystem
    repo = test_environment["repo_a"]
    session_manager.set_active_repo_name("Repo_A")
    target = repo / "src" / "hook-recovery.txt"
    target.write_text("safe", encoding="utf-8")
    original_fire = hooks_engine.fire

    def fail_after_edit(event, context=None):
        if event == "after_file_edit":
            raise RuntimeError("validation hook rejected change")
        return original_fire(event, context)

    monkeypatch.setattr(hooks_engine, "fire", fail_after_edit)
    result = filesystem.write_file("src/hook-recovery.txt", "unsafe")
    assert "error" in result
    assert target.read_text(encoding="utf-8") == "safe"


def test_orchestrator_resumes_persisted_session(test_environment, monkeypatch):
    from app.core import verification
    monkeypatch.setattr(verification, "verify_repository", lambda root, task_id: {
        "passed": True, "evidence_id": "resume-evidence", "checks": [], "revision_stable": True
    })
    session_manager.set_active_repo_name("Repo_A")
    monkeypatch.setattr(orchestration_module, "_tool_actions", lambda: {
        "read_file": lambda path: {"content": "existing source"},
        "write_file": lambda **kwargs: {"success": True},
        "run_tests": lambda **kwargs: {"exit_code": 0, "stdout": "passed", "stderr": "", "duration_seconds": 0.1},
        "run_command": lambda **kwargs: {"exit_code": 0, "stdout": "ok", "stderr": "", "duration_seconds": 0.1},
        "search_code": lambda **kwargs: {"results": []},
        "git_status": lambda **kwargs: {"clean": True},
        "git_diff": lambda **kwargs: {"diff": ""},
    })
    first = AutonomousOrchestrator(FakeProvider([
        {"action": "read_file", "args": {"path": "src/app.py"}, "note": "inspect"}
    ])).run("Inspect and validate app", max_steps=1, run_parallel_reviews=False)
    assert first["status"] == "failed"
    task_id = first["task_id"]

    resumed = AutonomousOrchestrator(FakeProvider([
        {"action": "run_tests", "args": {"test_path": "tests", "framework": "pytest"}, "note": "validate"},
        {"action": "finish", "args": {}, "acceptance_met": True, "summary": "validated"},
    ])).run("ignored on resume", task_id=task_id, max_steps=2, run_parallel_reviews=False)
    assert resumed["status"] == "completed"
    assert resumed["verified"] is True
    assert resumed["metrics"]["steps"] == 3


def test_hard_git_reset_checkpoints_dirty_files(test_environment, monkeypatch):
    from app.core.permissions import PermissionProfile, policy_engine
    from app.tools import git
    repo = test_environment["repo_a"]
    session_manager.set_active_repo_name("Repo_A")
    target = repo / "src" / "checkpointed.py"
    target.write_text("value = 1\n", encoding="utf-8")
    original = target.read_text(encoding="utf-8")
    target.write_text(original + "\n# local uncommitted change\n", encoding="utf-8")

    def fake_git(args, cwd, timeout=30):
        if args == ["rev-parse", "HEAD"]:
            return {"exit_code": 0, "stdout": "abc123\n", "stderr": ""}
        if args and args[0] == "branch":
            return {"exit_code": 0, "stdout": "", "stderr": ""}
        if args and args[0] == "checkout":
            return {"exit_code": 0, "stdout": "switched", "stderr": ""}
        if args == ["diff", "--name-only", "-z", "HEAD"]:
            return {"exit_code": 0, "stdout": "src/checkpointed.py\0", "stderr": ""}
        if args == ["reset", "--hard", "HEAD"]:
            target.write_text(original, encoding="utf-8")
            return {"exit_code": 0, "stdout": "reset", "stderr": ""}
        raise AssertionError(f"Unexpected git invocation: {args}")

    monkeypatch.setattr(git, "_run_git", fake_git)
    previous_profile = policy_engine.profile
    try:
        policy_engine.set_profile(PermissionProfile.UNRESTRICTED)
        result = git.git_reset(mode="hard", target="HEAD")
        assert result["success"] is True
        assert result["rollback_branch"]
        assert result["checkpoints"]
        assert target.read_text(encoding="utf-8") == original
        restored = git.rollback_git_reset_checkpoint(result["rollback_branch"], result["checkpoint_task_id"])
        assert restored["success"] is True
        assert "src/checkpointed.py" in restored["restored_files"]
        assert "local uncommitted change" in target.read_text(encoding="utf-8")
    finally:
        policy_engine.set_profile(previous_profile)


def test_parallel_review_workers_run_concurrently():
    import threading
    from app.core.orchestrator import AutonomousOrchestrator

    barrier = threading.Barrier(3)
    lock = threading.Lock()
    calls = 0
    active = 0
    max_active = 0

    class ParallelProvider:
        def complete(self, messages, *, role="orchestrator"):
            nonlocal calls, active, max_active
            with lock:
                calls += 1
                call_number = calls
                active += 1
                max_active = max(max_active, active)
            if call_number <= 3:
                barrier.wait(timeout=2)
            with lock:
                active -= 1
            return {"content": {"severity": "low", "findings": [], "summary": role + " reviewed"},
                    "latency_seconds": 0.01, "prompt_tokens": 1, "completion_tokens": 1,
                    "cost_usd": None, "model": "fake"}

    result = AutonomousOrchestrator(ParallelProvider())._parallel_reviews(
        "Implement feature", ["tests pass"], "trace context"
    )
    assert len(result) == 5
    assert calls == 5
    assert max_active == 3
    assert all("error" not in worker for worker in result.values())


def test_high_severity_worker_proposal_is_checkpointed_and_revalidated(test_environment, monkeypatch):
    from app.core import verification
    monkeypatch.setattr(verification, "verify_repository", lambda root, task_id: {
        "passed": True, "evidence_id": "worker-review-evidence", "checks": [], "revision_stable": True
    })
    import threading
    from app.core.orchestrator import AutonomousOrchestrator
    from app.tools import terminal
    monkeypatch.setattr(terminal, "run_tests", lambda **kwargs: {"exit_code": 0, "stdout": "passed", "stderr": "", "duration_seconds": 0.1})
    repo = test_environment["repo_a"]
    session_manager.set_active_repo_name("Repo_A")
    (repo / "src" / "worker-source.py").write_text("value = 1\n", encoding="utf-8")

    main_responses = [
        {"action": "read_file", "args": {"path": "src/worker-source.py"}, "note": "inspect"},
        {"action": "run_tests", "args": {"test_path": "tests", "framework": "pytest"}, "note": "test current change"},
        {"action": "finish", "args": {}, "acceptance_met": True, "summary": "initial pass"},
        {"action": "run_tests", "args": {"test_path": "tests", "framework": "pytest"}, "note": "validate worker proposal"},
        {"action": "finish", "args": {}, "acceptance_met": True, "summary": "proposal validated"},
    ]
    lock = threading.Lock()
    implementation_calls = 0

    class WorkerProvider:
        def complete(self, messages, *, role="orchestrator"):
            nonlocal implementation_calls
            if role == "orchestrator":
                with lock:
                    response = main_responses.pop(0)
                return {"content": response, "latency_seconds": 0.01, "prompt_tokens": 1,
                        "completion_tokens": 1, "cost_usd": None, "model": "fake"}
            if role == "implementation_worker":
                with lock:
                    implementation_calls += 1
                    first = implementation_calls == 1
                if first:
                    return {"content": {"severity": "high", "summary": "Missing required helper",
                        "findings": ["helper is absent"],
                        "proposed_changes": [{"path": "src/worker-helper.py", "content": "worker_helper = True\n",
                                              "reason": "Add the missing helper"}]},
                        "latency_seconds": 0.01, "prompt_tokens": 1, "completion_tokens": 1,
                        "cost_usd": None, "model": "fake"}
            return {"content": {"severity": "low", "summary": "No blocking issue", "findings": []},
                    "latency_seconds": 0.01, "prompt_tokens": 1, "completion_tokens": 1,
                    "cost_usd": None, "model": "fake"}

    result = AutonomousOrchestrator(WorkerProvider()).run(
        "Add the missing helper", requirements=["helper exists"], max_steps=5, run_parallel_reviews=True
    )
    assert result["status"] == "completed", result
    assert result["verified"] is True
    assert (repo / "src" / "worker-helper.py").read_text(encoding="utf-8") == "worker_helper = True\n"
    assert any(entry.get("worker") == "implementation_worker" for entry in result["trace"])
    assert implementation_calls == 2
