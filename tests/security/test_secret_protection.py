import pytest
from app.core.security import security_engine, SecurityError
from app.core.session import session_manager

def test_secret_files_shield(test_environment):
    session_manager.set_active_repo_name("Repo_A")

    secret_targets = [
        ".env",
        ".env.production",
        "app.env",
        "credentials.json",
        "secrets.json",
        "jwt_token.json",
        "server.key",
        "cert.pem",
        "id_rsa",
        "id_ed25519"
    ]

    for target in secret_targets:
        with pytest.raises(SecurityError) as exc_info:
            security_engine.sanitize_and_resolve_path(target)
        assert "sensitive" in str(exc_info.value).lower() or "prohibited" in str(exc_info.value).lower()
