---
name: dependency-management
description: Dependency auditing, updating, and conflict resolution workflow
version: 1.0.0
activation: ["requirements.txt", "package.json", "pyproject.toml", "Cargo.toml", "pom.xml"]
tags: [dependencies, security, updates, vulnerabilities, pip, npm]
requires_profile: full
---

# Dependency Management Skill

## Audit
1. Python: `run_command("pip-audit")` or `run_command("safety check")`
2. Node.js: `run_command("npm audit")`
3. Rust: `run_command("cargo audit")`

## Update Workflow
1. Check outdated: `run_command("pip list --outdated")`
2. Update one dependency at a time.
3. Run tests after each update.
4. Lock: `run_command("pip freeze > requirements.txt")`

## Principles
- Pin exact versions in production requirements.
- Use ranges in library requirements.
- Keep dev and production dependencies separate.
- Never auto-update all deps at once without testing.
