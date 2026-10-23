---
name: database-engineering
description: Database schema design, migrations, query optimization, and safety practices
version: 1.0.0
activation: ["*.sql", "alembic.ini", "migrations/", "schema.prisma"]
tags: [database, sql, migrations, postgresql, alembic, prisma]
requires_profile: full
---

# Database Engineering Skill

## Migration Workflow (Alembic)
1. Create migration: `run_command("alembic revision --autogenerate -m 'description'")`
2. Review generated migration file before applying.
3. Apply: `run_command("alembic upgrade head")`
4. Test rollback: `run_command("alembic downgrade -1")`

## Safety Rules
- Never `DROP` a column without a deprecation period.
- Always use transactions for multi-step migrations.
- Test migrations on a copy of production data.
- Add indexes for every foreign key and frequently-queried column.

## Query Optimization
1. Use `EXPLAIN ANALYZE` to inspect query plans.
2. Avoid SELECT * in production code.
3. Use connection pooling (PgBouncer, SQLAlchemy pool).
