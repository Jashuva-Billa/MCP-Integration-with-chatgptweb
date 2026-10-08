from app.tools.search import search_code
from app.core.session import session_manager

def test_search_code_unit(test_environment):
    session_manager.set_active_repo_name("Repo_A")
    res = search_code("Calculator")
    assert res["total_matches"] >= 1
    assert "src/app.py" in res["results"][0]["file"]
