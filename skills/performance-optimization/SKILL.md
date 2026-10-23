---
name: performance-optimization
description: Performance profiling, benchmarking, and optimization workflow
version: 1.0.0
activation: ["*.py", "*.ts", "*.java", "*.go"]
tags: [performance, profiling, benchmarking, caching, optimization]
requires_profile: full
---

# Performance Optimization Skill

## Process
1. **Measure first**: never optimize without a benchmark.
2. **Profile**: find the actual bottleneck, not the assumed one.
3. **Optimize the bottleneck**: focus on the 20% that causes 80% of the cost.
4. **Measure again**: confirm the improvement.
5. **Don't break correctness**: run the full test suite after each change.

## Python Profiling
1. `run_command("python -m cProfile -o prof.out script.py")`
2. `run_command("python -m pstats prof.out")` to inspect.
3. Or use `py-spy`: `run_command("py-spy top -- python script.py")`

## Common Wins
- Replace N+1 queries with eager loading or batch queries.
- Add database indexes.
- Cache expensive computations with `functools.lru_cache`.
- Use async I/O for network-bound work.
- Profile before and after — document the delta.
