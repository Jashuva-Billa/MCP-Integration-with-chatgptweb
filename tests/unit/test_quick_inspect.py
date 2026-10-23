from app.tools import quick_inspect


def test_inspect_workspace_combines_read_only_results(monkeypatch):
    monkeypatch.setattr(quick_inspect.workspace, "get_current_repository", lambda: {"repository_name": "demo"})
    monkeypatch.setattr(quick_inspect.git, "git_status", lambda: {"exit_code": 0, "status_output": " M app.py"})
    monkeypatch.setattr(quick_inspect.filesystem, "list_files", lambda path, recursive, max_results: {
        "base_directory": ".", "count": 1, "entries": [{"path": "app.py", "type": "file"}], "limit": max_results
    })

    result = quick_inspect.inspect_workspace(max_files=1000)

    assert result["repository"]["repository_name"] == "demo"
    assert result["git_status"]["exit_code"] == 0
    assert result["top_level_files"]["entries"][0]["path"] == "app.py"
    assert result["top_level_files"]["limit"] == 100
    assert "read-only" in result["note"].lower()
