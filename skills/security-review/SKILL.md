---
name: security-review
description: Security code review, vulnerability scanning, and hardening checklist
version: 1.0.0
activation: ["*.py", "*.ts", "*.java", ".env.example"]
tags: [security, vulnerabilities, injection, secrets, auth, owasp]
requires_profile: full
---

# Security Review Skill

## OWASP Top 10 Checklist
- [ ] Injection: all user input is sanitized/parameterized.
- [ ] Broken Auth: tokens are strong, expiring, and revocable.
- [ ] Sensitive Data: no secrets in code, logs, or response bodies.
- [ ] XXE: XML parsers disable external entity resolution.
- [ ] Broken Access Control: every endpoint checks authorization.
- [ ] Security Misconfiguration: no debug mode in production.
- [ ] XSS: all output is escaped; CSP header is set.
- [ ] Insecure Deserialization: no `pickle.loads` on untrusted data.
- [ ] Known Vulnerabilities: deps are up to date.
- [ ] Logging: failures are logged; secrets are redacted.

## Secret Scanning
1. Search for hardcoded secrets: `search_code("password", case_sensitive=False)`
2. Search for API keys: `search_code("api_key")`
3. Check `.gitignore` covers `.env`.
4. Run `git log --all --full-history -- .env` to check for past exposure.

## Path Traversal
- Validate all file paths stay within allowed boundaries.
- Resolve symlinks before checking containment.
