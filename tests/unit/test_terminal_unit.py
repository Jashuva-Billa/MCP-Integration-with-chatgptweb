from app.tools.terminal import run_command
from app.core.session import session_manager

def test_terminal_sandboxed_command(test_environment):
    session_manager.set_active_repo_name("Repo_A")
    res = run_command('python -c "print(55 + 45)"')
    assert res["exit_code"] == 0
    assert "100" in res["stdout"]

def test_terminal_blocked_command(test_environment):
    session_manager.set_active_repo_name("Repo_A")
    res = run_command("rm -rf /")
    assert "error" in res
    assert "Security Violation" in res["error"]
