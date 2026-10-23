"""
Tests for the expanded filesystem tools: delete_directory, move_file,
copy_file, backup_file, restore_file, diff_preview.
"""
import json
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_repo(tmp_path, monkeypatch):
    """Create a temporary repo with test files and point the session at it."""
    repo = tmp_path / "TestRepo"
    repo.mkdir()
    (repo / "README.md").write_text("# Test", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("def hello(): return 'hello'\n", encoding="utf-8")
    (repo / "src" / "util.py").write_text("def helper(): pass\n", encoding="utf-8")
    (repo / "subdir").mkdir()
    (repo / "subdir" / "child.txt").write_text("child content", encoding="utf-8")

    # Point session to this repo
    from app.core.session import session_manager
    from app.core.repository import repository_manager
    cfg = tmp_path / "repos.json"
    cfg.write_text(json.dumps({"repositories": {"TestRepo": {"path": str(repo), "enabled": True}}}), encoding="utf-8")
    monkeypatch.setattr(repository_manager, "config_path", cfg)
    session_manager.set_active_repo_name("TestRepo")
    return repo


@pytest.fixture(autouse=True)
def use_full_profile():
    from app.core.permissions import policy_engine, PermissionProfile, PROFILES
    policy_engine._profile = PermissionProfile.FULL
    policy_engine._rules = PROFILES[PermissionProfile.FULL]
    yield
    policy_engine._profile = PermissionProfile.FULL
    policy_engine._rules = PROFILES[PermissionProfile.FULL]


# ---------------------------------------------------------------------------
# delete_directory tests
# ---------------------------------------------------------------------------

class TestDeleteDirectory:
    def test_dry_run_lists_files_without_deleting(self, tmp_repo):
        from app.tools.filesystem import delete_directory
        result = delete_directory("subdir", dry_run=True)
        assert result["dry_run"] is True
        assert "subdir/child.txt" in result["would_delete"]
        assert (tmp_repo / "subdir").exists()   # not deleted

    def test_actual_delete_removes_directory(self, tmp_repo):
        from app.tools.filesystem import delete_directory
        result = delete_directory("subdir")
        assert result["success"] is True
        assert not (tmp_repo / "subdir").exists()

    def test_refuses_to_delete_repo_root(self, tmp_repo):
        from app.tools.filesystem import delete_directory
        result = delete_directory(".")
        assert "error" in result
        assert "root" in result["error"].lower()

    def test_safe_profile_denies_delete_directory(self, tmp_repo):
        from app.core.permissions import policy_engine, PermissionProfile, PROFILES
        from app.tools.filesystem import delete_directory
        policy_engine._profile = PermissionProfile.SAFE
        policy_engine._rules = PROFILES[PermissionProfile.SAFE]
        result = delete_directory("subdir")
        assert "error" in result
        assert "Permission denied" in result["error"]

    def test_nonexistent_path_returns_error(self, tmp_repo):
        from app.tools.filesystem import delete_directory
        result = delete_directory("does_not_exist")
        assert "error" in result

    def test_rejects_file_path(self, tmp_repo):
        from app.tools.filesystem import delete_directory
        result = delete_directory("README.md")
        assert "error" in result


# ---------------------------------------------------------------------------
# move_file tests
# ---------------------------------------------------------------------------

class TestMoveFile:
    def test_rename_file(self, tmp_repo):
        from app.tools.filesystem import move_file
        result = move_file("README.md", "DOCS.md")
        assert result["success"] is True
        assert not (tmp_repo / "README.md").exists()
        assert (tmp_repo / "DOCS.md").exists()

    def test_move_to_subdirectory(self, tmp_repo):
        from app.tools.filesystem import move_file
        result = move_file("src/util.py", "subdir/util.py")
        assert result["success"] is True
        assert (tmp_repo / "subdir" / "util.py").exists()

    def test_overwrite_false_prevents_clobber(self, tmp_repo):
        from app.tools.filesystem import move_file
        result = move_file("README.md", "src/app.py", overwrite=False)
        assert "error" in result

    def test_overwrite_true_replaces(self, tmp_repo):
        from app.tools.filesystem import move_file
        result = move_file("README.md", "src/app.py", overwrite=True)
        assert result["success"] is True


# ---------------------------------------------------------------------------
# copy_file tests
# ---------------------------------------------------------------------------

class TestCopyFile:
    def test_copy_creates_new_file(self, tmp_repo):
        from app.tools.filesystem import copy_file
        result = copy_file("README.md", "README_copy.md")
        assert result["success"] is True
        assert (tmp_repo / "README.md").exists()     # original preserved
        assert (tmp_repo / "README_copy.md").exists()

    def test_copy_overwrite_false(self, tmp_repo):
        from app.tools.filesystem import copy_file
        result = copy_file("README.md", "src/app.py", overwrite=False)
        assert "error" in result


# ---------------------------------------------------------------------------
# backup_file / restore_file tests
# ---------------------------------------------------------------------------

class TestBackupRestore:
    def test_backup_creates_bak_file(self, tmp_repo):
        from app.tools.filesystem import backup_file
        result = backup_file("README.md")
        assert result["success"] is True
        bak = Path(result["backup"])
        assert bak.name.startswith("README.md.bak.")
        assert (tmp_repo / bak).exists()

    def test_restore_overwrites_original(self, tmp_repo):
        from app.tools.filesystem import backup_file, restore_file, write_file
        bk = backup_file("README.md")
        assert bk["success"]
        # Overwrite original
        write_file("README.md", "# Changed")
        assert (tmp_repo / "README.md").read_text() == "# Changed"
        # Restore
        result = restore_file(bk["backup"])
        assert result["success"] is True
        assert "Test" in (tmp_repo / "README.md").read_text()


# ---------------------------------------------------------------------------
# diff_preview tests
# ---------------------------------------------------------------------------

class TestDiffPreview:
    def test_diff_shows_changes(self, tmp_repo):
        from app.tools.filesystem import diff_preview
        result = diff_preview("README.md", "# Changed\n")
        assert result["has_changes"] is True
        assert "diff" in result
        assert result["lines_changed"] > 0

    def test_no_diff_when_identical(self, tmp_repo):
        from app.tools.filesystem import diff_preview
        original = (tmp_repo / "README.md").read_text()
        result = diff_preview("README.md", original)
        assert result["has_changes"] is False

    def test_nonexistent_file_returns_error(self, tmp_repo):
        from app.tools.filesystem import diff_preview
        result = diff_preview("ghost.py", "content")
        assert "error" in result
