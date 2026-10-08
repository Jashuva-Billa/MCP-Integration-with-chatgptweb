from app.tools.code_intelligence import (
    list_functions,
    list_classes,
    get_file_structure,
    find_symbol,
    find_references
)
from app.core.session import session_manager

def test_code_intelligence_tools(test_environment):
    session_manager.set_active_repo_name("Repo_A")

    # List classes
    cls_res = list_classes("src/app.py")
    assert cls_res["total_classes"] >= 1
    assert cls_res["classes"][0]["name"] == "Calculator"

    # List functions
    fn_res = list_functions("src/app.py")
    assert fn_res["total_functions"] >= 1
    fn_names = [f["name"] for f in fn_res["functions"]]
    assert "add" in fn_names or "main" in fn_names

    # File structure
    struct = get_file_structure("src/app.py")
    assert "Calculator" in [c["name"] for c in struct.get("classes", [])]

    # Find symbol
    sym = find_symbol("Calculator")
    assert sym["total_definitions"] >= 1
