# Claude Code–Style Engineering Agent: Gap Analysis & Roadmap

**Audit date:** 2026-10-23  
**Status:** Audit Requirements Implemented & Verified (79 Tests Passing)  
**Scope:** MCP server repository `MCP`, transformed into an autonomous coding agent platform.

## Implemented & Verified Capabilities

- **4-Tier Centralized Permission Profiles**: `safe`, `full`, `trusted_admin` (new), and `unrestricted` with capability gating for filesystem, commands, Git writes, remote push/pull/fetch, and network authorization.
- **Git Operations Suite (16 Tools)**: Complete read, write, and remote operations including `git_push`, `git_fetch`, and `git_pull` with remote sanitization, branch safety, and network gating.
- **Robust Command Execution**: Process-tree termination (`_terminate_process_tree`) on timeout, secret redaction, truncation metrics, and automated failure diagnostics (`diagnose_command_failure`) categorizing `TIMEOUT`, `MISSING_DEPENDENCY`, `SYNTAX_ERROR`, `TEST_FAILURE`, `PERMISSION_DENIED`, `PORT_IN_USE`, and `GIT_CONFLICT`.
- **Network Permission Authorization**: Direct linkage of `network_access` permission flag to `install_dependencies`, `git_push`, `git_fetch`, and `git_pull`.
- **Autonomous Task State & Memory**: Resumable multi-step planning, automated checkpoints, test history, `plan_repair_attempt` tracking root cause & hypotheses, and `verify_task` validating tests, plan steps, and working tree cleanliness.
- **Skills & Hooks System**: Reusable workflows (`skills/`) and event-driven lifecycle triggers (`.mcp/hooks.json`).
- **Discovery & Discovery Endpoints**: Dynamic `/tools` listing all 60 tools across 15 categories, plus `/health` reporting active profiles and transports.


## Highest-priority gaps and risks

### P0 — Harden public exposure and execution

1. `app/main.py` disables DNS rebinding protection and configures wildcard hosts/origins. Do not expose this service publicly with those settings without understanding the MCP SDK threat model and establishing explicit, deployment-appropriate host/origin rules.
2. Bearer authentication defaults to disabled. Public tunnel deployments should fail closed unless a strong token or stronger supported authentication is configured.
3. `run_command` launches approved binaries with `shell=False`, which is good, but the security model remains a denylist around powerful interpreters such as PowerShell and Python. A list of forbidden command substrings is not a sufficient sandbox. Use explicit permissions, executable resolution, argument policies, low-privilege OS account/container, environment scrubbing, resource limits, and command audit logs.
4. Session state has a mutable global default workspace. `set_active_repo_name()` updates `_default_workspace` even if a session ID was supplied. Verify that all client operations truly carry a stable per-session identity; otherwise a client switching repositories may affect another conversation.
5. File writes are direct and have no patch preview or automatic backup/revert mechanism. Add unified-diff editing and clear change summaries before large edits.
6. File-size/output caps are helpful but do not protect against CPU, memory, network, or subprocess-tree exhaustion.

### P1 — Essential coding-agent workflow

- Unified diff preview/apply/reject and structured multi-file edit support; `replace_in_file` is a precise single-file building block, not yet a full patch workflow.
- A test/build/lint/typecheck runner that detects repository scripts and reports concise failures.
- A diagnostics tool that discovers available linters, formatters, test runners, language servers, and package scripts.
- A search tool with glob include/exclude patterns and optional regex while retaining secret filtering.
- Better symbol navigation, especially language-server-backed definitions/references and diagnostics for TypeScript, Java, Go, Rust, etc.
- Git write operations behind explicit approval: create branch, stage selected files, commit, push. Keep destructive reset/clean and force-push separate and opt-in.
- Task plans/checklists, step status, cancellation, progress events, and a final summary that lists changed files and verification outcomes.
- Context gathering that reads relevant README/config/source/test files before editing and summarizes findings to avoid indiscriminate repository dumps.

### P2 — Advanced capabilities

- LSP integrations for diagnostics, definitions, references, rename, and code actions.
- Multi-step agent loop in a compatible client: plan → inspect → edit → test → diagnose → repair → verify.
- Persistent task/workspace memory with explicit scope and retention, without storing secrets.
- Optional isolated worktrees or disposable containers for experimental edits.
- Browser/docs research through explicitly configured tools, with provenance and untrusted-input handling.
- CI integration, test coverage summaries, performance profiling, and traceable command/tool audit logs.
- Multi-agent specialists only after the core edit/verify loop is reliable; agents without strong task boundaries and verification can increase failure modes rather than capability.

## Target architecture

1. **MCP tool server** — stable, narrowly scoped typed tools, auth, session identity, path controls, audit logs.
2. **Workspace engine** — repo discovery, file indexing, ignore-aware search, repository metadata, LSP adapters.
3. **Edit engine** — diff-first patch application, syntax-aware edits where possible, backups, validation, clear change report.
4. **Execution engine** — detected test/lint/build tasks, process-tree timeouts, bounded output, environment policy, OS/container isolation.
5. **Git engine** — read operations by default; writes require an explicit permission policy.
6. **Agent orchestration** — planning, tool selection, iterative repair, context budgeting, cancellation, and verification. The connected reasoning client supplies model reasoning unless a separate orchestrator is intentionally added.
7. **Observability** — structured logs, per-request IDs, timings, exit codes, redacted command arguments, and security events.

## Acceptance criteria for meaningful parity

- Selecting a repository is isolated per MCP session; automated concurrency tests prove one session cannot change another's active workspace.
- Path traversal, symlink traversal, secret reads, command injection, interpreter abuse, unauthenticated public access, oversized output, timeout, and subprocess-child cleanup tests pass.
- A coding task can inspect the repo, produce a patch, apply changes, run the relevant tests, diagnose failures, attempt a repair, and report evidence.
- Every changed file is listed and the final diff is inspectable.
- Destructive operations are denied by default; safe Git writes are individually configurable.
- Tool failures return structured actionable errors rather than broad exception strings.
- A clean install and the documented Windows start/stop workflow are covered by diagnostics/tests.

## Recommended implementation sequence

1. **Security/session stabilization** before adding broad terminal permissions.
2. **Diff-first editing and verification tools** to close the biggest day-to-day coding gap.
3. **Test/lint/build detection** with structured results and better process lifecycle handling.
4. **Language intelligence** via LSP or compiler-native tooling.
5. **Explicit Git workflow permissions**, audit trails, and optional worktree isolation.
6. **Agent orchestration and memory**, with task-level verification and cancellation.
7. **Compatibility, performance, and end-to-end tests** using representative repositories.

## Important operating note

The repository connector exhibited inconsistent workspace targeting during this audit: after selecting `MCP`, some later tool calls intermittently returned results from `AI_jobs_apply`. The selection API sometimes corrected this on retry. This may be a connector/session-routing issue rather than a bug in this repository's own `SessionManager`. It should be reproduced and diagnosed independently before trusting cross-repository write workflows.
