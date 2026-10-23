---
name: debugging-root-cause
description: Systematic debugging, error analysis, and root cause identification
version: 1.0.0
activation: ["*.py", "*.ts", "*.java"]
tags: [debugging, root-cause, tracing, logging, errors]
requires_profile: full
---

# Debugging and Root Cause Analysis Skill

## Process
1. **Reproduce**: Get a minimal reproduction case.
2. **Observe**: Read the full error message and traceback. Don't skim.
3. **Hypothesize**: Form 2-3 plausible explanations.
4. **Test**: Eliminate hypotheses with targeted experiments.
5. **Fix**: Address the root cause, not the symptom.
6. **Verify**: Confirm the fix resolves the issue without regression.
7. **Document**: Add a test that would have caught this bug.

## Tools
- Run failing test with full output: `run_tests("tests/failing.py")`
- Search for error string: `search_code("ErrorMessage")`
- Find symbol definition: `find_symbol("ClassName")`
- Inspect recent changes: `git_diff()`, `git_log()`

## Anti-Patterns to Avoid
- Don't add `try/except Exception: pass` — it hides errors.
- Don't comment out failing code to make tests green.
- Don't blame the framework before ruling out your own code.
