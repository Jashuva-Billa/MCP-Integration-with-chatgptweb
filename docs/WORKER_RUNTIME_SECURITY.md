# Worker runtime, verification, and benchmark setup

## Real coding workers

The server starts configured CLI processes; it does not pretend to create extra ChatGPT Web sessions. Install and authenticate the worker CLIs or provide a container image that contains them. Configure argv arrays (never shell command strings) in the private `.env` file:

```dotenv
MCP_WORKER_COMMANDS={"codex":["codex","exec","--full-auto","{prompt}"],"claude":["claude","-p","{prompt}"],"cursor":["agent","-p","{prompt}"]}
MCP_WORKER_MAX_CONCURRENCY=3
MCP_WORKER_TIMEOUT_SECONDS=1800
MCP_WORKER_SANDBOX_MODE=docker
MCP_WORKER_SANDBOX_IMAGE=mcp-coding-worker:latest
MCP_WORKER_NETWORK_MODE=none
```

The command arrays are examples; validate the exact CLI syntax for the installed versions. Each worker gets a separate Git worktree and process, persistent status, captured output, a diff, timeout handling, and cancellation. Worker results are not merged automatically. The default synthesis is a structured, deterministic summary; optional model-based synthesis requires explicit `MCP_WORKER_SYNTHESIS_ENABLED=true` and a configured model provider, and may incur provider cost.

### Sandbox and credentials

The default Docker mode uses a container with no network, resource limits, dropped Linux capabilities, no-new-privileges, and only the worker worktree mounted writable. The image must contain the configured CLI executable and dependencies. Network access is disabled by default; set `MCP_WORKER_NETWORK_MODE=bridge` only when a worker needs outbound model access and you accept that risk.

CLI authentication should be provided through narrowly scoped, read-only mounts configured with `MCP_WORKER_CREDENTIAL_MOUNTS`, a JSON array of `{"source":"host-path","target":"/home/worker/.config/cli"}` objects. Mount only the exact CLI configuration directory needed; never mount the entire home directory or the repository's `.env`. Container users/paths must match the image. Do not bake tokens into the image.

Host mode is intentionally opt-in:
```dotenv
MCP_WORKER_SANDBOX_MODE=host
MCP_WORKER_HOST_MODE_ALLOWED=true
```
Host mode is not an OS sandbox and cannot enforce network isolation. Use only on a trusted local development machine.

Worker processes receive a minimal environment rather than all parent environment variables. Worker logs, output, diffs, and verification output pass through secret-pattern redaction. Redaction is defense in depth, not a guarantee against every possible secret format.

## Independent verification

By default, each verification runs in fresh subprocesses:
- `python -m pytest -q`
- `ruff check app tests`

The checks are configurable using `MCP_VERIFICATION_COMMANDS`, a JSON array of argv arrays. Only allowlisted test/lint executables are accepted; shell strings, pipes, and redirects are rejected. Verification evidence records check results, revision stability, timestamps, and an evidence ID. Task completion requires a passing independent verification in addition to completed plan steps and a recorded passing test.

If Ruff is not installed, install the development dependencies (for example, `pip install -e .[dev]`) or configure an available linter. Missing configured checks fail closed.

## Task state machine

Tasks persist a phase in addition to the broader status:
`planning -> execution -> testing -> review -> approval -> merging -> completed`.
Failed/cancelled tasks can be resumed through the supported transition graph. Illegal transitions are rejected. Evidence IDs are attached to review/completion phases. Approval and merge remain separate; a worker finishing does not grant merge permission.

## Benchmarking Codex, Claude Code, Cursor, and MCP

Use `start_worker_benchmark` with the same case JSON and selected configured worker names. The harness requires a clean baseline, records its Git revision, runs each case in independent worktrees, saves worker logs/diffs, runs independent verification, and reports success/time. Cost remains `null` unless the CLI exposes reliable cost metadata. The harness does not automatically claim results are comparable if a worker is unavailable or checks fail.

Example case payload:
```json
[
  {"name":"fix-parser-empty-input","objective":"Fix the parser crash on empty input and add a regression test."},
  {"name":"repair-auth-regression","objective":"Fix the authentication regression described in tests and add coverage."}
]
```

The first call returns a run ID. Poll `get_worker_benchmark(run_id)` or the dashboard API until status is completed. Review diffs and verification evidence before any merge.

## Dashboard authentication

When `MCP_AUTH_ENABLED=true`, the dashboard and all `/api/*` endpoints require the same Bearer token middleware as the MCP endpoints. Set `MCP_DASHBOARD_ENABLED=false` to disable them. The app refuses to bind to a non-loopback host without authentication. For a public deployment, use a strong token, exact allowed host/origin values, TLS at the ingress, and avoid mounting credentials into workers unless necessary.
