from app.config import settings

def test_config_has_safety_limits_and_blocked_patterns():
    assert settings.MAX_FILE_SIZE_BYTES > 0
    assert settings.COMMAND_TIMEOUT_SECONDS > 0
    assert len(settings.BLOCKED_PATTERNS) > 0
    assert "python" in settings.ALLOWED_COMMAND_BINARIES
    assert "powershell" in settings.ALLOWED_COMMAND_BINARIES
    assert "pwsh" in settings.ALLOWED_COMMAND_BINARIES
    assert "rm -rf" in settings.BLOCKED_COMMANDS
