import pytest
from app.tools import (
    workspace,
    filesystem,
    search,
    code_intelligence,
    terminal,
    git,
    repository_analysis
)

def test_complete_end_to_end_coding_agent_flow(test_environment):
    # 1. Discover available workspaces
    repos = workspace.list_repositories()
    assert repos["total_configured"] >= 2

    # 2. Select active workspace
    sel = workspace.select_repository("Repo_A")
    assert sel["success"] is True

    # 3. Analyze repository architecture
    analysis = repository_analysis.analyze_repository()
    assert analysis["repository"] == "Repo_A"
    assert "Python" in analysis["languages"]

    # 4. Search relevant code
    srch = search.search_code("Calculator")
    assert srch["total_matches"] >= 1

    # 5. Inspect symbols and functions using Code Intelligence
    syms = code_intelligence.find_symbol("Calculator")
    assert syms["total_definitions"] >= 1
    funcs = code_intelligence.list_functions("src/app.py")
    assert funcs["total_functions"] >= 1

    # 6. Controlled write-read-delete cycle
    test_file = "src/temp_test_module.py"
    w_res = filesystem.write_file(test_file, "def test_hello():\n    return 'hello_mcp'\n")
    assert w_res["success"] is True

    r_res = filesystem.read_file(test_file)
    assert "hello_mcp" in r_res["content"]

    # 7. Execute tests / python terminal command
    t_res = terminal.run_command('python -c "import src.temp_test_module as m; print(m.test_hello())"')
    assert t_res["exit_code"] == 0
    assert "hello_mcp" in t_res["stdout"]

    # 8. Check Git status and diff
    st_res = git.git_status()
    assert st_res["exit_code"] == 0
    assert "temp_test_module.py" in st_res.get("status_output", "")

    # 9. Clean up temporary file
    d_res = filesystem.delete_file(test_file)
    assert d_res["success"] is True

    # Verify deleted
    verify_del = filesystem.read_file(test_file)
    assert "error" in verify_del
