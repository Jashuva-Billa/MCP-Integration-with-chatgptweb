import sys
from pathlib import Path

# Ensure app package is on sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
import subprocess
import shutil
import json
from app.config import settings
from app.core.repository import repository_manager
from app.core.session import session_manager

@pytest.fixture(scope="session")
def test_environment(tmp_path_factory):
    root = tmp_path_factory.mktemp("mcp_full_test_env")
    repo_a = root / "Repo_A"
    repo_b = root / "Repo_B"
    repo_a.mkdir()
    repo_b.mkdir()

    # Initialize Git in repo_a
    subprocess.run(["git", "init"], cwd=str(repo_a), capture_output=True)
    subprocess.run(["git", "config", "user.name", "TestUser"], cwd=str(repo_a), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_a), capture_output=True)

    # Populate repo_a
    (repo_a / "README.md").write_text("# Repo A\nSample application repository for testing.", encoding="utf-8")
    (repo_a / "requirements.txt").write_text("fastapi>=0.100.0\npytest>=8.0.0\n", encoding="utf-8")
    (repo_a / "src").mkdir()
    (repo_a / "src" / "app.py").write_text(
        "class Calculator:\n"
        "    def add(self, a: int, b: int) -> int:\n"
        "        return a + b\n\n"
        "def main():\n"
        "    calc = Calculator()\n"
        "    print(calc.add(2, 3))\n",
        encoding="utf-8"
    )
    (repo_a / ".env").write_text("DATABASE_PASSWORD=supersecret\nAPI_KEY=abc123secret\n", encoding="utf-8")
    (repo_a / "credentials.json").write_text('{"token": "xyz_secret_999"}\n', encoding="utf-8")

    # Initial commit in repo_a
    subprocess.run(["git", "add", "README.md", "requirements.txt", "src/app.py"], cwd=str(repo_a), capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial test commit"], cwd=str(repo_a), capture_output=True)

    # Populate repo_b
    (repo_b / "README.md").write_text("# Repo B\nIsolated second repository.", encoding="utf-8")
    (repo_b / "private_b.txt").write_text("Secret in Repo B", encoding="utf-8")

    # Configure temporary repositories.json
    config_json = root / "test_repositories.json"
    settings.REPOSITORIES_CONFIG_PATH = str(config_json)
    repository_manager.config_path = config_json

    with open(config_json, "w", encoding="utf-8") as f:
        json.dump({
            "repositories": {
                "Repo_A": {"path": str(repo_a), "description": "Mock Repo A", "enabled": True},
                "Repo_B": {"path": str(repo_b), "description": "Mock Repo B", "enabled": True}
            }
        }, f, indent=2)

    session_manager.set_active_repo_name("Repo_A")

    return {
        "root": root,
        "repo_a": repo_a,
        "repo_b": repo_b,
        "config_json": config_json
    }
