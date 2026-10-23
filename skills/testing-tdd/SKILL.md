---
name: testing-tdd
description: Test-driven development, test structure, fixtures, and coverage
version: 1.0.0
activation: ["tests/", "test_*.py", "*.test.ts", "*.spec.ts"]
tags: [testing, tdd, pytest, jest, fixtures, coverage, mocking]
requires_profile: full
---

# Testing and TDD Skill

## TDD Cycle
1. RED: Write a failing test that describes the desired behavior.
2. GREEN: Write the minimum code to make the test pass.
3. REFACTOR: Clean up the implementation without breaking tests.

## Test Structure (pytest)
```python
def test_<feature>_<scenario>_<expected>():
    # Arrange
    ...
    # Act
    result = function_under_test(input)
    # Assert
    assert result == expected
```

## Fixtures
- Use `@pytest.fixture(scope="session")` for expensive setup (DB, server).
- Use `tmp_path` for file system tests.
- Use `monkeypatch.setenv` for environment variables.

## Coverage
- Run: `pytest --cov=app --cov-report=html`
- Target: ≥80% line coverage; 100% on critical paths.
- Never add `# noqa` just to pass coverage; fix the gap instead.
