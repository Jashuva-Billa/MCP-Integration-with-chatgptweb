import os
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Server Network Configuration
    MCP_HOST: str = "127.0.0.1"
    MCP_PORT: int = 8766
    MCP_LOG_LEVEL: str = "INFO"

    # Authentication Configuration
    MCP_AUTH_ENABLED: bool = False
    MCP_AUTH_TOKEN: str = ""

    # Repository Registry Configuration
    REPOSITORIES_CONFIG_PATH: str = str(
        Path(__file__).resolve().parent.parent / "config" / "repositories.json"
    )

    # Tunnel Configuration
    CLOUDFLARED_PATH: str = ""
    TUNNEL_MODE: str = "quick"

    # Operational Safety Limits
    MAX_FILE_SIZE_BYTES: int = 2 * 1024 * 1024       # 2MB max file read/write
    MAX_COMMAND_OUTPUT_BYTES: int = 100 * 1024       # 100KB max stdout/stderr
    COMMAND_TIMEOUT_SECONDS: int = 120               # 120s max execution duration
    MAX_SEARCH_RESULTS: int = 100                    # Max search matches returned

    # Secret Files & Patterns Protection
    BLOCKED_PATTERNS: List[str] = [
        ".env", ".env.*", "*.env",
        "*.pem", "*.key", "*.p12", "*.pfx", "*.cer", "*.crt",
        "*credentials*.json", "*secrets*.json", "*token*.json",
        "id_rsa*", "id_ed25519*", "id_ecdsa*", "id_dsa*",
        "*.keystore", "*.jks", "*.p8",
        ".git/config", ".git/credentials"
    ]

    # Allowed Command Binaries (Allowlist)
    ALLOWED_COMMAND_BINARIES: Set[str] = {
        "python", "python3", "pytest", "pip", "uv", "poetry",
        "npm", "node", "npx", "yarn", "pnpm",
        "git", "ruff", "mypy", "flake8", "black", "isort", "pylint",
        "cargo", "go", "dir", "echo", "where", "cat", "findstr"
    }

    # Blocked Dangerous Command Patterns (Denylist)
    BLOCKED_COMMANDS: List[str] = [
        "format", "shutdown", "reboot", "diskpart",
        "rm -rf", "rm -r", "del /s", "del /f", "rmdir /s",
        "Remove-Item", "rd /s",
        "git reset --hard", "git clean -fd", "git clean -f",
        "git push", "git commit", "git rebase", "git merge",
        "sudo", "su", "ssh", "scp", "ftp",
        "powershell -enc", "powershell -encodedcommand",
        "curl | sh", "curl | bash", "wget | sh", "wget | bash"
    ]

settings = Settings()
