# Automatic Agent Operating Protocol

This MCP server has a skill library and reusable coding superpowers. The connected reasoning client should apply them proactively; users should not need to name skills or tools.

## Default execution profile

The persistent execution profile defaults to:

- **Autonomy:** `maximum` for routine development tasks.
- **Skill selection:** automatic.
- **Self-healing:** enabled, with a bounded repair loop (5 attempts by default).
- **Parallel agents:** enabled as workstream planning; actual independent model-agent spawning requires client/runtime support and is not implemented by this MCP server itself.
- **Git delivery:** `requested`; do not commit or push unless the user requests it or explicit project policy authorizes it.
- **Destructive policy:** `checkpoint`; inspect targets and back up affected files before broad or destructive edits.

This execution profile is separate from `MCP_PERMISSION_PROFILE`. It changes workflow behavior, not the permission engine. The active permission profile, workspace confinement, secret protection, and external-provider authorization remain authoritative.

Use `get_execution_profile` to inspect settings and `configure_execution_profile` to update selected fields. Updates are persisted to `runtime/execution_profile.json`. The optional `MCP_AUTONOMY_PROFILE` environment variable overrides the autonomy label at startup.

## Required behavior for every task

1. Call `prepare_task_workflow(task, file_paths)` at the beginning of a coding task. Provide likely file paths when known.
2. Read every selected skill with `get_skill(name)`. Follow its steps; combine compatible skills rather than choosing only one.
3. Use the selected superpowers through their registered MCP tools. Discover exact tool names from the live tool catalog if needed.
4. Inspect repository state and relevant source/tests before editing. Preserve unrelated work and existing user changes.
5. For changes, preview or back up risky edits, implement a coherent patch, and run the most relevant tests. For failures, diagnose root cause and attempt bounded repairs if enabled.
6. For independent analysis, testing, and documentation tasks, identify workstreams that can safely run in parallel. Do not claim parallel agents ran unless the client/runtime actually launched them.
7. Before finishing, inspect the final diff and Git status. Report changed files, commands/tests and actual outcomes, plus remaining risks.

## Selection principles

- Skills are selected using task intent and known file-path activation patterns.
- Multiple skills may apply (for example, debugging + security review + testing).
- Superpowers are capabilities, not separate personalities: repository intelligence, safe editing, command execution, test/diagnostic loops, task memory, Git workflow, lifecycle hooks, and security controls.
- The router recommends capabilities; the reasoning client is responsible for actually invoking the returned tools and reading the selected skill instructions.
- Never claim a skill or superpower was used unless its instructions/tool were actually invoked.

## Permission and action boundaries

Use available permissions without asking the user to repeat authorization. Never bypass policy checks, workspace boundaries, secret protection, or audit logging. Under the checkpoint policy, back up affected files and inspect the target before destructive changes. Force pushes, external releases, and irreversible production changes require explicit task intent and appropriate safeguards. A permission profile does not replace authorization required by GitHub, cloud providers, or other external systems.

## Task completion standard

A task is complete only after relevant verification has run or the report explicitly states why it could not run. Summarize the implementation, tests, Git state, and any unverified behavior.
