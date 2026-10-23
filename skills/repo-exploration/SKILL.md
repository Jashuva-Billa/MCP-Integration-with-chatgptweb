---
name: repo-exploration
description: Systematically explore and understand an unfamiliar codebase
version: 1.0.0
activation: ["README.md", "*.md"]
tags: [exploration, discovery, architecture]
requires_profile: safe
---

# Repository Exploration Skill

## Purpose
Quickly build a complete mental model of an unfamiliar codebase before making any changes.

## Activation
Use this skill whenever you encounter a new repository or need to understand a module deeply before editing.

## Step-by-Step Workflow

### Step 1 — Entry Points
1. Read `README.md` (or `README.rst`, `CONTRIBUTING.md`) for the project's stated purpose and setup instructions.
2. Check `pyproject.toml`, `package.json`, `pom.xml`, `Cargo.toml`, or `build.gradle` for dependency declarations and build targets.
3. Identify the primary entrypoint: `main.py`, `index.ts`, `App.java`, `src/main.rs`, `cmd/main.go`.

### Step 2 — Architecture Overview
1. Run `list_files(path=".", recursive=True)` to get the full project tree.
2. Identify the top-level module structure (src/, lib/, app/, pkg/).
3. Check for existing architecture docs: `docs/`, `ADR/`, `ARCHITECTURE.md`.
4. Run `analyze_repository` to get a summary of languages, file counts, and structure.

### Step 3 — Configuration and Environment
1. Check `.env.example`, `config/`, `settings.py`, `config.yaml` for configuration surface.
2. Identify all external service dependencies (databases, APIs, message queues).
3. Check for `.gitignore`, `Dockerfile`, `docker-compose.yml`.

### Step 4 — Code Deep Dive
1. Read each top-level module's `__init__.py`, `index.ts`, or equivalent.
2. Use `list_functions` and `list_classes` on key files.
3. Use `find_symbol` to locate core abstractions.
4. Trace the request lifecycle (entry → router → service → data layer).

### Step 5 — Tests
1. Locate the test directory (`tests/`, `spec/`, `__tests__/`).
2. Run `list_files(path="tests/", recursive=True)`.
3. Read `conftest.py` or equivalent test setup.
4. Run `run_tests` with dry-run first to understand the test surface.

### Step 6 — Git History
1. Run `git_log(max_commits=20)` to understand recent activity.
2. Run `git_status` to see current changes.
3. Use `git_show` on interesting commits.

## Expected Output
- Summary of architecture (2-3 paragraphs)
- Module dependency map
- List of key abstractions and their locations
- Test coverage estimate
- List of open questions or unclear areas

## Validation
- [ ] README read and understood
- [ ] Top-level structure mapped
- [ ] Entry points identified
- [ ] Key abstractions located
- [ ] Test framework identified
