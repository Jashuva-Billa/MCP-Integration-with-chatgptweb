from app.tools.filesystem import list_files, read_file, write_file, create_directory, delete_file
from app.core.session import session_manager

def test_filesystem_operations(test_environment):
    session_manager.set_active_repo_name("Repo_A")

    # Create dir
    assert create_directory("src/helpers")["success"] is True

    # Write file
    w = write_file("src/helpers/utils.py", "def helper():\n    return 'ok'\n")
    assert w["success"] is True

    # List files
    lf = list_files("src/helpers")
    assert lf["count"] >= 1

    # Read file
    rf = read_file("src/helpers/utils.py")
    assert "def helper():" in rf["content"]

    # Delete file
    df = delete_file("src/helpers/utils.py")
    assert df["success"] is True
