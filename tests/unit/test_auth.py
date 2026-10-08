from app.auth.auth import verify_token

def test_verify_token_valid():
    assert verify_token("secret123", "secret123") is True

def test_verify_token_invalid():
    assert verify_token("wrong", "secret123") is False
    assert verify_token("", "secret123") is False
    assert verify_token("secret123", "") is False
