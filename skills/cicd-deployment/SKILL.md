---
name: cicd-deployment
description: CI/CD pipeline configuration, deployment automation, and container workflows
version: 1.0.0
activation: [".github/workflows/", "Dockerfile", "docker-compose.yml", ".gitlab-ci.yml"]
tags: [ci, cd, docker, github-actions, deployment, kubernetes]
requires_profile: full
---

# CI/CD and Deployment Skill

## GitHub Actions Pipeline
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r requirements.txt
      - run: pytest
      - run: ruff check .
```

## Docker
1. Build: `run_command("docker build -t app:latest .")`
2. Test: `run_command("docker run --rm app:latest pytest")`
3. Push: requires `unrestricted` profile and explicit push auth.

## Deployment Checklist
- [ ] All tests pass on CI.
- [ ] No secrets committed.
- [ ] Docker image builds cleanly.
- [ ] Health check endpoint returns 200.
- [ ] Rollback plan documented.
