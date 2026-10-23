---
name: production-readiness
description: Production readiness review: observability, reliability, security, and scalability
version: 1.0.0
activation: ["*.py", "Dockerfile", "*.yaml", "*.yml"]
tags: [production, reliability, observability, logging, health-checks, sre]
requires_profile: full
---

# Production Readiness Review Skill

## Checklist

### Reliability
- [ ] Health check endpoint (`/health`, `/readiness`, `/liveness`).
- [ ] Graceful shutdown handles in-flight requests.
- [ ] Retry logic with exponential backoff for external calls.
- [ ] Circuit breaker for downstream dependencies.
- [ ] Resource limits set (memory, CPU, open files).

### Observability
- [ ] Structured logging (JSON, includes request ID).
- [ ] Metrics exported (latency, error rate, throughput).
- [ ] Distributed tracing configured.
- [ ] Alerts for error rate spikes and latency P99.

### Security
- [ ] No secrets in environment output or logs.
- [ ] TLS enforced for all network communication.
- [ ] Authentication required on all non-public endpoints.
- [ ] Rate limiting configured.

### Scalability
- [ ] Database connection pool sized appropriately.
- [ ] Stateless application (state in DB/cache, not in-process).
- [ ] Horizontal scaling tested.
