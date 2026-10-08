# Security Policy & Defense Matrix

## 1. Security Architecture

The standalone MCP server enforces defense-in-depth across six distinct security barriers:

```
[Incoming Request]
       │
       ▼
┌─────────────────────────────────┐
│ 1. Bearer Authentication Guard  │ ──► [Invalid/Missing Token: 401 Unauthorized]
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│ 2. Session Isolation Controller │ ──► [Unselected Repo: 400 Bad Request]
└──────────────┬──────────────────┘
               │ Active Workspace: C:\Development\RepoA
               ▼
┌─────────────────────────────────────────────────────────────┐
│                   3. SecurityEngine Layer                   │
└──────┬───────────────────────┬───────────────────────┬──────┘
       │                       │                       │
       ▼                       ▼                       ▼
[Path Traversal Check]   [Secret Shield]      [Command Allowlist]
- Canonical .resolve()   - Block .env, *.key  - Permitted: python, pytest,
- Strict .is_relative_to - Block *.pem, *.p12   npm, git, ruff, mypy
- Check symlink targets  - Block credentials  - Denied: rm -rf, del /s,
- Block UNC network      - Block tokens, certs  format, git push/commit
       │                       │                       │
       └───────────────────────┼───────────────────────┘
                               │ (All checks PASS)
                               ▼
                   [Execute Local Operation]
```

---

## 2. Path Traversal & Filesystem Containment

- **Canonical Path Resolution**: All file and directory operations use `Path.resolve()` to eliminate relative dot-dot (`..`) traversal patterns.
- **Strict Boundary Check**: Every resolved path is checked with `target.is_relative_to(clean_root)`. Any path attempting to access system folders (`C:\Windows`, `/etc/`), external directories, or other registered repositories raises a `SecurityError`.
- **Symlink Escape Guard**: Symlinks targeting locations outside the active repository root are detected and blocked.
- **UNC Paths**: Network share paths (`\\\\server\\share`) are unconditionally rejected.

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
- **Allowed Binaries**: Only approved development binaries (`python`, `pytest`, `pip`, `npm`, `node`, `git`, `ruff`, `mypy`, `cargo`, `go`, etc.) are permitted.
- **Blocked Commands**: Destructive commands (`rm -rf`, `del /s`, `format`, `shutdown`, `diskpart`, `git reset --hard`, `git push`, `git commit`) are strictly rejected.
- **Process Protection**: Commands run with an execution timeout (default 120s) and stdout/stderr output capping (100KB) to prevent resource exhaustion.
