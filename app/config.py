from pathlib import Path
from typing import List, Set, Optional
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

    # Authentication Configuration. Cloud mode always requires a strong token.
    MCP_AUTH_ENABLED: bool = False
    MCP_AUTH_TOKEN: str = ""
    MCP_DEPLOYMENT_MODE: str = "local"  # local | cloud

    # Hosted GitHub workspaces. Comma-separated OWNER/REPOSITORY allowlist.
    MCP_GITHUB_CLONE_ENABLED: bool = False
    MCP_GITHUB_ALLOWED_REPOS: str = ""
    MCP_GITHUB_TOKEN: str = ""
    MCP_WORKSPACE_ROOT: str = "/tmp/mcp-workspaces"

    # Remote Git delivery is opt-in and can require a matching, unexpired approval.
    MCP_GIT_PUSH_ENABLED: bool = False
    MCP_GIT_PUSH_REQUIRE_APPROVAL: bool = True

    # Real coding-worker subprocesses. JSON object: {"codex":["codex","exec","--full-auto","{prompt}"]}
    MCP_WORKER_COMMANDS: str = ""
    MCP_WORKER_MAX_CONCURRENCY: int = 3
    MCP_WORKER_TIMEOUT_SECONDS: int = 1800
    MCP_WORKER_SANDBOX_MODE: str = "docker"  # docker | host
    MCP_WORKER_SANDBOX_IMAGE: str = "mcp-coding-worker:latest"
    MCP_WORKER_NETWORK_MODE: str = "none"  # none | bridge; bridge explicitly permits outbound network
    MCP_WORKER_CREDENTIAL_MOUNTS: str = ""  # JSON array of {"source": "...", "target": "/home/worker/.config/..."} read-only mounts
    MCP_WORKER_HOST_MODE_ALLOWED: bool = False
    MCP_WORKER_SYNTHESIS_ENABLED: bool = False  # Optional model-based synthesis; structured synthesis works without API calls.
    # Independent checks run in fresh subprocesses; commands are argv arrays, never shell strings.
    MCP_VERIFICATION_COMMANDS: str = ""
    MCP_VERIFICATION_TIMEOUT_SECONDS: int = 600
    # Dashboard is protected by BearerAuthMiddleware whenever MCP_AUTH_ENABLED=true.
    MCP_DASHBOARD_ENABLED: bool = True

    # Optional OpenAI-compatible model provider for autonomous orchestration
    MCP_LLM_API_KEY: str = ""
    MCP_LLM_BASE_URL: str = "https://api.openai.com/v1"
    MCP_LLM_MODEL: str = ""
    MCP_LLM_INPUT_COST_PER_1M: Optional[float] = None
    MCP_LLM_OUTPUT_COST_PER_1M: Optional[float] = None

    # Repository Registry Configuration
    REPOSITORIES_CONFIG_PATH: str = str(
        Path(__file__).resolve().parent.parent / "config" / "repositories.json"
    )

    # Tunnel Configuration
    CLOUDFLARED_PATH: str = ""
    TUNNEL_MODE: str = "quick"
    NGROK_DOMAIN: str = ""
    CLOUDFLARE_TUNNEL_TOKEN: str = ""
    STATIC_TUNNEL_URL: str = ""

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

    # Allowed Command Binaries (Allowlist). PowerShell is explicitly enabled;
    # terminal validation still rejects shell operators and dangerous patterns.
    ALLOWED_COMMAND_BINARIES: Set[str] = {
        "python", "python3", "pytest", "pip", "uv", "poetry",
        "npm", "node", "npx", "yarn", "pnpm",
        "git", "ruff", "mypy", "flake8", "black", "isort", "pylint",
        "cargo", "go", "dir", "echo", "where", "cat", "findstr",
        "powershell", "pwsh"
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
