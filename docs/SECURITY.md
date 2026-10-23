# Security Policy & Defense Matrix

## 1. Security Architecture

The standalone MCP server enforces defense-in-depth across six distinct security barriers:

```
[Incoming Request]
       |
       v
[Bearer Authentication Guard] -> [Invalid/Missing Token: 401 Unauthorized]
       |
       v
[Session Isolation Controller] -> [Unselected Repo: 400 Bad Request]
       |
       v
[SecurityEngine Layer]
       |                    |                  |
       v                    v                  v
[Path Traversal Check] [Secret Shield] [Command Allowlist]
- Canonical .resolve() - Block .env, *.key - Approved binaries only
- Strict root boundary - Block *.pem, *.p12 - Deny dangerous patterns
- Check symlink targets - Block credentials
- Block UNC network
       |
       v
[Execute Local Operation]
```

---

## 2. Path Traversal & Filesystem Containment

- **Canonical Path Resolution**: All file and directory operations use `Path.resolve()` to eliminate relative dot-dot (`..`) traversal patterns.
- **Strict Boundary Check**: Every resolved path is checked against the active repository root. Any path attempting to access system folders, external directories, or other registered repositories raises a `SecurityError`.
- **Symlink Escape Guard**: Symlinks targeting locations outside the active repository root are detected and blocked.
- **UNC Paths**: Network share paths are unconditionally rejected.

---

## 3. Secret Protection

Access to files matching the following patterns is strictly prohibited during `read_file`, `write_file`, and `search_code`:
- `.env`, `.env.*`, `*.env`
- `*.pem`, `*.key`, `*.p12`, `*.pfx`, `*.cer`, `*.crt`
- `*credentials*.json`, `*secrets*.json`, `*token*.json`
- `id_rsa*`, `id_ed25519*`, `id_ecdsa*`, `id_dsa*`
- `*.keystore`, `*.jks`, `*.p8`
- `.git/config`, `.git/credentials`

---

## 4. Command Security & Terminal Sandbox

- **Working Directory**: Terminal commands execute with `cwd` locked to the active repository root.
- **Allowed Binaries**: Approved development binaries include `python`, `pytest`, `pip`, `npm`, `node`, `git`, `ruff`, `mypy`, `cargo`, `go`, `powershell`, and `pwsh`.
- **PowerShell**: `powershell` and `pwsh` are enabled in the repository-level executable allowlist. This does not override any outer MCP client/host allowlist. The terminal uses `shell=False`, rejects shell operators and configured dangerous command patterns, and remains subject to OS permissions. These checks are not a substitute for an OS-level sandbox.
- **Blocked Commands**: Configured destructive command patterns (`rm -rf`, `del /s`, `format`, `shutdown`, `diskpart`, `git reset --hard`, `git push`, `git commit`) are rejected.
- **Process Protection**: Commands run with an execution timeout (default 120s) and stdout/stderr output capping (100KB) to prevent resource exhaustion.
