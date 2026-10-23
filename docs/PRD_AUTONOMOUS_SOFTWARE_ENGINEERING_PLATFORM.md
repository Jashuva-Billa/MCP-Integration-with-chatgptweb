# Product Requirements Document (PRD)
# MCP Coding Tool — Reliable Autonomous Software Engineering Platform

- **Status:** Proposed
- **Version:** 1.0
- **Date:** 2026-10-23
- **Target repository:** MCP
- **Document type:** Product requirements and implementation plan

## 1. Executive Summary

Evolve the existing MCP Coding Tool into a reliable, secure, provider-independent software engineering control plane. It should coordinate coding agents in isolated execution environments, preserve task state across failures, independently verify changes, enforce security boundaries, and provide observable, auditable delivery workflows.

The product should integrate with existing coding engines rather than attempt to recreate every model or agent runtime. ChatGPT Web may remain a planning/client interface; configured CLI/SDK agents execute independent worker jobs. The system must clearly distinguish capabilities actually implemented and tested from capabilities merely configured or documented.

## 2. Problem Statement

The current project already documents multi-repository management, file/Git operations, skills, task lifecycle tools, approvals, parallel workstreams, CLI worker runtimes, independent verification, and benchmarking. The next step is to harden these paths into a cohesive system.

Key risks to address:
- Worker jobs can fail, hang, be duplicated, or outlive their task.
- Concurrent tasks may conflict if isolation and ownership are not enforced end to end.
- Process-local state can be lost on restart or become inconsistent with actual worker processes.
- A worker's claim that work is complete is not independent evidence.
- Permission profiles alone do not provide OS-level sandbox isolation.
- Operators need a single view of task state, worker logs, approvals, diffs, verification, and delivery.
- Benchmark results must be reproducible and report uncertainty, failures, and actual known/unknown costs.

## 3. Product Vision

A user submits a software task once. The system plans it, dispatches work to one or more appropriate coding engines in isolated workspaces, monitors execution, independently verifies outputs, routes failures into bounded repair/review cycles, requests approval for privileged actions, and delivers a reviewed branch or pull request with evidence.

### Product principles
1. **Evidence over claims:** no task is marked verified without required independent checks.
2. **Secure by default:** least privilege, isolated execution, explicit network policy, secret protection.
3. **Durable by design:** recover tasks and reconcile worker state after restarts.
4. **Provider-independent:** coding engines are adapters behind a common worker contract.
5. **Human control:** approvals, cancellation, review, and merge authority remain explicit.
6. **Observable:** every state transition and material action is attributable and auditable.
7. **Incremental migration:** preserve working tools and public interfaces where practical.
8. **Honest reporting:** unavailable evidence, unsupported runtimes, and unknown costs are never fabricated.

## 4. Goals and Non-Goals

### Goals
- Reliable task state machine and restart recovery.
- Independent, isolated worker execution with cancellation and timeouts.
- Enforced sandbox and credential/network boundaries.
- Independent test, lint, security, and diff verification.
- Review/approval/merge gates and reproducible evidence artifacts.
- Live task/worker dashboard and structured audit trail.
- Comparable benchmarks and task-aware worker selection.
- Backward-compatible MCP tools where feasible.

### Non-goals for the initial release
- Training or hosting foundation models.
- Automatically merging unreviewed or unverified code.
- Guaranteeing every task can be completed autonomously.
- Unrestricted shell execution on the host.
- Replacing IDEs, Git providers, or coding agents.
- Claiming full compliance certification without a separate audit.

## 5. Users and Core Use Cases

### Personas
- **Individual developer:** asks an agent to implement, debug, refactor, or test code.
- **Technical lead/reviewer:** assigns parallel work, reviews diffs and verification evidence, approves delivery.
- **Platform/security administrator:** manages permissions, sandbox profiles, credentials, and audit retention.
- **Engineering evaluator:** compares coding workers on a stable task suite.

### Primary workflows
1. Implement a feature from a written task.
2. Reproduce and fix a bug with regression tests.
3. Split independent subtasks across isolated workers and synthesize results.
4. Resume a task after server or worker failure.
5. Run independent verification and request repair when checks fail.
6. Review a patch and approve a branch/PR; merge only under policy.
7. Benchmark multiple configured workers on identical repository revisions.

## 6. Scope and Priority

- **P0:** required for the first hardened release.
- **P1:** important product capabilities after P0 foundations.
- **P2:** advanced optimization and enterprise scale.

## 7. Functional Requirements

### FR-1 — Durable Task State Machine (P0)

Define explicit, validated task phases:
- `queued`
- `planning`
- `ready`
- `running`
- `testing`
- `review`
- `awaiting_approval`
- `merging`
- `completed`
- `failed`
- `cancelled`
- `blocked`

Requirements:
- Every transition is validated against an explicit transition table.
- Store task state, phase, plan, attempts, worker IDs, timestamps, checkpoints, verification records, approvals, and failure reasons durably.
- Record append-only state-transition events with actor, timestamp, prior state, new state, and correlation ID.
- Support idempotency keys for task creation and side-effecting actions.
- On startup, reconcile persisted tasks with actual worker processes and worktrees.
- Recover eligible tasks safely; do not blindly restart non-idempotent operations.
- Use bounded retries, exponential backoff with jitter, and a maximum retry budget.
- Preserve backward compatibility or provide versioned adapters for existing task APIs.

Acceptance criteria:
- Unit tests cover every legal and illegal transition.
- Killing/restarting the server does not lose accepted tasks or completed verification records.
- Duplicate requests with the same idempotency key do not create duplicate jobs.
- Recovery correctly identifies orphaned, exited, running, and ambiguous workers.
- State cannot become completed before required verification and approval gates pass.

### FR-2 — Worker Runtime Contract and Lifecycle (P0)

Define a provider-neutral worker adapter interface with:
- `start(job_spec)`
- `get_status(worker_id)`
- `stream_events(worker_id)`
- `cancel(worker_id, reason)`
- `collect_result(worker_id)`
- `cleanup(worker_id)`
- health/capability discovery

Each job records worker/provider/version, task ID, repository revision, workspace/worktree, command policy, start/end time, exit status, logs/artifacts, cancellation status, and resource usage when available.

Requirements:
- Each concurrent worker receives a unique execution ID and isolated worktree/workspace.
- Explicit lifecycle states: created, starting, running, cancelling, succeeded, failed, timed_out, cancelled, cleanup_failed.
- Cancellation terminates the complete process tree or sandbox job, then confirms termination.
- Enforce wall-clock timeout, output limits, concurrency limits, and resource budgets.
- Redact secrets from logs and tool outputs.
- Ensure cleanup runs after success, failure, timeout, cancellation, and server recovery.
- Do not claim that a CLI worker is an independent model session unless the adapter actually creates one.

Acceptance criteria:
- Two concurrent workers cannot write to the same worktree unless an explicit shared-workspace mode exists.
- Cancellation tests prove child processes terminate.
- Failed startup and cleanup failures are visible and recoverable.
- Adapter contract tests can be run against a fake worker without model/API costs.

### FR-3 — Parallel Planning, Dependencies, and Result Synthesis (P0/P1)

- Represent a task plan as a dependency graph with task/subtask IDs, ownership, expected artifacts, and completion criteria.
- Dispatch only ready subtasks whose dependencies have passed.
- Avoid splitting tasks that share heavily coupled files without explicit conflict handling.
- Collect results in structured format: summary, files changed, tests run, evidence, known limitations, commit/worktree reference.
- Synthesize results only after inspecting actual diffs and verification results.
- Detect overlapping file changes and merge conflicts before integration.
- Support cancellation propagation and policy for sibling tasks when one subtask fails.

Acceptance criteria:
- Blocked subtasks are not started prematurely.
- A failed required dependency prevents final completion.
- Conflicting changes are reported instead of silently overwritten.
- Synthesis references real worker results and exact revision IDs.

### FR-4 — Independent Verification and Evidence Ledger (P0)

Verification must execute independently of the worker's own claims, in a fresh process and, where practical, a clean environment.

Required checks are policy-configurable:
- Test suite and targeted regression tests.
- Lint and formatting checks.
- Type checks/build checks where configured.
- Diff and whitespace checks.
- Secret and dependency/security scanning where tools are available.
- Optional reviewer pass by a separate worker/provider.
- Final revision/commit identity and clean/expected working-tree state.

For each check persist:
- command/tool and version
- exact repository revision and workspace
- start/end time, exit code, status
- bounded stdout/stderr or artifact references
- test counts when parsable
- environment/profile and failure classification
- verifier identity and evidence hash

Requirements:
- Distinguish pass, fail, skipped, unavailable, and inconclusive.
- A skipped or unavailable required check must not be represented as passed.
- Verification applies to the exact candidate revision delivered.
- Any code change after verification invalidates affected evidence and requires rerun.
- Task completion is gated on all required checks and approvals.

Acceptance criteria:
- A worker cannot mark its own claimed tests as independently passed.
- Tests that pass on one commit but fail on the delivered commit block completion.
- Missing tools produce explicit unavailable status.
- Evidence is retrievable by task ID and linked from the dashboard/report.

### FR-5 — Sandbox and Security Boundaries (P0)

Use layered security. Application permission profiles remain useful but are not the sandbox.

Requirements:
- Provide a runtime interface for local containers first, with a future remote VM/runner adapter.
- Run workers as non-root/non-administrator wherever feasible.
- Mount only the task workspace and explicitly required paths.
- Make the host filesystem read-only except for dedicated workspace/cache/output mounts.
- Default network egress to deny or an explicit allowlist for sandboxed workers.
- Separate worker credentials from MCP server credentials and from one another.
- Never expose host environment variables wholesale to a worker.
- Use scoped, short-lived credentials; support redaction and revocation.
- Restrict command execution through policy and allowlists; avoid shell interpolation of untrusted values.
- Validate repository paths and symlinks to prevent workspace escape.
- Treat source files, README instructions, issue text, tool output, and generated code as untrusted data, not privileged policy.
- Require approval for destructive filesystem operations, remote pushes, production operations, and policy-defined sensitive actions.
- Emit auditable policy decisions with reason codes.
- Provide a documented break-glass process that is disabled by default.

Acceptance criteria:
- Security tests attempt path traversal, symlink escape, malicious shell input, credential leakage, and forbidden network access.
- A worker cannot read unrelated repositories or secrets without explicit scoped permission.
- Public tunnel mode refuses to start without required authentication.
- Denied actions fail closed and are logged without leaking secrets.

### FR-6 — Approvals, Git Delivery, and Rollback (P0)

- Approval requests bind to a specific action, repository, branch/revision, diff hash, requester, expiration, and policy.
- Any material change to an approved diff invalidates approval.
- Separate permissions for branch creation, commit, fetch/pull, push, PR creation, merge, and destructive Git operations.
- Default to branch/PR delivery; never merge solely because a worker reports success.
- Verify remote push results and reconcile local/remote references.
- Create recoverable checkpoints before risky changes.
- Rollback must be scoped and explicit; never use hard reset or delete user work implicitly.
- Surface merge conflicts and preserve both source and target artifacts for review.

Acceptance criteria:
- Approval cannot be replayed for a different diff or expired action.
- Push failure cannot be reported as successful delivery.
- Rollback tests preserve unrelated user changes.
- Merge requires policy-required verification and approval.

### FR-7 — Observability and Control Dashboard (P1)

Provide a responsive local web dashboard with:
- Task queue and phase/state filters.
- Task timeline and state-transition history.
- Worker cards with status, duration, cancellation, retries, and bounded logs.
- Dependency graph and parallel execution status.
- Changed-file list, diff preview, branch and revision information.
- Verification checklist with evidence links and explicit skipped/unavailable states.
- Approval queue and action details.
- Retry, cancel, resume, and approve actions subject to authorization.
- Failure classification and diagnostics.
- Benchmark runs and comparative reports.
- Search by task, repository, worker, and correlation ID.

Requirements:
- UI is a view of the persisted backend state, not the source of truth.
- All mutating actions use authenticated, authorized backend endpoints.
- Enforce CSRF protections where relevant and safe browser security headers.
- Logs are paginated/streamed and bounded; never expose raw secrets.
- Dashboard remains useful when workers are offline.

Acceptance criteria:
- UI state matches persisted task state after refresh/reconnect.
- Unauthorized actions are rejected server-side.
- Worker events appear without requiring manual page refresh, using an appropriate streaming mechanism.
- No secrets are present in dashboard logs or API responses.

### FR-8 — Benchmarking and Task-Aware Routing (P1)

- Maintain a versioned benchmark dataset of real, reproducible coding tasks.
- Pin repository baseline commits, task instructions, environment images, and verification rules.
- Support repeated runs and a configurable timeout/budget per task.
- Record task success, verification result, regressions, duration, retries, token/cost values when known, and human review outcomes.
- Explicitly label missing cost/token data as unknown.
- Compare workers across the same tasks and comparable settings.
- Report sample size and failure rate; do not rank on successful tasks alone.
- Add routing based on task language, repository, task type, tool capability, historical success, latency, and known cost.
- Keep routing explainable and allow policy overrides.

Acceptance criteria:
- Re-running a benchmark records an immutable new run rather than overwriting history.
- Every result is linked to baseline and candidate revisions.
- Failed and timed-out tasks remain in the report.
- Worker recommendations explain the signals used and uncertainty.

### FR-9 — Skills, Hooks, and Tool Extensibility (P1)

- Preserve the current skills registry and task preparation workflow.
- Validate skill metadata and path containment; treat skill contents as untrusted instructions subordinate to system policy.
- Add worker capability discovery and adapter/plugin versioning.
- Hooks must have explicit event names, timeouts, output limits, permissions, and audit records.
- Prevent recursive hook execution and duplicate side effects.
- Make tool registration discoverable with schemas and capability metadata.
- Add compatibility tests for supported MCP clients/transports.

Acceptance criteria:
- Invalid or malicious skill paths are rejected.
- Hooks cannot bypass permission policy.
- Worker adapters and skills can be added without changing core task-state logic.

### FR-10 — Authentication, Tenancy, and Audit (P0 for exposed deployments; P1 for multi-user)

- Require authentication for any network-exposed deployment.
- Enforce repository/task-level authorization on every read and mutation.
- Use per-user or per-session task ownership and explicit context isolation.
- Store append-only audit events for login/auth decisions, policy decisions, task transitions, approvals, worker launches, file mutations, Git operations, and delivery.
- Add configurable retention and safe export.
- Prevent cross-user leakage through logs, task IDs, workspace paths, and caches.
- Do not assume a random tunnel URL provides authorization.

Acceptance criteria:
- Cross-session and cross-user isolation tests pass.
- Unauthenticated public access is denied.
- Audit events identify actor, action, target, result, and correlation ID without storing secrets.

### FR-11 — Reliability, Performance, and Resource Limits (P0/P1)

- Add health/readiness endpoints and dependency health reporting.
- Bound concurrency, queues, logs, payload sizes, request duration, and worker resources.
- Apply timeouts to all external processes and network operations.
- Use structured logs, metrics, and trace/correlation IDs.
- Handle server shutdown gracefully and reconcile unfinished tasks on startup.
- Avoid blocking the API event loop with long-running operations.
- Measure API latency, queue wait, worker startup, verification duration, and end-to-end completion time.

Acceptance criteria:
- Load tests establish supported concurrent tasks and resource limits.
- Hung workers do not block unrelated tasks.
- Graceful shutdown leaves recoverable state.
- Health endpoints distinguish liveness from readiness.

## 8. Non-Functional Requirements

### Security
- Least privilege and deny-by-default for sensitive operations.
- No secrets in source control, test fixtures, logs, benchmark artifacts, or responses.
- Threat model and abuse cases documented.
- Dependency and image scanning in CI where feasible.

### Reliability
- No silent task loss after acknowledgement.
- Idempotent recovery for supported operations.
- Every terminal task has a clear outcome and reason.
- All critical paths have automated tests.

### Maintainability
- Typed schemas and validated state transitions.
- Clear module boundaries: API, orchestration, persistence, worker adapters, sandbox, verification, policy, dashboard.
- Database migrations and versioned API contracts.
- Avoid duplicating orchestration logic across MCP tools.

### Portability
- Support current documented Windows local workflow.
- Keep worker/sandbox implementations behind adapters to enable Linux/container/remote execution.
- Document platform-specific security limitations.

### Accessibility and usability
- Clear status text and keyboard-accessible controls.
- Distinguish warning, failure, blocked, and success states.
- Require confirmation for irreversible operations.

## 9. Proposed Architecture

1. **MCP/API layer:** schemas, authentication, authorization, request validation, rate limits.
2. **Orchestrator:** durable state machine, dependency graph, scheduler, retries, reconciliation.
3. **Persistence:** relational database for tasks, workers, transitions, approvals, verification, benchmark metadata; artifact storage for larger logs and diffs.
4. **Worker adapters:** Codex CLI, Claude Code CLI, Cline SDK/CLI, OpenHands, and future providers, only where supported and configured.
5. **Execution sandbox:** container/VM/remote runner with explicit mounts, network policy, credentials, and resource limits.
6. **Verification service:** independent fresh-process checks and immutable evidence records.
7. **Policy/approval service:** centralized authorization and action-specific approval tokens.
8. **Delivery service:** branch, push, PR, and merge operations with verification and approval gates.
9. **Dashboard:** task state, events, worker logs, diffs, approvals, verification, and benchmarks.
10. **Telemetry:** structured logs, metrics, trace IDs, audit events.

Use existing modules where sound. Avoid a broad rewrite until implementation and tests establish a concrete need.

## 10. Data Model (Minimum)

- `Task`: id, idempotency_key, repository_id, requested_by, title, description, phase, status, plan_version, baseline_revision, candidate_revision, created_at, updated_at, deadline, failure_code.
- `TaskStep`: id, task_id, dependency_ids, description, status, owner_worker_id, retry_count, acceptance_criteria.
- `WorkerJob`: id, task_id, step_id, provider, runtime_version, workspace_id, process_handle, status, started_at, ended_at, exit_code, resource_summary.
- `Workspace`: id, repository_id, path_or_runtime_ref, baseline_revision, candidate_revision, ownership, lifecycle_state.
- `StateEvent`: id, task_id, actor, event_type, from_state, to_state, timestamp, correlation_id, metadata_redacted.
- `VerificationRun`: id, task_id, revision, verifier, check_name, status, exit_code, started_at, ended_at, artifact_ref, evidence_hash.
- `Approval`: id, action, target_ref, diff_hash, requested_by, decided_by, status, expires_at, decision_reason.
- `Artifact`: id, task_id, worker_id, type, storage_ref, content_hash, size_bytes, redaction_status.
- `BenchmarkRun`: id, suite_version, worker_config, baseline_revision, start/end times, result_summary.
- `BenchmarkCaseResult`: run_id, case_id, worker_id, status, duration, retries, known_cost, verification_summary.

Use migrations, indexes for task/status/time lookups, foreign keys, and retention policies. Avoid persisting secrets or unnecessary raw prompts in audit records.

## 11. Delivery Phases

### Phase 0 — Audit and baseline
- Inspect all current task, worker, verification, approval, permission, Git, and dashboard paths.
- Map README claims to code, tests, and runtime behavior.
- Record existing APIs and compatibility requirements.
- Run the current test suite; classify failures before changing code.
- Produce threat model, architecture diagram, and gap report.
- Capture baseline worker benchmark where runnable.

**Exit gate:** baseline results and prioritized gaps are reviewed; existing uncommitted changes are preserved.

### Phase 1 — P0 foundations
- Implement/finish durable task transitions and recovery.
- Standardize worker adapter lifecycle and isolated worktree ownership.
- Harden cancellation, timeouts, output limits, and cleanup.
- Make independent verification evidence-based and revision-bound.
- Enforce authentication, approval binding, and policy gates.
- Add security and failure-injection tests.

**Exit gate:** restart, cancellation, isolation, verification, and approval acceptance criteria pass.

### Phase 2 — Delivery and operations
- Complete safe branch/PR delivery and rollback behavior.
- Add structured audit events, health checks, and operational metrics.
- Harden exposed deployment configuration and documentation.

**Exit gate:** end-to-end task can go from request to verified branch/PR with clear evidence and no unapproved privileged actions.

### Phase 3 — Dashboard and benchmarking
- Build/complete dashboard using persisted state.
- Add benchmark suite versioning, repeated runs, and cost-unknown semantics.
- Add task-aware worker routing behind an opt-in feature flag.

**Exit gate:** dashboard actions are authorized; benchmark reports are reproducible and include failures.

### Phase 4 — Scale and enterprise hardening
- Add remote sandbox/runner adapters, multi-user isolation, quotas, retention, and enterprise integrations as needed.
- Run load, recovery, and security tests in a deployment-like environment.
- Conduct an external security review before broad production exposure.

**Exit gate:** operational SLOs, security findings, and deployment runbooks are reviewed and accepted.

## 12. Testing Strategy

- **Unit:** state machine, policies, redaction, idempotency, retries, transition validation, approval binding.
- **Contract:** every worker adapter against a shared fake-worker contract suite.
- **Integration:** persistence, Git/worktrees, sandbox, verification, approvals, API and dashboard.
- **End-to-end:** bug fix and feature task from request through verification and delivery.
- **Failure injection:** kill worker, kill server, corrupt/lose process handle, timeout command, fill disk/output quota, fail database/network, fail cleanup.
- **Security:** path traversal, symlink escape, prompt injection, shell injection, secret exfiltration, unauthorized tool calls, cross-session access, forbidden network egress.
- **Performance:** concurrent tasks, queue fairness, API responsiveness, log streaming, startup and recovery.
- **Regression:** preserve existing MCP tool contracts and documented local setup.

Every test must be deterministic where feasible, avoid live paid model calls by default, and clearly label integration tests requiring external services.

## 13. Product Metrics and Initial Targets

These are proposed release targets to validate against the baseline, not current performance claims:
- 100% of accepted tasks have durable IDs and state.
- 100% of completed tasks satisfy configured mandatory verification gates.
- 100% of sensitive actions are authorized and audited.
- 0 cross-worktree writes in concurrency tests.
- 0 known secrets in redaction test outputs.
- 100% of supported cancellation tests confirm process/sandbox termination.
- 100% of duplicate idempotency test requests avoid duplicate jobs.
- At least 95% successful recovery in deterministic restart/failure-injection scenarios; all unrecovered cases must be surfaced as blocked/failed, never falsely completed.
- Benchmark reporting includes all attempted cases and reports sample size.
- Establish P50/P95 end-to-end latency and supported concurrency from measured baseline before setting numeric SLOs.

## 14. Risks and Mitigations

- **Overengineering before validating the current code:** begin with a code/test audit and reuse working components.
- **Host-level destructive access:** use sandboxing and least privilege; retain explicit approvals.
- **Agent output is untrusted:** validate tool calls, paths, generated scripts, and results; keep policy enforcement outside the model.
- **Provider behavior changes:** version adapters and contract-test them.
- **Benchmark unfairness:** pin task revisions/environments, repeat runs, report failed cases and uncertainty.
- **Persistence migration breaks existing workflows:** back up state, migrate incrementally, test rollback, and preserve API compatibility.
- **Dashboard expands attack surface:** authenticate, authorize every mutation, apply browser security protections, and avoid exposing secrets.
- **False sense of security from permission profiles:** clearly document the difference between application-level permissions and OS-level isolation.

## 15. Open Decisions

Resolve during Phase 0, based on existing code and deployment needs:
1. Persistence engine: SQLite for single-user/local-first operation versus PostgreSQL for multi-user/remote deployments.
2. Initial sandbox: Docker/Podman availability on supported hosts and fallback behavior.
3. Supported worker adapters and their licensed/installed requirements.
4. Whether dashboard and API share the same process or are separately deployed.
5. Audit and artifact retention defaults.
6. Initial Git provider and PR automation scope.
7. Whether remote execution is in initial release or a later phase.
8. Which checks are mandatory per repository type.
9. Expected maximum concurrent workers and task duration.
10. Whether multi-user tenancy is required now or only after single-user hardening.

## 16. Definition of Done

A release is done only when:
- Requirements are mapped to implementation and automated tests.
- Existing APIs and local workflows are preserved or migration is documented.
- Task state survives restarts and cannot bypass required gates.
- Workers are isolated and can be reliably cancelled and cleaned up.
- Verification evidence refers to the exact delivered revision.
- Privileged operations require the right authorization and approval.
- Dashboard reflects persisted backend state and does not leak secrets.
- Benchmark reports include failed runs and unknown costs honestly.
- Security, recovery, operational, and developer documentation is updated.
- No uncommitted user changes were overwritten or discarded during implementation.

## 17. Implementation Instruction

Implement this PRD incrementally in the existing MCP repository. First inspect the current architecture, README, tests, task-state/orchestrator/worker-runtime/verification/approval/permissions/Git/dashboard modules, and current Git status. Preserve all pre-existing user changes. Create an implementation plan with requirement-to-file mapping and baseline test results before editing.

Do not perform a blind rewrite. Implement one phase at a time, write tests with each change, run independent verification, inspect diffs, and report: files changed, tests executed and results, security limitations, unresolved gaps, and the next phase. Never claim a requirement is complete without implementation evidence.
