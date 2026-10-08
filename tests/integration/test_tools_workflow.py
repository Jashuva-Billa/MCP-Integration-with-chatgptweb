from app.tools import workspace, filesystem, search, git, code_intelligence

def test_full_tools_workflow(test_environment):
    # 1. Select repository
    sel = workspace.select_repository("Repo_A")
    assert sel["success"] is True

    # 2. Inspect current repo
    curr = workspace.get_current_repository()
    assert curr["repository_name"] == "Repo_A"

    # 3. List files
    files = filesystem.list_files()
    assert files["count"] >= 1

    # 4. Search
    srch = search.search_code("Calculator")
    assert srch["total_matches"] >= 1

    # 5. Modify file
    mod = filesystem.write_file("README.md", "# Repo A - Updated via Workflow\nNew line added.")
    assert mod["success"] is True

    # 6. Check Git Diff
    diff = git.git_diff()
    assert "Updated via Workflow" in diff.get("diff", "")
