from app.tools.repository_analysis import analyze_repository
from app.core.session import session_manager

def test_analyze_repository(test_environment):
    session_manager.set_active_repo_name("Repo_A")
    res = analyze_repository()
    assert res["repository"] == "Repo_A"
    assert "Python" in res["languages"]
    assert "FastAPI" in res["frameworks"]
    assert "requirements.txt" in res["configuration_files"]
