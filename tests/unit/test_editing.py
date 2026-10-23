from app.core.session import session_manager
from app.tools.editing import replace_in_file


def test_replace_in_file_exact_match_updates_file(test_environment):
    session_manager.set_active_repo_name("Repo_A")
    target = test_environment["repo_a"] / "edit-success.txt"
    target.write_text("Sample application\n", encoding="utf-8")

    result = replace_in_file("edit-success.txt", "Sample application", "Sample coding-agent")
    assert result.get("success") is True, result
    assert result["replacements"] == 1
    assert "Sample coding-agent" in target.read_text(encoding="utf-8")


def test_replace_in_file_aborts_on_unexpected_occurrence_count(test_environment):
    session_manager.set_active_repo_name("Repo_A")
    target = test_environment["repo_a"] / "edit-mismatch.txt"
    target.write_text("Repo string\n", encoding="utf-8")
    before = target.read_text(encoding="utf-8")

    result = replace_in_file("edit-mismatch.txt", "Repo", "Workspace", expected_occurrences=2)

    assert "error" in result
    assert result["unchanged"] is True
    assert target.read_text(encoding="utf-8") == before


def test_replace_in_file_protects_secret_files(test_environment):
    session_manager.set_active_repo_name("Repo_A")
    result = replace_in_file(".env", "supersecret", "redacted")
    assert "error" in result
    assert "Security Violation" in result["error"]


def test_replace_in_file_refuses_invalid_utf8(test_environment):
    session_manager.set_active_repo_name("Repo_A")
    target = test_environment["repo_a"] / "edit-binary.bin"
    target.write_bytes(b"hello\xffworld")
    before = target.read_bytes()

    result = replace_in_file("edit-binary.bin", "hello", "changed")

    assert "error" in result
    assert target.read_bytes() == before
