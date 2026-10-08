from app.core.session import SessionManager

def test_session_isolation(test_environment):
    session_mgr = SessionManager()
    
    # Session 1 selects Repo_A
    s1_ok, _ = session_mgr.set_active_repo_name("Repo_A", session_id="user_1")
    assert s1_ok is True

    # Session 2 selects Repo_B
    s2_ok, _ = session_mgr.set_active_repo_name("Repo_B", session_id="user_2")
    assert s2_ok is True

    # Verify complete isolation
    assert session_mgr.get_active_repo_name("user_1") == "Repo_A"
    assert session_mgr.get_active_repo_name("user_2") == "Repo_B"
    assert "Repo_A" in str(session_mgr.get_active_repo_path("user_1"))
    assert "Repo_B" in str(session_mgr.get_active_repo_path("user_2"))
