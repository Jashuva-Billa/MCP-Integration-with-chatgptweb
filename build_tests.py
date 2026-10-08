import os
from pathlib import Path

BASE_DIR = Path(r"C:\Development\chatgpt-mcp-server\tests")
BASE_DIR.mkdir(parents=True, exist_ok=True)

test_files = {}

# 1. tests/__init__.py
test_files["__init__.py"] = ""

# 2. tests/conftest.py
test_files["conftest.py"] = '''import pytest
import subprocess
import shutil
from pathlib import Path
from server.config import config
from server.session import session_manager

@pytest.fixture(scope="session")
def test_environment(tmp_path_factory):
    root = tmp_path_factory.mktemp("mcp_test_env")
    repo_a = root / "Repo_A"
    repo_b = root / "Repo_B"
    repo_a.mkdir()
    repo_b.mkdir()

    # Initialize Git in repo_a
    subprocess.run(["git", "init"], cwd=str(repo_a), capture_output=True)
    subprocess.run(["git", "config", "user.name", "TestUser"], cwd=str(repo_a), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_a), capture_output=True)

    # Add sample files to repo_a
    (repo_a / "README.md").write_text("# Repo A\\nWelcome to Repo A", encoding="utf-8")
    (repo_a / "src").mkdir()
    (repo_a / "src" / "app.py").write_text("def run():\\n    print('Running App A')\\n", encoding="utf-8")
    (repo_a / ".env").write_text("SECRET_KEY=supersecret\\n", encoding="utf-8")
    (repo_a / "credentials.json").write_text('{"token": "xyz123"}\\n', encoding="utf-8")

    # Initial commit in repo_a
    subprocess.run(["git", "add", "README.md", "src/app.py"], cwd=str(repo_a), capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo_a), capture_output=True)

    # Add sample files to repo_b
    (repo_b / "README.md").write_text("# Repo B\\nWelcome to Repo B", encoding="utf-8")
    (repo_b / "secret_b.txt").write_text("Top secret in Repo B", encoding="utf-8")

    # Configure temporary repositories.yaml
    config_yaml = root / "test_repositories.yaml"
    config.REPOSITORIES_CONFIG_PATH = str(config_yaml)
    config.save_repositories({
        "Repo_A": {"path": str(repo_a), "description": "Mock Repository A"},
        "Repo_B": {"path": str(repo_b), "description": "Mock Repository B"}
    })

    # Set initial default repo
    session_manager.set_active_repo_name("Repo_A")

    return {
        "root": root,
        "repo_a": repo_a,
        "repo_b": repo_b,
        "config_yaml": config_yaml
    }
'''

# 3. tests/test_workspace.py
test_files["test_workspace.py"] = '''import pytest
from pathlib import Path
from tools.workspace import (
    list_repositories,
    select_repository,
    get_current_repository,
    add_repository,
    remove_repository
)
from server.session import session_manager

def test_list_repositories(test_environment):
    res = list_repositories()
    assert res["total_configured"] >= 2
    repo_names = [r["name"] for r in res["repositories"]]
    assert "Repo_A" in repo_names
    assert "Repo_B" in repo_names

def test_select_and_get_current_repository(test_environment):
    sel_res = select_repository("Repo_A")
    assert sel_res["success"] is True
    assert sel_res["active_repository"] == "Repo_A"

    curr_res = get_current_repository()
    assert curr_res["repository_name"] == "Repo_A"
    assert "Repo_A" in curr_res["absolute_path"]

def test_select_invalid_repository(test_environment):
    res = select_repository("NonExistent_Repo")
    assert res["success"] is False
    assert "not found" in res["message"].lower()

def test_add_and_remove_repository(test_environment):
    new_dir = test_environment["root"] / "Repo_C"
    new_dir.mkdir(exist_ok=True)

    # Add repo
    add_res = add_repository("Repo_C", str(new_dir), "Mock Repository C")
    assert add_res["success"] is True

    # Verify present
    list_res = list_repositories()
    names = [r["name"] for r in list_res["repositories"]]
    assert "Repo_C" in names

    # Remove repo
    rem_res = remove_repository("Repo_C")
    assert rem_res["success"] is True

    # Physical folder MUST NOT be deleted
    assert new_dir.exists()
    assert new_dir.is_dir()

def test_session_isolation_multi_client(test_environment):
    """Verify that Session A selecting Repo A and Session B selecting Repo B remain strictly isolated."""
    session_manager.set_active_repo_name("Repo_A", session_id="session_user_1")
    session_manager.set_active_repo_name("Repo_B", session_id="session_user_2")

    assert session_manager.get_active_repo_name("session_user_1") == "Repo_A"
    assert session_manager.get_active_repo_name("session_user_2") == "Repo_B"

    path_1 = session_manager.get_active_repo_path("session_user_1")
    path_2 = session_manager.get_active_repo_path("session_user_2")

    assert path_1 == test_environment["repo_a"].resolve()
    assert path_2 == test_environment["repo_b"].resolve()
'''

# 4. tests/test_security.py
test_files["test_security.py"] = '''import pytest
from server.security import (
    sanitize_and_resolve_path,
    validate_command_security,
    SecurityError
)
from server.session import session_manager

def test_cross_repository_access_prevention(test_environment):
    """CRITICAL TEST: When Repo A is selected, any attempt to access Repo B MUST fail."""
    session_manager.set_active_repo_name("Repo_A")
    repo_b_path = str(test_environment["repo_b"] / "secret_b.txt")

    with pytest.raises(SecurityError) as exc_info:
        sanitize_and_resolve_path(repo_b_path)
    assert "escapes active repository" in str(exc_info.value).lower()

def test_path_traversal_prevention(test_environment):
    session_manager.set_active_repo_name("Repo_A")

    # Relative dot-dot traversal
    with pytest.raises(SecurityError):
        sanitize_and_resolve_path("../../secret.txt")

    with pytest.raises(SecurityError):
        sanitize_and_resolve_path("..\\\\..\\\\secret.txt")

    with pytest.raises(SecurityError):
        sanitize_and_resolve_path("src/../../outside.txt")

def test_absolute_path_escape_prevention(test_environment):
    session_manager.set_active_repo_name("Repo_A")

    with pytest.raises(SecurityError):
        sanitize_and_resolve_path("C:\\\\Windows\\\\System32")

    with pytest.raises(SecurityError):
        sanitize_and_resolve_path("C:/Windows")

def test_secret_file_protection(test_environment):
    session_manager.set_active_repo_name("Repo_A")

    blocked_files = [
        ".env",
        ".env.local",
        "id_rsa",
        "id_ed25519",
        "credentials.json",
        "secrets.json",
        "server.key",
        "cert.pem",
        "auth.p12"
    ]

    for fname in blocked_files:
        with pytest.raises(SecurityError) as exc_info:
            sanitize_and_resolve_path(fname)
        assert "sensitive" in str(exc_info.value).lower() or "prohibited" in str(exc_info.value).lower()

def test_unc_path_rejection(test_environment):
    session_manager.set_active_repo_name("Repo_A")
    with pytest.raises(SecurityError) as exc_info:
        sanitize_and_resolve_path("\\\\\\\\remote-share\\\\malicious\\\\file.txt")
    assert "unc" in str(exc_info.value).lower()

def test_command_security_guard():
    # Blocked commands
    blocked = [
        "format C:",
        "shutdown /s",
        "rm -rf /",
        "del /s *.*",
        "rmdir /s /q test",
        "git reset --hard HEAD~1",
        "git clean -fd",
        "git push origin main",
        "git commit -m 'hack'"
    ]
    for cmd in blocked:
        with pytest.raises(SecurityError):
            validate_command_security(cmd)

    # Allowed safe commands
    allowed = [
        "pytest tests/",
        "python -m unittest",
        "npm test",
        "git status",
        "git diff",
        "ruff check ."
    ]
    for cmd in allowed:
        binary, args = validate_command_security(cmd)
        assert binary in ["pytest", "python", "npm", "git", "ruff"]
'''

# 5. tests/test_filesystem.py
test_files["test_filesystem.py"] = '''import pytest
from tools.filesystem import (
    list_files,
    read_file,
    write_file,
    create_directory,
    delete_file
)
from server.session import session_manager

def test_filesystem_crud(test_environment):
    session_manager.set_active_repo_name("Repo_A")

    # 1. Create directory
    mkdir_res = create_directory("src/utils")
    assert mkdir_res["success"] is True

    # 2. Write file
    write_res = write_file("src/utils/math_helper.py", "def add(a, b):\\n    return a + b\\n")
    assert write_res["success"] is True

    # 3. List files
    list_res = list_files("src/utils")
    assert list_res["count"] >= 1
    paths = [e["path"] for e in list_res["entries"]]
    assert any("math_helper.py" in p for p in paths)

    # 4. Read file
    read_res = read_file("src/utils/math_helper.py")
    assert "def add(a, b):" in read_res["content"]
    assert read_res["total_lines"] == 2

    # 5. Read file line range
    range_res = read_file("src/utils/math_helper.py", start_line=1, end_line=1)
    assert range_res["content"].strip() == "def add(a, b):"

    # 6. Delete file
    del_res = delete_file("src/utils/math_helper.py")
    assert del_res["success"] is True

    # Verify deleted
    verify_res = read_file("src/utils/math_helper.py")
    assert "error" in verify_res
'''

# 6. tests/test_search.py
test_files["test_search.py"] = '''import pytest
from tools.search import search_code
from tools.filesystem import write_file, create_directory
from server.session import session_manager

def test_search_code_within_active_repo(test_environment):
    session_manager.set_active_repo_name("Repo_A")
    write_file("src/search_target.py", "def unique_search_marker_12345():\\n    return True\\n")

    res = search_code("unique_search_marker_12345")
    assert res["total_matches"] >= 1
    match = res["results"][0]
    assert "search_target.py" in match["file"]
    assert "def unique_search_marker_12345" in match["snippet"]

def test_search_code_ignores_ignored_directories(test_environment):
    session_manager.set_active_repo_name("Repo_A")
    # Write into node_modules (which should be skipped)
    create_directory("node_modules")
    write_file("node_modules/ignore_marker.js", "const SECRET_IGNORE_TOKEN = 9999;")

    res = search_code("SECRET_IGNORE_TOKEN")
    assert res["total_matches"] == 0
'''

# 7. tests/test_terminal.py
test_files["test_terminal.py"] = '''import pytest
from tools.terminal import run_command
from server.session import session_manager

def test_run_command_in_active_repo(test_environment):
    session_manager.set_active_repo_name("Repo_A")

    # Run Python inline command
    res = run_command('python -c "print(123 + 456)"')
    assert res["exit_code"] == 0
    assert "579" in res["stdout"]

def test_run_blocked_command(test_environment):
    session_manager.set_active_repo_name("Repo_A")

    res = run_command("rm -rf /")
    assert "error" in res
    assert "Security Violation" in res["error"]

def test_run_command_timeout(test_environment):
    session_manager.set_active_repo_name("Repo_A")

    # Command exceeding timeout
    res = run_command('python -c "import time; time.sleep(5)"', timeout=1)
    assert "error" in res
    assert "timed out" in res["error"].lower()
'''

# 8. tests/test_git.py
test_files["test_git.py"] = '''import pytest
from tools.git import git_status, git_diff, git_branch
from tools.filesystem import write_file
from server.session import session_manager

def test_git_tools_in_active_repo(test_environment):
    session_manager.set_active_repo_name("Repo_A")

    # Initial status
    status_res = git_status()
    assert status_res["exit_code"] == 0

    # Modify file to produce a diff
    write_file("README.md", "# Repo A - Modified for Diff Test\\nUpdated content.")
    diff_res = git_diff()
    assert diff_res["exit_code"] == 0
    assert "Modified for Diff Test" in diff_res["diff"]

    # Check branch
    branch_res = git_branch()
    assert branch_res["exit_code"] == 0
'''

# Write all test files
for rel_path, content in test_files.items():
    dest = BASE_DIR / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created Test File: {dest}")

print("All test files successfully written.")
