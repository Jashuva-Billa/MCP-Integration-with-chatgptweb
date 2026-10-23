---
name: python-development
description: Python project setup, development, linting, and testing workflow
version: 1.0.0
activation: ["*.py", "requirements.txt", "pyproject.toml", "setup.py", "Pipfile"]
tags: [python, testing, linting, formatting, type-checking]
requires_profile: full
---

# Python Development Skill

## Purpose
Establish and maintain a high-quality Python development workflow.

## Workflow

### Setup
1. Check Python version: `run_command("python --version")`
2. Check virtual environment: look for `venv/`, `.venv/`, `env/` directories.
3. Install deps: `install_dependencies(manager="pip", requirements_file="requirements.txt")`
4. Or with uv: `install_dependencies(manager="uv")`

### Code Quality Gates (run in order)
1. **Format**: `run_command("ruff format .")` or `run_command("black .")`
2. **Lint**: `run_command("ruff check . --fix")` or `run_command("flake8 .")`
3. **Type check**: `run_command("mypy . --ignore-missing-imports")`
4. **Test**: `run_tests(test_path="tests/", framework="pytest")`
5. **Coverage**: `run_command("pytest --cov=. --cov-report=term-missing")`

### Test-Driven Development
1. Write the test first in `tests/test_<module>.py`.
2. Run tests to confirm they fail: `run_tests("tests/test_<module>.py")`
3. Implement the feature.
4. Run tests again to confirm they pass.
5. Refactor while keeping tests green.

### Common Patterns
- Use `pytest.fixture` for shared setup.
- Use `tmp_path` for temporary file fixtures.
- Use `monkeypatch` for environment variable and external dependency mocking.
- Use `pytest.mark.parametrize` for data-driven tests.

### Debugging Failed Tests
1. Run with verbose output: `run_command("pytest -xvs tests/failing_test.py")`
2. Check stderr for import errors or fixture failures.
3. Use `get_file_structure("tests/failing_test.py")` to understand test layout.
4. Add `--tb=long` for full tracebacks.

## Validation Checklist
- [ ] All tests pass
- [ ] No ruff/flake8 errors
- [ ] mypy reports no errors (or known suppressions are documented)
- [ ] No unused imports
- [ ] Docstrings on public functions
