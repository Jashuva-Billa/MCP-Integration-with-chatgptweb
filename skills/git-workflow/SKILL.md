---
name: git-workflow
description: Git branching strategy, commit hygiene, and code review workflow
version: 1.0.0
activation: ["*.md", ".github/"]
tags: [git, workflow, branching, commits, pr, code-review]
requires_profile: full
---

# Git Workflow and Code Review Skill

## Branching
- Use `feature/<ticket>-description` for features.
- Use `fix/<ticket>-description` for bug fixes.
- Keep branches short-lived (< 3 days).
- Create branch: `git_create_branch("feature/add-caching")`

## Commit Message Format
```
<type>(<scope>): <subject>

<body>

<footer>
```
Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`.

## Before Opening a PR
1. `git_status()` — no unintended files.
2. `git_diff()` — review all changes.
3. Run tests: `run_tests()`.
4. Lint: `run_command("ruff check .")`.
5. `git_stage(all_changes=True)`.
6. `git_commit("feat(module): add feature X")`.
