import pytest
from app.core.security import SecurityEngine, SecurityError

def test_security_path_and_command_validation(test_environment):
    sec = SecurityEngine()
    repo_a = test_environment["repo_a"]

    # Safe path
    p = sec.verify_path_in_root("src/app.py", repo_a)
    assert p.exists()

    # Path traversal attack
    with pytest.raises(SecurityError):
        sec.verify_path_in_root("../../outside.txt", repo_a)

    # Secret file attack
    with pytest.raises(SecurityError):
        sec.verify_path_in_root(".env", repo_a)

    # Command security allowlist
    bin_name, _ = sec.validate_command_security("pytest tests/")
    assert bin_name == "pytest"

    # Blocked dangerous command
    with pytest.raises(SecurityError):
        sec.validate_command_security("rm -rf /")
