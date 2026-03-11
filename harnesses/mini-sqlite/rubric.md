# mini-sqlite Scoring Rubric

**Harness version:** 1.0.0

## Dimension Weights

| Dimension | Weight |
|-----------|--------|
| Functional completeness | 0.30 |
| Adversarial survival | 0.15 |
| Extension readiness | 0.10 |
| Mutation kill rate | 0.10 |
| Performance | 0.15 |
| Reliability | 0.10 |
| Code quality | 0.10 |

**N/A redistribution:** If mutation has no tests, its weight redistributes proportionally to functional + adversarial + extension.

## D1: Functional Completeness (0.30)

| Tier | Weight within D1 |
|------|----------------|
| Tier 1 — Core SQL | 0.40 |
| Tier 2 — Queries | 0.35 |
| Tier 3 — Advanced | 0.25 |

```
D1 = 0.40 * tier1_score + 0.35 * tier2_score + 0.25 * tier3_score
```

## D2: Adversarial Survival (0.15)

~150 public edge cases: SQL injection (stored as data, not executed), NULL edge cases, type coercion, empty tables, unicode, reserved keywords as values, boundary integers/floats, WHERE edge cases, JOIN with NULLs.

```
D2 = (passed / total) * 100
```

## D3: Extension Readiness (0.10)

Second prompt: agent given 15 min to add CREATE INDEX + EXPLAIN. 16 tests.

```
D3 = (passed / 16) * 100
```

## D4: Mutation Kill Rate (0.10)

```
D4 = (killed / total_mutants) * 100
```
N/A if agent has < 5 test functions.

## D5: Performance (0.15)

| Benchmark | Target p95 | Fail p95 | Weight |
|-----------|-----------|---------|--------|
| select_1k_rows | 2.0s | 10.0s | 0.40 |
| insert_100_rows | 5.0s | 30.0s | 0.35 |
| join_1k_rows | 3.0s | 15.0s | 0.25 |

## D6: Reliability (0.10)

7 scenarios:
1. Data survives process restart (SELECT after INSERT + restart)
2. Concurrent identical queries (no crash)
3. Corrupt database file → non-zero exit, no traceback
4. Missing database file → creates new empty DB, no crash
5. Transaction ROLLBACK reverts changes
6. Large text value (100k chars) stored and retrieved
7. NULL values preserved across restarts

```
D6 = (passed / 7) * 100
```

## D7: Code Quality (0.10)

LLM judge — see `judge/rubric.md`.
