import pytest
from app.core.repository import RepositoryManager

def test_repository_crud(tmp_path):
    config_file = tmp_path / "repos.json"
    repo_dir = tmp_path / "my_project"
    repo_dir.mkdir()

    mgr = RepositoryManager(str(config_file))
    
    # 1. Add repository
    added = mgr.add_repository("my_project", str(repo_dir), "Sample project")
    assert added["name"] == "my_project"

    # 2. Get repository
    item = mgr.get_repository("my_project")
    assert item is not None
    assert item["exists_on_disk"] is True

    # 3. List repositories
    repos = mgr.list_repositories()
    assert len(repos) == 1

    # 4. Remove repository (Registry only)
    assert mgr.remove_repository("my_project") is True
    assert repo_dir.exists()  # Physical disk untouched!
