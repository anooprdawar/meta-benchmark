# mini-sqlite LLM Judge Rubric

Score each dimension 0-100. Most implementations score 40-70.

## Dimension 1: Separation of Concerns

Does the implementation separate CLI, query processing, and storage?

- **0:** All logic in main(). Single monolithic function.
- **25:** A dispatch function exists but parsing/execution/storage tangled.
- **50:** Parser separated, but execution and storage interleaved.
- **75:** Clear parse → plan → execute → store pipeline. Minor tangling.
- **100:** Fully separated. Each layer independently testable. Clean interfaces.

## Dimension 2: Query Engine Abstraction Quality

Is there a coherent internal model for tables, rows, and expressions?

- **0:** SQL parsed with string splitting. No data model.
- **25:** Tables as lists of dicts. No expression tree.
- **50:** Rows as typed dicts. WHERE evaluated by string comparison.
- **75:** Expression trees or AST. Typed comparisons. Row model is clean.
- **100:** Excellent. Parser produces AST. Executor is data-driven. Storage is swappable.

## Dimension 3: Naming and Pattern Consistency

- **0:** Mixed conventions, inconsistent patterns.
- **50:** Mostly consistent within files, some cross-module inconsistency.
- **100:** Consistent throughout. Similar operations share structure.

## Dimension 4: Test Quality and Coverage

- **0:** No tests or no assertions.
- **25:** Tests only check exit code.
- **50:** Happy paths with content assertions.
- **75:** Happy paths + error conditions + NULL semantics tested.
- **100:** Comprehensive. Every SQL feature tested. Persistence tested. Type edge cases.

## Dimension 5: Scope Discipline

- **0:** Built something else or < 50% of SQL features.
- **50:** Mostly on-scope, 1-2 missing or extra features.
- **100:** Exact implementation. No sqlite3 import. Missing features documented.

## Output Format

```json
{
  "dimensions": {
    "separation_of_concerns": {"score": 70, "reasoning": "..."},
    "query_engine_abstraction": {"score": 55, "reasoning": "..."},
    "naming_consistency": {"score": 75, "reasoning": "..."},
    "test_quality": {"score": 60, "reasoning": "..."},
    "scope_discipline": {"score": 85, "reasoning": "..."}
  },
  "aggregate_score": 69.0,
  "overall_notes": "..."
}
```
