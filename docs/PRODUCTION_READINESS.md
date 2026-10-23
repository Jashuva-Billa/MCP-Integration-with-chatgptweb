# MCP Coding Tool: Production Readiness

This document describes the current reliability, workstream, safety, dashboard, benchmark, and Git delivery controls. The connected ChatGPT Web model remains the planner in the no-API-key workflow; this MCP server executes tools and persists state, but does not launch new ChatGPT Web sessions.

## Implemented in this iteration

- **Verified task completion:** `complete_task(verified=true)` refuses completion unless every plan step is `done` and at least one passing test result is recorded. `finish_chatgpt_coding_task` also runs final verification.
- **Persistent approval queue:** `request_approval`, `list_approvals`, and `resolve_approval` create expiring, target-specific decisions and audit-log them. An approval cannot be changed after resolution.
- **Configurable Git push:** `MCP_GIT_PUSH_ENABLED=false` by default. Enable only in a trusted environment and use a profile that authorizes push. `MCP_GIT_PUSH_REQUIRE_APPROVAL=true` by default; the approved request must match the exact `remote/branch` target. Push reports success only after `git ls-remote` confirms the remote branch SHA matches local `HEAD`.
- **Isolated workstream primitives:** create and remove worktrees, run a test command inside the worktree, and merge a validated branch only after an explicit approval, a clean target tree, and passing target-branch tests. Workstream branches use the `mcp-work/<task>/<worker>` namespace.
- **Developer dashboard:** open `/dashboard` on the MCP server. The page polls `/api/tasks`, `/api/approvals`, `/api/events`, and `/api/checkpoints`; it shows task progress, approval controls, redacted audit events, working/staged diff review, and one-click checkpoint recovery after a confirmation prompt. Recovery is restricted to checkpoints whose recorded repository root matches the active workspace. If authentication is enabled, the same server middleware protects these endpoints.
- **Benchmark provenance:** benchmark records include baseline revision, worktree cleanliness, case-start revision, and whether the case started from a clean baseline. External comparisons report whether case sets and repository revisions match. Unknown cost stays null.
- **Auditability:** push authorization failures, push results, approval decisions, workstream lifecycle, and task lifecycle are recorded in the existing redacted JSONL audit log.

## Configuration

```dotenv
# Remote Git delivery remains disabled unless explicitly enabled.
MCP_GIT_PUSH_ENABLED=false
MCP_GIT_PUSH_REQUIRE_APPROVAL=true

# Remote cloning is a separate capability and also requires an allowlist.
MCP_GITHUB_CLONE_ENABLED=false
MCP_GITHUB_ALLOWED_REPOS=
```

To enable a push in a trusted deployment, set `MCP_GIT_PUSH_ENABLED=true`, choose a permission profile that authorizes push (normally `trusted_admin`), create an approval request such as `operation=git_push`, `target=origin/main`, and resolve it as approved. Then call `git_push(remote="origin", branch="main", approval_id="...")`. Do not enable push on an unauthenticated public server.

## Parallel-worker boundary

A workstream is an isolated Git worktree, not a spawned model. Each independent worker must run in a separate agent/client context and use the returned path. ChatGPT Web does not let this server create additional ChatGPT Web model sessions. The MCP layer provides worktree isolation, persisted metadata, test validation, and approved merge coordination; it does not claim independent LLM workers when only one ChatGPT conversation is connected.

## Benchmark fairness

Use a clean baseline commit, the same case names and requirements, the same test commands, and the same repository revision for each agent. External results should include `repository_revision`. Results from dirty starting trees or mismatched revisions are marked non-comparable; provider cost remains unknown unless the provider or operator supplies it.

## Security notes and limitations

- Push and merge are explicit, auditable operations; force push remains restricted to the unrestricted profile.
- Worktree removal refuses to delete worktrees with uncommitted changes unless Git itself is forced externally; this tool does not force-remove them.
- The dashboard is intended for the authenticated MCP deployment or local loopback. Do not expose the server publicly without strong authentication and transport restrictions.
- A passing test command is evidence, not proof that all product acceptance criteria are satisfied. The agent must still review the diff and record unmet requirements.
