import pytest
from app.core.security import security_engine, SecurityError
from app.core.session import session_manager

def test_path_traversal_attacks(test_environment):
    session_manager.set_active_repo_name("Repo_A")
    repo_b = test_environment["repo_b"]

    # 1. Parent folder dot-dot attacks
    with pytest.raises(SecurityError):
        security_engine.sanitize_and_resolve_path("../../secret.txt")

    with pytest.raises(SecurityError):
        security_engine.sanitize_and_resolve_path("..\\\\..\\\\secret.txt")

    # 2. Windows absolute external paths
    with pytest.raises(SecurityError):
        security_engine.sanitize_and_resolve_path("C:\\Windows\\System32")

    # 3. Cross-repository access attempt (Repo A active -> attempt Repo B)
    with pytest.raises(SecurityError):
        security_engine.sanitize_and_resolve_path(str(repo_b / "private_b.txt"))

    # 4. UNC network path injection
    with pytest.raises(SecurityError):
        security_engine.sanitize_and_resolve_path("\\\\remote-server\\malicious\\payload")
