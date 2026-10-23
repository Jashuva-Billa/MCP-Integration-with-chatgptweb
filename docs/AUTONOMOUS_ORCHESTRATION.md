# ChatGPT Web-Driven Coding, Recovery, and Benchmarks

## Architecture without an API key

This deployment uses ChatGPT Web as the reasoning model. ChatGPT Web calls the connected MCP server; the MCP server cannot call back into the logged-in ChatGPT Web session or create independent ChatGPT model sessions.

Use \`run_autonomous_task\` (or \`start_chatgpt_coding_task\`) to create a persistent task. ChatGPT Web then owns the plan/act/inspect/repair loop and calls the normal MCP tools for repository reads, edits, tests, Git inspection, and recovery. No LLM API key or model endpoint is required for this mode.

The API-backed implementation remains available internally for users who deliberately configure a separate OpenAI-compatible endpoint, but it is not the workflow for this ChatGPT Web setup. Do not add ChatGPT session cookies, browser tokens, or credentials to the server.

## ChatGPT Web task tools

- \`run_autonomous_task\` — start a ChatGPT Web-driven task, or pass \`task_id\` to retrieve persistent task context.
- \`start_chatgpt_coding_task\` — create a task with requirements, plan, skill recommendations, and bounded repair budget.
- \`record_chatgpt_task_progress\` — persist plan-step status, changed files, test outcomes, and repair notes.
- \`finish_chatgpt_coding_task\` — run final verification and mark the task complete only when every plan step is done and the verification command passes.
- \`rollback_task_checkpoint\` — restore a file or directory checkpoint.
- \`rollback_git_reset_checkpoint\` — return to a hard-reset safety branch and restore snapshotted tracked edits.
- \`record_chatgpt_benchmark_result\` — record completed ChatGPT Web or Claude Code benchmark outcomes without an API.
- \`get_benchmark_report\` — retrieve saved benchmark records and summaries.

## Recommended loop

1. Select the intended repository and inspect \`git_status\` before changes.
2. Call \`run_autonomous_task\` with the objective, requirements, and a concise plan.
3. Inspect the repository using search, symbol, and file-reading tools. Read the relevant skill instructions with \`get_skill\` where useful.
4. Make changes through the registered permission-aware filesystem and editing tools. They create local checkpoints before mutations.
5. Update progress with \`record_chatgpt_task_progress\` after each meaningful plan step. Include actual test command and exit code when tests are run.
6. If a test fails, record the failure and repair note; investigate and retry within the task's configured repair budget.
7. Run the required tests, inspect the final diff and Git status, and review security and regression risks.
8. Mark steps done only with evidence, then call \`finish_chatgpt_coding_task\` with a final verification command.
9. Report verified results, remaining issues, tests, and the task ID. Do not commit or push unless explicitly requested.

The server persists task state under \`runtime/tasks/\`, audit events, and filesystem checkpoints under \`runtime/checkpoints/\`. Checkpoint storage is local recovery data, not a substitute for Git history or off-machine backups.

## Parallel review boundary

ChatGPT Web remains the model and therefore this mode cannot spawn separate ChatGPT model sessions or independent model-backed agents from the MCP server. ChatGPT can perform implementation, test, security, and code-review passes in the current conversation, and the client may issue compatible tool calls concurrently. That is not equivalent to separate subagent reasoning contexts or isolated Git worktrees. The API-backed orchestrator has concurrent review calls only when a separate provider is configured.

## Benchmarks without an API key

Run the same benchmark case against ChatGPT Web and Claude Code on the same repository revision and environment. Record each result using \`record_chatgpt_benchmark_result\` with:

- \`case_name\`: shared task identifier, such as \`fix-parser-regression\`
- \`agent_name\`: \`ChatGPT Web\` or \`Claude Code\`
- \`success\`: whether the acceptance criteria were met
- \`baseline_test_passed\` and \`final_test_passed\`: actual test outcomes
- \`repair_attempts\`, \`tool_failures\`, and \`latency_seconds\`
- \`repository_revision\`: Git commit or immutable starting revision
- \`cost_usd\`: leave null if unknown; do not invent subscription cost per task

Example sequence for each agent:
1. Capture the starting commit and baseline test result.
2. Execute the same objective and acceptance criteria.
3. Record elapsed time, repair attempts, tool failures, final test result, and success.
4. Call \`record_chatgpt_benchmark_result\`.
5. After both agents' records are stored, call \`get_benchmark_report\` and compare success and regression rates, mean repair attempts, mean tool failures, latency, and known cost.

The benchmark recorder stores results; it does not automatically launch Claude Code or independently run ChatGPT Web. \`run_coding_benchmark\` is the API-backed benchmark runner and is not required for this ChatGPT Web workflow.

## Safety guarantees and limits

Filesystem operations and commands still obey the active MCP permission policy. The autonomous profile does not bypass permissions. File edits return checkpoint identifiers; hard Git resets create a safety branch and snapshot tracked local edits when permitted. A successful final status requires all plan steps to be marked done and the final verification command to pass.

The MCP server cannot guarantee the ChatGPT model will never make a mistake. Review diffs, keep backups/checkpoints, use tests, and retain human approval for consequential operations.
