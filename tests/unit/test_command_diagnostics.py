"""
Tests for command handling, output capture, timeout behavior, and diagnostics.
"""
import pytest
from app.tools.terminal import diagnose_command_failure, _run_process


def test_diagnose_timeout():
    diag = diagnose_command_failure("pytest", exit_code=-1, stdout="", stderr="", timed_out=True)
    assert diag["category"] == "TIMEOUT"
    assert "timeout" in diag["summary"].lower()
    assert "suggested_action" in diag


def test_diagnose_missing_python_dependency():
    diag = diagnose_command_failure(
        "python app.py",
        exit_code=1,
        stdout="",
        stderr="ModuleNotFoundError: No module named 'fastapi'",
        timed_out=False,
    )
    assert diag["category"] == "MISSING_DEPENDENCY"
    assert "fastapi" in diag["summary"]
    assert "install_dependencies" in diag["suggested_action"]


def test_diagnose_syntax_error():
    diag = diagnose_command_failure(
        "python -m py_compile app.py",
        exit_code=1,
        stdout="",
        stderr="SyntaxError: invalid syntax (line 42)",
        timed_out=False,
    )
    assert diag["category"] == "SYNTAX_ERROR"
    assert "replace_in_file" in diag["suggested_action"]


def test_diagnose_test_failure():
    diag = diagnose_command_failure(
        "pytest tests/",
        exit_code=1,
        stdout="FAILED tests/unit/test_calc.py::test_add - AssertionError: assert 4 == 5",
        stderr="",
        timed_out=False,
    )
    assert diag["category"] == "TEST_FAILURE"
    assert "assertions failed" in diag["summary"]


def test_diagnose_git_conflict():
    diag = diagnose_command_failure(
        "git merge feature",
        exit_code=1,
        stdout="CONFLICT (content): Merge conflict in main.py",
        stderr="Automatic merge failed; fix conflicts and then commit the result.",
        timed_out=False,
    )
    assert diag["category"] == "GIT_CONFLICT"
    assert "git_stage" in diag["suggested_action"]


def test_process_output_capture_and_diagnostics(tmp_path):
    # Run a command that fails and verify structured output capture
    res = _run_process(["python", "-c", "import non_existent_library_xyz"], str(tmp_path), timeout=10)
    assert res["exit_code"] != 0
    assert "diagnostics" in res
    assert res["diagnostics"]["category"] == "MISSING_DEPENDENCY"
    assert res["stdout_truncated"] is False
    assert res["stderr_truncated"] is False
    assert res["output_bytes"] > 0
