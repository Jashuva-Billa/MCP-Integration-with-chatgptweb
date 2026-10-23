---
name: frontend-development
description: Frontend HTML/CSS/JS and React/Vue/Svelte development workflow
version: 1.0.0
activation: ["*.html", "*.css", "*.jsx", "*.tsx", "*.vue", "*.svelte"]
tags: [frontend, react, vue, css, html, accessibility]
requires_profile: full
---

# Frontend Development Skill

## Setup
1. Install deps: `install_dependencies(manager="npm")`
2. Start dev server: `run_command("npm run dev")`

## Quality Gates
1. Lint: `run_command("npx eslint src/ --fix")`
2. Format: `run_command("npx prettier --write src/")`
3. Test: `run_tests(framework="vitest")`
4. Build: `run_command("npm run build")`

## Accessibility
- Check for `alt` attributes on images.
- Ensure keyboard navigation works.
- Run `npx axe-cli` on rendered pages if available.
