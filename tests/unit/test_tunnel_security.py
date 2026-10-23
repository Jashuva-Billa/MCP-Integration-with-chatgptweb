from scripts.tunnel import public_tunnel_auth_error


def test_public_tunnel_requires_authentication_enabled():
    assert "MCP_AUTH_ENABLED=true" in public_tunnel_auth_error(False, "x" * 48)


def test_public_tunnel_rejects_short_token():
    assert "at least 32" in public_tunnel_auth_error(True, "too-short")


def test_public_tunnel_accepts_enabled_long_token():
    assert public_tunnel_auth_error(True, "a" * 48) == ""
