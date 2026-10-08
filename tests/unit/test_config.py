from pathlib import Path
from app.config import settings

def test_settings_defaults():
    assert settings.MCP_HOST == "127.0.0.1"
    assert settings.MCP_PORT > 0
    assert settings.MAX_FILE_SIZE_BYTES > 0
    assert settings.COMMAND_TIMEOUT_SECONDS > 0
    assert len(settings.BLOCKED_PATTERNS) > 0
    assert "python" in settings.ALLOWED_COMMAND_BINARIES
    assert "rm -rf" in settings.BLOCKED_COMMANDS
