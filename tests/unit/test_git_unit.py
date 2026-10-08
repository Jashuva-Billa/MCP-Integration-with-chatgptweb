from app.tools.git import git_status, git_diff, git_branch, git_log, git_show, git_changed_files
from app.core.session import session_manager

def test_git_unit_tools(test_environment):
    session_manager.set_active_repo_name("Repo_A")

    st = git_status()
    assert "status_output" in st or st.get("exit_code") == 0

    br = git_branch()
    assert br.get("exit_code") == 0

    lg = git_log(max_commits=5)
    assert lg.get("exit_code") == 0

    sh = git_show("HEAD")
    assert sh.get("exit_code") == 0

    cf = git_changed_files()
    assert "changed_files" in cf
