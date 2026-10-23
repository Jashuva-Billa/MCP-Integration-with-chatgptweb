---
name: refactoring-cleanup
description: Safe refactoring, dead code removal, and code quality improvement
version: 1.0.0
activation: ["*.py", "*.ts", "*.java", "*.go"]
tags: [refactoring, cleanup, quality, dead-code, duplication]
requires_profile: full
---

# Refactoring and Code Cleanup Skill

## Safety Rules
1. Never refactor without a passing test suite as a safety net.
2. Make small, committed, verifiable steps.
3. Run tests after each step.
4. Don't change behavior while refactoring — separate concerns.

## Process
1. Run `run_tests` to establish green baseline.
2. Identify issue: duplication, long function, unclear naming, missing abstraction.
3. Make one change at a time.
4. Run tests.
5. Commit if green.

## Common Techniques
- **Extract function**: move a block of code into a named function.
- **Rename**: use `find_references` to find all usages before renaming.
- **Reduce duplication**: extract shared logic to a module.
- **Flatten nesting**: use early returns to reduce indentation levels.
- **Remove dead code**: use `search_code` to verify nothing calls it.
