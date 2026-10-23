---
name: typescript-javascript
description: TypeScript and JavaScript development, bundling, and testing workflow
version: 1.0.0
activation: ["*.ts", "*.tsx", "*.js", "package.json", "tsconfig.json"]
tags: [typescript, javascript, node, npm, jest, vitest]
requires_profile: full
---

# TypeScript / JavaScript Development Skill

## Setup
1. Install deps: `run_command("npm install")`
2. Build: `run_command("npm run build")`
3. Type check: `run_command("npx tsc --noEmit")`

## Quality Gates
1. Lint: `run_command("npx eslint . --fix")`
2. Format: `run_command("npx prettier --write .")`
3. Test: `run_tests(framework="jest")` or `run_tests(framework="vitest")`

## Patterns
- Use describe/it blocks for test organization.
- Use eforeEach/fterEach for setup/teardown.
- Mock modules with jest.mock().
- Use 	s-jest or itest for TypeScript-native testing.