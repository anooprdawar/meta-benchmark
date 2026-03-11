# mini-sqlite Harness Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a complete mini-sqlite harness to meta-benchmark — all harness docs and a full test suite.

**Architecture:** Same pattern as mini-git and mini-redis. CLI is a thin shell over a required internal library. DB file is first positional argument. Scorer is already generalized (done in mini-redis plan — run that first).

**Prerequisites:** The mini-redis plan (scorer generalization) must be completed before executing this plan.

**Tech Stack:** Python 3.10+, pytest, custom on-disk storage (agent's choice), subprocess-based tests

---

## Chunk 1: Harness Docs

### Task 1: Create harnesses/mini-sqlite/prompt.md

**Files:**
- Create: `harnesses/mini-sqlite/prompt.md`

- [ ] **Step 1: Create the file**

```markdown
# mini-sqlite

Build me a SQL database engine in a single Python file called `mini_sqlite.py`.

## What I need

A command-line tool that accepts SQL statements and executes them against an on-disk database file.

```
python mini_sqlite.py mydb.db "CREATE TABLE users (id INTEGER, name TEXT)"
python mini_sqlite.py mydb.db "INSERT INTO users VALUES (1, 'Alice')"
python mini_sqlite.py mydb.db "SELECT * FROM users"
```

The first argument is the database file path. The second argument is the SQL statement.

## Supported SQL

### Core (implement first)

- `CREATE TABLE name (col type, col type, ...)` — supported types: INTEGER, REAL, TEXT, NULL
- `DROP TABLE name` — error if table doesn't exist
- `INSERT INTO name VALUES (v, ...)` — one row at a time
- `INSERT INTO name (col, ...) VALUES (v, ...)` — named columns; unlisted columns default to NULL
- `SELECT * FROM name` — all rows and columns
- `SELECT col, col FROM name` — specific columns
- `DELETE FROM name` — delete all rows

### Queries

- `WHERE col op val` — operators: =, !=, <, >, <=, >=, IS NULL, IS NOT NULL; combine with AND, OR, NOT
- `UPDATE name SET col=val [, col=val ...] [WHERE ...]`
- `DELETE FROM name WHERE ...`
- `ORDER BY col [ASC|DESC]` — stable sort
- `LIMIT N [OFFSET N]`

### Advanced

- `INNER JOIN name ON condition` and `LEFT JOIN name ON condition`
- `GROUP BY col [HAVING condition]` with aggregates: COUNT(*), COUNT(col), SUM(col), AVG(col), MIN(col), MAX(col)
- Transactions: `BEGIN`, `COMMIT`, `ROLLBACK`

## Architecture requirement

The implementation must separate CLI, query processing, and storage concerns. High-quality designs typically factor parsing, execution, and storage into distinct components. `import sqlite3` is explicitly forbidden.

## Output format

**SELECT output:**
```
id|name|age
1|Alice|30
2|Bob|
```
- Header always printed, even for zero rows
- Columns in schema-definition order
- NULL → empty field (between pipes)
- `|` in value → `\|`, newline → `\n`, `\` → `\\`
- Empty result: header only

**Mutation output:**
- `CREATE TABLE` / `DROP TABLE` / `BEGIN` / `COMMIT` / `ROLLBACK` → `OK`
- `INSERT` → `1 row affected`
- `UPDATE` / `DELETE` → `N rows affected`

All output ends with a newline.

## Exit codes and errors

- Exit 0: success
- Exit 1: SQL error (syntax, unknown table/column, type error, unsupported feature)
- Exit 2: I/O error

On error: print message to stderr, nothing to stdout.

Error message format:
- Unknown table: `Error: no such table: <name>`
- Unknown column: `Error: no such column: <name>`
- Syntax error: `Error: syntax error near '<token>'`
- Unsupported: `Error: unsupported feature '<feature>'`

## NULL semantics

- NULL != NULL; NULL IS NULL is true
- NULL sorts last in both ASC and DESC ORDER BY
- COUNT(col) ignores NULLs; COUNT(*) counts all rows; SUM/AVG/MIN/MAX ignore NULLs
- INSERT with `NULL` keyword: `INSERT INTO t VALUES (NULL, 'Alice')`

## Ordering

- SELECT without ORDER BY: insertion order
- Ties in ORDER BY: stable (insertion order)
- SELECT * with JOIN: left-table columns first, then right-table columns

## Tests

Write a pytest test suite covering every SQL feature, NULL semantics, transactions, error cases, and persistence across process restarts.
```

---

### Task 2: Create harnesses/mini-sqlite/spec.md

**Files:**
- Create: `harnesses/mini-sqlite/spec.md`

- [ ] **Step 1: Create the file**

```markdown
# mini-sqlite: Product Requirements Document

**Version:** 1.0.0
**Harness:** mini-sqlite

---

## 1. Overview

Agents implement a SQL database engine as a single Python CLI. The CLI is a thin shell over an internal query engine. Data is stored on disk in agent's choice of format. `import sqlite3` is explicitly forbidden.

---

## 2. Scope

**In scope:** CREATE/DROP TABLE, INSERT (single-row), SELECT (columns, *), DELETE, UPDATE, WHERE, ORDER BY, LIMIT/OFFSET, INNER/LEFT JOIN, GROUP BY/HAVING, aggregates, transactions (BEGIN/COMMIT/ROLLBACK), persistence.

**Out of scope:** Subqueries, window functions, foreign keys, triggers, views, ALTER TABLE, UNIQUE, CHECK, DEFAULT, AUTO_INCREMENT, ROWID, PRIMARY KEY, multi-row INSERT.

---

## 3. Interface Contract

### CLI invocation

```
python mini_sqlite.py <db_file> "<SQL statement>"
```

`MINI_SQLITE_CMD` env var is split with `shlex.split()` to form argv. DB file is `sys.argv[1]`, SQL is `sys.argv[2]`.

### Persistence

Data written by one process invocation must be readable by subsequent invocations against the same file. Tests verify persistence (SELECT after process restart). Agent chooses storage format.

---

## 4. Output Format

### Global rules

- All stdout ends with exactly one `\n`
- Tests strip trailing whitespace before comparison
- On error (exit ≠ 0): stderr contains error message; stdout is empty

### SELECT output

- Header: `col1|col2|col3`
- Header is always printed, even for zero rows
- Columns in schema-definition order (regardless of INSERT column order)
- Data rows: `val1|val2|val3`
- NULL → empty field: `val1||val3`
- Escape sequences in values:
  - `\` → `\\` (applied first)
  - `|` → `\|`
  - newline → `\n` (two chars)
- Whitespace: preserved as-is
- Empty result: header line only, no data rows

### Mutation output

| Statement | stdout |
|-----------|--------|
| CREATE TABLE | `OK` |
| DROP TABLE | `OK` |
| INSERT | `1 row affected` |
| UPDATE | `N rows affected` (N = rows matched by WHERE, 0 if none) |
| DELETE (all) | `N rows affected` |
| DELETE WHERE | `N rows affected` |
| BEGIN | `OK` |
| COMMIT | `OK` |
| ROLLBACK | `OK` |
| CREATE INDEX (extension) | `OK` |

---

## 5. Supported Types

| Type | Semantics |
|------|-----------|
| INTEGER | 64-bit signed integer |
| REAL | 64-bit float |
| TEXT | UTF-8 string |
| NULL | First-class. NULL != NULL. NULL IS NULL is true. |
| BLOB | Out of scope |
| PRIMARY KEY | Out of scope → exit 1: `Error: unsupported feature 'PRIMARY KEY'` |

---

## 6. NULL Semantics

- NULL sorts last in ORDER BY ASC and DESC (intentional deviation from standard SQL)
- COUNT(col) ignores NULLs; COUNT(*) counts all rows; SUM/AVG/MIN/MAX ignore NULLs
- Partial-column INSERT: unlisted columns default to NULL
- WHERE NULL comparisons: `col = NULL` → always false; use `col IS NULL`

---

## 7. SQL Grammar by Tier

### Tier 1 — Core SQL (40% of functional score)

- `CREATE TABLE name (col type, col type, ...)`
- `DROP TABLE name` — exit 1 if table doesn't exist: `Error: no such table: <name>`
- `INSERT INTO name VALUES (v, ...)` — one row; emits `1 row affected`
- `INSERT INTO name (col, ...) VALUES (v, ...)` — unlisted columns default to NULL
- `SELECT * FROM name`
- `SELECT col, col FROM name`
- `DELETE FROM name` — all rows; emits `N rows affected`

### Tier 2 — Queries (35% of functional score)

- `WHERE col op val` — op: =, !=, <, >, <=, >=, IS NULL, IS NOT NULL; combined with AND, OR, NOT
- `UPDATE name SET col=val [, col=val ...] [WHERE ...]`
- `DELETE FROM name WHERE ...`
- `ORDER BY col [ASC|DESC]` — stable sort for ties
- `LIMIT N [OFFSET N]`

### Tier 3 — Advanced (25% of functional score)

- `INNER JOIN name ON condition`
- `LEFT JOIN name ON condition`
- `GROUP BY col [HAVING condition]`
- Aggregates: COUNT(*), COUNT(col), SUM(col), AVG(col), MIN(col), MAX(col)
- `BEGIN` / `COMMIT` / `ROLLBACK`

---

## 8. Ordering Semantics

- SELECT without ORDER BY → insertion order
- Ties in ORDER BY → stable (insertion order)
- NULL → sorts last in both ASC and DESC
- SELECT * with JOIN: left-table columns first (schema order), then right-table columns (schema order)
- Ambiguous column names in JOIN: disambiguate as `table.column` in header

---

## 9. Transaction Semantics

- ROLLBACK undoes all writes (INSERT, UPDATE, DELETE, CREATE TABLE, DROP TABLE) since last BEGIN
- BEGIN when transaction active: exit 1, `Error: transaction already active`
- COMMIT or ROLLBACK with no active transaction: exit 1, `Error: no active transaction`
- Nested transactions: out of scope

---

## 10. Error Message Templates

| Condition | stderr |
|-----------|--------|
| Unknown table | `Error: no such table: <name>` |
| Unknown column | `Error: no such column: <name>` |
| Syntax error | `Error: syntax error near '<token>'` |
| Type mismatch | `Error: type mismatch` |
| Unsupported feature | `Error: unsupported feature '<feature>'` |
| I/O error | `Error: cannot open database '<path>'` |
| Transaction active | `Error: transaction already active` |
| No active transaction | `Error: no active transaction` |

---

## 11. Performance Targets

| Benchmark | Target p95 | Fail p95 |
|-----------|-----------|---------|
| SELECT 1k rows | 2.0s | 10.0s |
| INSERT 100 rows | 5.0s | 30.0s |
| SELECT with JOIN (1k rows each) | 3.0s | 15.0s |

---

## 12. Architecture Requirement

The implementation must separate CLI, query processing, and storage concerns. `import sqlite3` is explicitly forbidden.
```

---

### Task 3: Create rubric.md and judge/rubric.md

**Files:**
- Create: `harnesses/mini-sqlite/rubric.md`
- Create: `harnesses/mini-sqlite/judge/rubric.md`
- Create: `harnesses/mini-sqlite/judge/calibration/README.md`
- Create: `harnesses/mini-sqlite/judge/calibration/scores.json`

- [ ] **Step 1: Create rubric.md**

```markdown
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
```

- [ ] **Step 2: Create judge/rubric.md**

```markdown
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
```

- [ ] **Step 3: Create calibration files**

```bash
mkdir -p harnesses/mini-sqlite/judge/calibration
```

`harnesses/mini-sqlite/judge/calibration/README.md`:
```markdown
# Judge Calibration

Reference implementations for calibrating the LLM judge.
`scores.json` contains human expert scores for each sample.
```

`harnesses/mini-sqlite/judge/calibration/scores.json`:
```json
{"calibration_version": "1.0.0", "samples": {}}
```

- [ ] **Step 4: Commit harness docs**

```bash
git add harnesses/mini-sqlite/
git commit -m "feat: add mini-sqlite harness scaffold docs

prompt.md, spec.md, rubric.md, judge/rubric.md."
```

---

## Chunk 2: Test Infrastructure + Tier 1 + Tier 2

### Task 4: Create test infrastructure

**Files:**
- Create: `harnesses/mini-sqlite/tests/__init__.py`
- Create: `harnesses/mini-sqlite/tests/conftest.py`
- Create: `harnesses/mini-sqlite/tests/pytest.ini`
- Create: `harnesses/mini-sqlite/tests/tier1/__init__.py`
- Create: `harnesses/mini-sqlite/tests/tier2/__init__.py`
- Create: `harnesses/mini-sqlite/tests/tier3/__init__.py`
- Create: `harnesses/mini-sqlite/tests/adversarial/__init__.py`
- Create: `harnesses/mini-sqlite/tests/extension/__init__.py`
- Create: `harnesses/mini-sqlite/tests/held-out/.gitkeep`
- Create: `harnesses/mini-sqlite/tests/reliability/__init__.py`
- Create: `harnesses/mini-sqlite/tests/performance/__init__.py`

- [ ] **Step 1: Create conftest.py**

```python
"""
conftest.py — shared fixtures and helpers for mini-sqlite tests.

Environment:
    MINI_SQLITE_CMD — command to invoke mini-sqlite (split with shlex).

Usage in tests:
    def test_something(db, sql):
        r = sql("SELECT * FROM users")
        assert r.returncode == 0
"""

import os
import shlex
import subprocess
from pathlib import Path
from typing import List, Optional

import pytest


def _discover_cmd() -> Optional[List[str]]:
    env_cmd = os.environ.get("MINI_SQLITE_CMD")
    if env_cmd:
        return shlex.split(env_cmd)
    return None


_CMD: Optional[List[str]] = _discover_cmd()
CMD_NOT_FOUND: bool = _CMD is None


def run_sql(db_path: Path, statement: str) -> subprocess.CompletedProcess:
    """Run mini-sqlite with db_path and statement. Returns CompletedProcess."""
    if _CMD is None:
        pytest.skip("MINI_SQLITE_CMD not set")
    return subprocess.run(
        _CMD + [str(db_path), statement],
        capture_output=True,
        text=True,
    )


def assert_success(result: subprocess.CompletedProcess) -> None:
    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


def assert_failure(result: subprocess.CompletedProcess, code: int = 1) -> None:
    assert result.returncode == code, (
        f"Expected exit {code} but got {result.returncode}\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


def assert_stdout(result: subprocess.CompletedProcess, expected: str) -> None:
    assert result.stdout.strip() == expected.strip(), (
        f"stdout mismatch.\nExpected: {expected!r}\nGot:      {result.stdout!r}"
    )


def _unescape_pipe(s: str) -> str:
    """Unescape \\| back to | for post-parse processing."""
    return s.replace("\\|", "|")


def parse_rows(result: subprocess.CompletedProcess) -> tuple[list[str], list[list[str]]]:
    """Parse pipe-separated SELECT output. Returns (header_cols, data_rows).

    Splits on unescaped | only. Values containing literal pipes are escaped as
    \\| in the output per the spec; callers receive unescaped values.
    """
    import re
    lines = result.stdout.strip().splitlines()
    if not lines:
        return [], []

    def split_row(line: str) -> list[str]:
        # Split on | not preceded by backslash, then unescape
        parts = re.split(r'(?<!\\)\|', line)
        return [_unescape_pipe(p) for p in parts]

    header = split_row(lines[0])
    rows = [split_row(line) for line in lines[1:]]
    return header, rows


@pytest.fixture
def db(tmp_path: Path) -> Path:
    """Path to a fresh database file (does not exist yet)."""
    return tmp_path / "test.db"


@pytest.fixture
def sql(db):
    """Shorthand: run SQL against the tmp db."""
    def _run(statement: str) -> subprocess.CompletedProcess:
        return run_sql(db, statement)
    return _run
```

- [ ] **Step 2: Create pytest.ini**

```ini
[pytest]
testpaths = .
python_files = test_*.py
python_functions = test_*
```

- [ ] **Step 3: Create __init__.py files and .gitkeep**

```bash
touch harnesses/mini-sqlite/tests/__init__.py
touch harnesses/mini-sqlite/tests/tier1/__init__.py
touch harnesses/mini-sqlite/tests/tier2/__init__.py
touch harnesses/mini-sqlite/tests/tier3/__init__.py
touch harnesses/mini-sqlite/tests/adversarial/__init__.py
touch harnesses/mini-sqlite/tests/extension/__init__.py
touch harnesses/mini-sqlite/tests/reliability/__init__.py
touch harnesses/mini-sqlite/tests/performance/__init__.py
touch harnesses/mini-sqlite/tests/held-out/.gitkeep
```

---

### Task 5: Tier 1 tests

**Files:**
- Create: `harnesses/mini-sqlite/tests/tier1/test_create_table.py`
- Create: `harnesses/mini-sqlite/tests/tier1/test_insert_select.py`
- Create: `harnesses/mini-sqlite/tests/tier1/test_delete.py`
- Create: `harnesses/mini-sqlite/tests/tier1/test_persistence.py`

- [ ] **Step 1: Create test_create_table.py**

```python
"""Tier 1: CREATE TABLE and DROP TABLE."""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_failure, assert_success, assert_stdout, run_sql


def test_create_table_returns_ok(db):
    r = run_sql(db, "CREATE TABLE users (id INTEGER, name TEXT)")
    assert_success(r)
    assert_stdout(r, "OK")


def test_create_table_with_three_columns(db):
    r = run_sql(db, "CREATE TABLE products (id INTEGER, name TEXT, price REAL)")
    assert_success(r)
    assert_stdout(r, "OK")


def test_drop_table_returns_ok(db):
    run_sql(db, "CREATE TABLE t (x INTEGER)")
    r = run_sql(db, "DROP TABLE t")
    assert_success(r)
    assert_stdout(r, "OK")


def test_drop_table_missing_exits_1(db):
    r = run_sql(db, "DROP TABLE nosuchable")
    assert_failure(r, code=1)
    assert r.stdout.strip() == ""
    assert "Error" in r.stderr


def test_select_from_empty_table_shows_header(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT)")
    r = run_sql(db, "SELECT * FROM t")
    assert_success(r)
    assert r.stdout.strip() == "id|name"


def test_select_from_unknown_table_exits_1(db):
    r = run_sql(db, "SELECT * FROM nosuchable")
    assert_failure(r, code=1)
    assert "no such table" in r.stderr


def test_create_table_with_null_type(db):
    r = run_sql(db, "CREATE TABLE t (a INTEGER, b TEXT, c REAL)")
    assert_success(r)
```

- [ ] **Step 2: Create test_insert_select.py**

```python
"""Tier 1: INSERT and SELECT."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_failure, assert_success, assert_stdout, parse_rows, run_sql


def test_insert_one_row_returns_1_row_affected(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT)")
    r = run_sql(db, "INSERT INTO t VALUES (1, 'Alice')")
    assert_success(r)
    assert_stdout(r, "1 row affected")


def test_select_star_returns_inserted_row(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 'Alice')")
    r = run_sql(db, "SELECT * FROM t")
    assert_success(r)
    header, rows = parse_rows(r)
    assert header == ["id", "name"]
    assert rows == [["1", "Alice"]]


def test_select_specific_columns(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT, age INTEGER)")
    run_sql(db, "INSERT INTO t VALUES (1, 'Alice', 30)")
    r = run_sql(db, "SELECT name, age FROM t")
    header, rows = parse_rows(r)
    assert header == ["name", "age"]
    assert rows == [["Alice", "30"]]


def test_select_multiple_rows_insertion_order(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 'Alice')")
    run_sql(db, "INSERT INTO t VALUES (2, 'Bob')")
    run_sql(db, "INSERT INTO t VALUES (3, 'Carol')")
    r = run_sql(db, "SELECT * FROM t")
    header, rows = parse_rows(r)
    assert rows == [["1", "Alice"], ["2", "Bob"], ["3", "Carol"]]


def test_insert_named_columns(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT, age INTEGER)")
    run_sql(db, "INSERT INTO t (name, id) VALUES ('Alice', 1)")
    r = run_sql(db, "SELECT * FROM t")
    header, rows = parse_rows(r)
    # Schema order: id, name, age; age defaults to NULL (empty)
    assert header == ["id", "name", "age"]
    assert rows == [["1", "Alice", ""]]


def test_insert_null_value(db):
    run_sql(db, "CREATE TABLE t (a INTEGER, b TEXT)")
    run_sql(db, "INSERT INTO t VALUES (NULL, 'hello')")
    r = run_sql(db, "SELECT * FROM t")
    header, rows = parse_rows(r)
    assert rows == [["", "hello"]]


def test_select_empty_table_shows_header_only(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT)")
    r = run_sql(db, "SELECT * FROM t")
    lines = r.stdout.strip().splitlines()
    assert lines == ["id|name"]


def test_select_star_column_order_matches_schema(db):
    """Columns always in schema order, regardless of INSERT column order."""
    run_sql(db, "CREATE TABLE t (a INTEGER, b TEXT, c REAL)")
    run_sql(db, "INSERT INTO t (c, a, b) VALUES (3.14, 1, 'hello')")
    r = run_sql(db, "SELECT * FROM t")
    header, rows = parse_rows(r)
    assert header == ["a", "b", "c"]
    assert rows[0][0] == "1"
    assert rows[0][1] == "hello"
```

- [ ] **Step 3: Create test_delete.py**

```python
"""Tier 1: DELETE (all rows)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, assert_stdout, parse_rows, run_sql


def test_delete_all_rows(db):
    run_sql(db, "CREATE TABLE t (id INTEGER)")
    run_sql(db, "INSERT INTO t VALUES (1)")
    run_sql(db, "INSERT INTO t VALUES (2)")
    r = run_sql(db, "DELETE FROM t")
    assert_success(r)
    assert_stdout(r, "2 rows affected")


def test_delete_all_from_empty_table(db):
    run_sql(db, "CREATE TABLE t (id INTEGER)")
    r = run_sql(db, "DELETE FROM t")
    assert_success(r)
    assert_stdout(r, "0 rows affected")


def test_delete_all_leaves_table_empty(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 'Alice')")
    run_sql(db, "DELETE FROM t")
    r = run_sql(db, "SELECT * FROM t")
    lines = r.stdout.strip().splitlines()
    assert lines == ["id|name"]
```

- [ ] **Step 4: Create test_persistence.py**

```python
"""Tier 1: data persists across process restarts."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, parse_rows, run_sql


def test_table_persists_after_restart(db):
    run_sql(db, "CREATE TABLE users (id INTEGER, name TEXT)")
    run_sql(db, "INSERT INTO users VALUES (1, 'Alice')")
    # New process invocation
    r = run_sql(db, "SELECT * FROM users")
    assert_success(r)
    header, rows = parse_rows(r)
    assert rows == [["1", "Alice"]]


def test_multiple_tables_persist(db):
    run_sql(db, "CREATE TABLE a (x INTEGER)")
    run_sql(db, "CREATE TABLE b (y TEXT)")
    run_sql(db, "INSERT INTO a VALUES (42)")
    run_sql(db, "INSERT INTO b VALUES ('hello')")
    r_a = run_sql(db, "SELECT * FROM a")
    r_b = run_sql(db, "SELECT * FROM b")
    _, rows_a = parse_rows(r_a)
    _, rows_b = parse_rows(r_b)
    assert rows_a == [["42"]]
    assert rows_b == [["hello"]]


def test_new_db_file_created_on_first_create(tmp_path):
    db = tmp_path / "brand_new.db"
    assert not db.exists()
    r = run_sql(db, "CREATE TABLE t (x INTEGER)")
    assert_success(r)
    assert db.exists()
```

---

### Task 6: Tier 2 tests

**Files:**
- Create: `harnesses/mini-sqlite/tests/tier2/test_where.py`
- Create: `harnesses/mini-sqlite/tests/tier2/test_update.py`
- Create: `harnesses/mini-sqlite/tests/tier2/test_order_limit.py`

- [ ] **Step 1: Create test_where.py**

```python
"""Tier 2: WHERE clause with various operators."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, parse_rows, run_sql


def _setup(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT, score REAL)")
    run_sql(db, "INSERT INTO t VALUES (1, 'Alice', 90.5)")
    run_sql(db, "INSERT INTO t VALUES (2, 'Bob', 75.0)")
    run_sql(db, "INSERT INTO t VALUES (3, 'Carol', 90.5)")
    run_sql(db, "INSERT INTO t VALUES (4, 'Dave', NULL)")


def test_where_equality(db):
    _setup(db)
    r = run_sql(db, "SELECT name FROM t WHERE id = 2")
    _, rows = parse_rows(r)
    assert rows == [["Bob"]]


def test_where_inequality(db):
    _setup(db)
    r = run_sql(db, "SELECT id FROM t WHERE id != 2")
    _, rows = parse_rows(r)
    ids = [row[0] for row in rows]
    assert "2" not in ids
    assert len(ids) == 3


def test_where_less_than(db):
    _setup(db)
    r = run_sql(db, "SELECT name FROM t WHERE id < 3")
    _, rows = parse_rows(r)
    assert len(rows) == 2


def test_where_greater_than(db):
    _setup(db)
    r = run_sql(db, "SELECT name FROM t WHERE score > 80.0")
    _, rows = parse_rows(r)
    names = [r[0] for r in rows]
    assert "Alice" in names
    assert "Carol" in names
    assert "Bob" not in names


def test_where_and(db):
    _setup(db)
    r = run_sql(db, "SELECT name FROM t WHERE id > 1 AND score > 80.0")
    _, rows = parse_rows(r)
    assert rows == [["Carol"]]


def test_where_or(db):
    _setup(db)
    r = run_sql(db, "SELECT name FROM t WHERE id = 1 OR id = 3")
    _, rows = parse_rows(r)
    names = {r[0] for r in rows}
    assert names == {"Alice", "Carol"}


def test_where_is_null(db):
    _setup(db)
    r = run_sql(db, "SELECT name FROM t WHERE score IS NULL")
    _, rows = parse_rows(r)
    assert rows == [["Dave"]]


def test_where_is_not_null(db):
    _setup(db)
    r = run_sql(db, "SELECT name FROM t WHERE score IS NOT NULL")
    _, rows = parse_rows(r)
    assert len(rows) == 3


def test_where_not(db):
    _setup(db)
    r = run_sql(db, "SELECT name FROM t WHERE NOT id = 1")
    _, rows = parse_rows(r)
    names = [r[0] for r in rows]
    assert "Alice" not in names


def test_where_no_matches_returns_header_only(db):
    _setup(db)
    r = run_sql(db, "SELECT * FROM t WHERE id = 999")
    lines = r.stdout.strip().splitlines()
    assert len(lines) == 1  # header only


def test_delete_where(db):
    _setup(db)
    r = run_sql(db, "DELETE FROM t WHERE id = 2")
    assert_success(r)
    assert r.stdout.strip() == "1 rows affected"
    r2 = run_sql(db, "SELECT name FROM t WHERE id = 2")
    _, rows = parse_rows(r2)
    assert rows == []
```

- [ ] **Step 2: Create test_update.py**

```python
"""Tier 2: UPDATE."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, parse_rows, run_sql


def test_update_all_rows(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, val TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 'old')")
    run_sql(db, "INSERT INTO t VALUES (2, 'old')")
    r = run_sql(db, "UPDATE t SET val = 'new'")
    assert_success(r)
    assert r.stdout.strip() == "2 rows affected"


def test_update_with_where(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 'Alice')")
    run_sql(db, "INSERT INTO t VALUES (2, 'Bob')")
    run_sql(db, "UPDATE t SET name = 'Alicia' WHERE id = 1")
    r = run_sql(db, "SELECT name FROM t WHERE id = 1")
    _, rows = parse_rows(r)
    assert rows == [["Alicia"]]


def test_update_no_match_returns_0(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 'Alice')")
    r = run_sql(db, "UPDATE t SET name = 'X' WHERE id = 999")
    assert r.stdout.strip() == "0 rows affected"


def test_update_multiple_columns(db):
    run_sql(db, "CREATE TABLE t (a INTEGER, b TEXT, c REAL)")
    run_sql(db, "INSERT INTO t VALUES (1, 'old', 1.0)")
    run_sql(db, "UPDATE t SET b = 'new', c = 2.0 WHERE a = 1")
    r = run_sql(db, "SELECT * FROM t")
    _, rows = parse_rows(r)
    assert rows[0] == ["1", "new", "2.0"]


def test_update_rows_matched_not_changed(db):
    """UPDATE counts rows matched by WHERE, not rows where value changed."""
    run_sql(db, "CREATE TABLE t (id INTEGER, val TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 'same')")
    run_sql(db, "INSERT INTO t VALUES (2, 'same')")
    r = run_sql(db, "UPDATE t SET val = 'same'")
    assert r.stdout.strip() == "2 rows affected"
```

- [ ] **Step 3: Create test_order_limit.py**

```python
"""Tier 2: ORDER BY, LIMIT, OFFSET."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, parse_rows, run_sql


def _setup(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, score INTEGER, name TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 30, 'Charlie')")
    run_sql(db, "INSERT INTO t VALUES (2, 10, 'Alice')")
    run_sql(db, "INSERT INTO t VALUES (3, 20, 'Bob')")


def test_order_by_asc(db):
    _setup(db)
    r = run_sql(db, "SELECT name FROM t ORDER BY score ASC")
    _, rows = parse_rows(r)
    assert [r[0] for r in rows] == ["Alice", "Bob", "Charlie"]


def test_order_by_desc(db):
    _setup(db)
    r = run_sql(db, "SELECT name FROM t ORDER BY score DESC")
    _, rows = parse_rows(r)
    assert [r[0] for r in rows] == ["Charlie", "Bob", "Alice"]


def test_order_by_stable_on_ties(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, score INTEGER)")
    run_sql(db, "INSERT INTO t VALUES (1, 5)")
    run_sql(db, "INSERT INTO t VALUES (2, 5)")
    run_sql(db, "INSERT INTO t VALUES (3, 5)")
    r = run_sql(db, "SELECT id FROM t ORDER BY score ASC")
    _, rows = parse_rows(r)
    # Stable sort: original insertion order preserved for ties
    assert [r[0] for r in rows] == ["1", "2", "3"]


def test_order_by_null_sorts_last_asc(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, val INTEGER)")
    run_sql(db, "INSERT INTO t VALUES (1, NULL)")
    run_sql(db, "INSERT INTO t VALUES (2, 10)")
    run_sql(db, "INSERT INTO t VALUES (3, 5)")
    r = run_sql(db, "SELECT id FROM t ORDER BY val ASC")
    _, rows = parse_rows(r)
    ids = [r[0] for r in rows]
    assert ids[-1] == "1"  # NULL sorts last


def test_order_by_null_sorts_last_desc(db):
    """NULLs sort last in DESC too — intentional non-standard behavior."""
    run_sql(db, "CREATE TABLE t (id INTEGER, val INTEGER)")
    run_sql(db, "INSERT INTO t VALUES (1, NULL)")
    run_sql(db, "INSERT INTO t VALUES (2, 10)")
    run_sql(db, "INSERT INTO t VALUES (3, 5)")
    r = run_sql(db, "SELECT id FROM t ORDER BY val DESC")
    _, rows = parse_rows(r)
    ids = [r[0] for r in rows]
    # DESC: 10, 5, NULL — NULL last even in descending order
    assert ids[0] == "2"   # val=10 first
    assert ids[-1] == "1"  # NULL last


def test_limit(db):
    _setup(db)
    r = run_sql(db, "SELECT id FROM t ORDER BY id ASC LIMIT 2")
    _, rows = parse_rows(r)
    assert len(rows) == 2
    assert rows[0][0] == "1"


def test_limit_offset(db):
    _setup(db)
    r = run_sql(db, "SELECT id FROM t ORDER BY id ASC LIMIT 2 OFFSET 1")
    _, rows = parse_rows(r)
    assert len(rows) == 2
    assert rows[0][0] == "2"
```

- [ ] **Step 4: Commit tier1 + tier2 tests**

```bash
git add harnesses/mini-sqlite/tests/
git commit -m "feat: add mini-sqlite test infrastructure and tier1/tier2 tests

conftest.py, pytest.ini, and 40 tests covering CREATE TABLE,
INSERT, SELECT, DELETE, persistence, WHERE, UPDATE, ORDER BY, LIMIT."
```

---

## Chunk 3: Tier 3 + Adversarial

### Task 7: Tier 3 tests

**Files:**
- Create: `harnesses/mini-sqlite/tests/tier3/test_joins.py`
- Create: `harnesses/mini-sqlite/tests/tier3/test_aggregates.py`
- Create: `harnesses/mini-sqlite/tests/tier3/test_transactions.py`

- [ ] **Step 1: Create test_joins.py**

```python
"""Tier 3: INNER JOIN and LEFT JOIN."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, parse_rows, run_sql


def _setup(db):
    run_sql(db, "CREATE TABLE users (id INTEGER, name TEXT)")
    run_sql(db, "CREATE TABLE orders (id INTEGER, user_id INTEGER, item TEXT)")
    run_sql(db, "INSERT INTO users VALUES (1, 'Alice')")
    run_sql(db, "INSERT INTO users VALUES (2, 'Bob')")
    run_sql(db, "INSERT INTO users VALUES (3, 'Carol')")
    run_sql(db, "INSERT INTO orders VALUES (1, 1, 'Book')")
    run_sql(db, "INSERT INTO orders VALUES (2, 1, 'Pen')")
    run_sql(db, "INSERT INTO orders VALUES (3, 2, 'Notebook')")


def test_inner_join_basic(db):
    _setup(db)
    r = run_sql(db, "SELECT users.name, orders.item FROM users INNER JOIN orders ON users.id = orders.user_id")
    assert_success(r)
    _, rows = parse_rows(r)
    names = [r[0] for r in rows]
    assert "Alice" in names
    assert "Bob" in names
    assert "Carol" not in names


def test_inner_join_excludes_no_match(db):
    _setup(db)
    r = run_sql(db, "SELECT users.name FROM users INNER JOIN orders ON users.id = orders.user_id")
    _, rows = parse_rows(r)
    names = [r[0] for r in rows]
    assert "Carol" not in names


def test_left_join_includes_non_matching(db):
    _setup(db)
    r = run_sql(db, "SELECT users.name, orders.item FROM users LEFT JOIN orders ON users.id = orders.user_id")
    assert_success(r)
    _, rows = parse_rows(r)
    names = [r[0] for r in rows]
    assert "Carol" in names
    # Carol's item should be NULL (empty)
    carol_row = [r for r in rows if r[0] == "Carol"]
    assert len(carol_row) == 1
    assert carol_row[0][1] == ""  # NULL → empty


def test_inner_join_all_match(db):
    _setup(db)
    r = run_sql(db, "SELECT orders.item FROM users INNER JOIN orders ON users.id = orders.user_id ORDER BY orders.id ASC")
    _, rows = parse_rows(r)
    assert [r[0] for r in rows] == ["Book", "Pen", "Notebook"]


def test_select_star_join_column_order_and_disambiguation(db):
    """SELECT * on a JOIN: left-table cols first, right-table cols second.
    Ambiguous column names (both tables have 'id') must be disambiguated
    as 'users.id' and 'orders.id' in the header."""
    _setup(db)
    r = run_sql(db, "SELECT * FROM users INNER JOIN orders ON users.id = orders.user_id")
    assert_success(r)
    header, rows = parse_rows(r)
    # Header must include disambiguated names for shared column 'id'
    assert "users.id" in header, f"Expected 'users.id' in header, got {header}"
    assert "orders.id" in header, f"Expected 'orders.id' in header, got {header}"
    # Left-table columns come before right-table columns
    assert header.index("users.id") < header.index("orders.id")
    assert header.index("users.id") < header.index("item")
```

- [ ] **Step 2: Create test_aggregates.py**

```python
"""Tier 3: GROUP BY, HAVING, and aggregate functions."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, parse_rows, run_sql


def _setup(db):
    run_sql(db, "CREATE TABLE sales (id INTEGER, dept TEXT, amount REAL)")
    run_sql(db, "INSERT INTO sales VALUES (1, 'Engineering', 100.0)")
    run_sql(db, "INSERT INTO sales VALUES (2, 'Engineering', 200.0)")
    run_sql(db, "INSERT INTO sales VALUES (3, 'Marketing', 50.0)")
    run_sql(db, "INSERT INTO sales VALUES (4, 'Marketing', NULL)")


def test_count_star(db):
    _setup(db)
    r = run_sql(db, "SELECT COUNT(*) FROM sales")
    _, rows = parse_rows(r)
    assert rows == [["4"]]


def test_count_column_ignores_null(db):
    _setup(db)
    r = run_sql(db, "SELECT COUNT(amount) FROM sales")
    _, rows = parse_rows(r)
    assert rows == [["3"]]


def test_sum(db):
    _setup(db)
    r = run_sql(db, "SELECT SUM(amount) FROM sales")
    _, rows = parse_rows(r)
    assert float(rows[0][0]) == 350.0


def test_avg(db):
    _setup(db)
    r = run_sql(db, "SELECT AVG(amount) FROM sales WHERE dept = 'Engineering'")
    _, rows = parse_rows(r)
    assert abs(float(rows[0][0]) - 150.0) < 0.001


def test_min_max(db):
    _setup(db)
    r_min = run_sql(db, "SELECT MIN(amount) FROM sales")
    r_max = run_sql(db, "SELECT MAX(amount) FROM sales")
    _, min_rows = parse_rows(r_min)
    _, max_rows = parse_rows(r_max)
    assert float(min_rows[0][0]) == 50.0
    assert float(max_rows[0][0]) == 200.0


def test_group_by(db):
    _setup(db)
    r = run_sql(db, "SELECT dept, COUNT(*) FROM sales GROUP BY dept")
    assert_success(r)
    _, rows = parse_rows(r)
    dept_counts = {r[0]: int(r[1]) for r in rows}
    assert dept_counts["Engineering"] == 2
    assert dept_counts["Marketing"] == 2


def test_having_filters_groups(db):
    _setup(db)
    r = run_sql(db, "SELECT dept, SUM(amount) FROM sales GROUP BY dept HAVING SUM(amount) > 100")
    assert_success(r)
    _, rows = parse_rows(r)
    depts = [r[0] for r in rows]
    assert "Engineering" in depts
    assert "Marketing" not in depts
```

- [ ] **Step 3: Create test_transactions.py**

```python
"""Tier 3: BEGIN, COMMIT, ROLLBACK."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_failure, assert_success, assert_stdout, parse_rows, run_sql


def test_begin_commit_persists(db):
    run_sql(db, "CREATE TABLE t (id INTEGER)")
    run_sql(db, "BEGIN")
    run_sql(db, "INSERT INTO t VALUES (1)")
    run_sql(db, "COMMIT")
    r = run_sql(db, "SELECT * FROM t")
    _, rows = parse_rows(r)
    assert rows == [["1"]]


def test_rollback_reverts_insert(db):
    run_sql(db, "CREATE TABLE t (id INTEGER)")
    run_sql(db, "BEGIN")
    run_sql(db, "INSERT INTO t VALUES (42)")
    run_sql(db, "ROLLBACK")
    r = run_sql(db, "SELECT * FROM t")
    _, rows = parse_rows(r)
    assert rows == []


def test_rollback_reverts_delete(db):
    run_sql(db, "CREATE TABLE t (id INTEGER)")
    run_sql(db, "INSERT INTO t VALUES (1)")
    run_sql(db, "BEGIN")
    run_sql(db, "DELETE FROM t")
    run_sql(db, "ROLLBACK")
    r = run_sql(db, "SELECT * FROM t")
    _, rows = parse_rows(r)
    assert rows == [["1"]]


def test_rollback_reverts_update(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 'Alice')")
    run_sql(db, "BEGIN")
    run_sql(db, "UPDATE t SET name = 'Changed'")
    run_sql(db, "ROLLBACK")
    r = run_sql(db, "SELECT name FROM t")
    _, rows = parse_rows(r)
    assert rows == [["Alice"]]


def test_begin_returns_ok(db):
    r = run_sql(db, "BEGIN")
    assert_success(r)
    assert_stdout(r, "OK")
    run_sql(db, "COMMIT")


def test_commit_without_begin_exits_1(db):
    r = run_sql(db, "COMMIT")
    assert_failure(r, code=1)
    assert "no active transaction" in r.stderr.lower()


def test_rollback_without_begin_exits_1(db):
    r = run_sql(db, "ROLLBACK")
    assert_failure(r, code=1)
    assert "no active transaction" in r.stderr.lower()


def test_begin_twice_exits_1(db):
    run_sql(db, "BEGIN")
    r = run_sql(db, "BEGIN")
    assert_failure(r, code=1)
    assert "transaction already active" in r.stderr.lower()
    run_sql(db, "ROLLBACK")


def test_rollback_reverts_create_table(db):
    """ROLLBACK must undo DDL (CREATE TABLE) per spec."""
    run_sql(db, "BEGIN")
    run_sql(db, "CREATE TABLE temp_table (id INTEGER)")
    run_sql(db, "ROLLBACK")
    # After rollback, temp_table must not exist
    r = run_sql(db, "SELECT * FROM temp_table")
    assert r.returncode != 0, "Table should not exist after ROLLBACK"
    assert "no such table" in r.stderr.lower()
```

---

### Task 8: Adversarial tests

**Files:**
- Create: `harnesses/mini-sqlite/tests/adversarial/test_sql_safety.py`
- Create: `harnesses/mini-sqlite/tests/adversarial/test_null_semantics.py`
- Create: `harnesses/mini-sqlite/tests/adversarial/test_type_handling.py`
- Create: `harnesses/mini-sqlite/tests/adversarial/test_error_messages.py`
- Create: `harnesses/mini-sqlite/tests/adversarial/test_edge_cases.py`
- Create: `harnesses/mini-sqlite/tests/adversarial/test_forbidden_imports.py`

- [ ] **Step 0: Create test_forbidden_imports.py**

```python
"""Adversarial: verify agent did not use forbidden stdlib modules (import sqlite3)."""

import os
import shlex
import sys
from pathlib import Path

import pytest


def test_no_sqlite3_import():
    """Agent implementation must not use 'import sqlite3'.

    The spec explicitly forbids delegating to the stdlib sqlite3 module.
    This test reads the agent's source file and asserts the forbidden import
    is absent.
    """
    cmd_str = os.environ.get("MINI_SQLITE_CMD", "")
    if not cmd_str:
        pytest.skip("MINI_SQLITE_CMD not set")
    parts = shlex.split(cmd_str)
    # The source file is typically the last argument (e.g. "python mini_sqlite.py")
    source_file = Path(parts[-1])
    if not source_file.exists():
        pytest.skip(f"Source file not found: {source_file}")
    content = source_file.read_text()
    assert "import sqlite3" not in content, (
        "Agent used 'import sqlite3' which is explicitly forbidden by the spec. "
        "The implementation must be built from scratch without the stdlib sqlite3 module."
    )
```

- [ ] **Step 1: Create test_sql_safety.py**

```python
"""Adversarial: SQL injection stored as data (not executed)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, parse_rows, run_sql


def test_sql_in_string_value_stored_not_executed(db):
    """SQL injection attempt in a value must be stored as a string."""
    run_sql(db, "CREATE TABLE t (id INTEGER, payload TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 'DROP TABLE t; --')")
    r = run_sql(db, "SELECT payload FROM t")
    assert_success(r)
    _, rows = parse_rows(r)
    assert rows == [["DROP TABLE t; --"]]


def test_single_quote_in_value(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, \"it's a test\")")
    r = run_sql(db, "SELECT name FROM t")
    assert_success(r)
    _, rows = parse_rows(r)
    assert "it's a test" in rows[0][0]


def test_pipe_in_value_escaped(db):
    """Value containing | must be escaped as \\| in output."""
    run_sql(db, "CREATE TABLE t (id INTEGER, val TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 'a|b')")
    r = run_sql(db, "SELECT val FROM t")
    assert_success(r)
    out = r.stdout.strip()
    # The data row must not parse as two columns
    lines = out.splitlines()
    assert len(lines) == 2  # header + 1 row
    # The value should contain the escaped pipe
    assert "\\|" in lines[1] or "a|b" in lines[1]


def test_empty_string_value_roundtrips(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, val TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, '')")
    r = run_sql(db, "SELECT val FROM t")
    _, rows = parse_rows(r)
    # SELECT val selects one column; empty string stored as '' should roundtrip as ""
    assert rows == [[""]]


def test_unicode_value_stored(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 'こんにちは')")
    r = run_sql(db, "SELECT name FROM t")
    assert_success(r)
    assert "こんにちは" in r.stdout


def test_numeric_string_not_coerced(db):
    """TEXT column stores '42' as text, not integer."""
    run_sql(db, "CREATE TABLE t (val TEXT)")
    run_sql(db, "INSERT INTO t VALUES ('42')")
    r = run_sql(db, "SELECT val FROM t")
    _, rows = parse_rows(r)
    assert rows == [["42"]]
```

- [ ] **Step 2: Create test_null_semantics.py**

```python
"""Adversarial: NULL edge cases."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, parse_rows, run_sql


def test_null_not_equal_null(db):
    """WHERE col = NULL should match nothing (NULL != NULL)."""
    run_sql(db, "CREATE TABLE t (val INTEGER)")
    run_sql(db, "INSERT INTO t VALUES (NULL)")
    r = run_sql(db, "SELECT * FROM t WHERE val = NULL")
    _, rows = parse_rows(r)
    assert rows == []


def test_null_is_null_matches(db):
    run_sql(db, "CREATE TABLE t (val INTEGER)")
    run_sql(db, "INSERT INTO t VALUES (NULL)")
    run_sql(db, "INSERT INTO t VALUES (1)")
    r = run_sql(db, "SELECT val FROM t WHERE val IS NULL")
    _, rows = parse_rows(r)
    assert rows == [[""]]


def test_null_in_order_by_last(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, val INTEGER)")
    run_sql(db, "INSERT INTO t VALUES (1, NULL)")
    run_sql(db, "INSERT INTO t VALUES (2, 5)")
    run_sql(db, "INSERT INTO t VALUES (3, 1)")
    r = run_sql(db, "SELECT id FROM t ORDER BY val ASC")
    _, rows = parse_rows(r)
    assert rows[-1][0] == "1"  # NULL row last


def test_count_star_counts_null_rows(db):
    run_sql(db, "CREATE TABLE t (val INTEGER)")
    run_sql(db, "INSERT INTO t VALUES (NULL)")
    run_sql(db, "INSERT INTO t VALUES (NULL)")
    r = run_sql(db, "SELECT COUNT(*) FROM t")
    _, rows = parse_rows(r)
    assert rows == [["2"]]


def test_count_col_skips_nulls(db):
    run_sql(db, "CREATE TABLE t (val INTEGER)")
    run_sql(db, "INSERT INTO t VALUES (NULL)")
    run_sql(db, "INSERT INTO t VALUES (5)")
    r = run_sql(db, "SELECT COUNT(val) FROM t")
    _, rows = parse_rows(r)
    assert rows == [["1"]]


def test_sum_ignores_nulls(db):
    run_sql(db, "CREATE TABLE t (val REAL)")
    run_sql(db, "INSERT INTO t VALUES (10.0)")
    run_sql(db, "INSERT INTO t VALUES (NULL)")
    run_sql(db, "INSERT INTO t VALUES (20.0)")
    r = run_sql(db, "SELECT SUM(val) FROM t")
    _, rows = parse_rows(r)
    assert float(rows[0][0]) == 30.0


def test_null_output_is_empty_field(db):
    run_sql(db, "CREATE TABLE t (a INTEGER, b INTEGER)")
    run_sql(db, "INSERT INTO t VALUES (1, NULL)")
    r = run_sql(db, "SELECT * FROM t")
    lines = r.stdout.strip().splitlines()
    assert lines[1] == "1|"
```

- [ ] **Step 3: Create test_type_handling.py**

```python
"""Adversarial: integer/real edge cases and type storage."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, parse_rows, run_sql


def test_integer_roundtrip(db):
    run_sql(db, "CREATE TABLE t (val INTEGER)")
    run_sql(db, "INSERT INTO t VALUES (9999999999)")
    r = run_sql(db, "SELECT val FROM t")
    _, rows = parse_rows(r)
    assert rows == [["9999999999"]]


def test_negative_integer(db):
    run_sql(db, "CREATE TABLE t (val INTEGER)")
    run_sql(db, "INSERT INTO t VALUES (-42)")
    r = run_sql(db, "SELECT val FROM t")
    _, rows = parse_rows(r)
    assert rows == [["-42"]]


def test_real_roundtrip(db):
    run_sql(db, "CREATE TABLE t (val REAL)")
    run_sql(db, "INSERT INTO t VALUES (3.14)")
    r = run_sql(db, "SELECT val FROM t")
    _, rows = parse_rows(r)
    assert abs(float(rows[0][0]) - 3.14) < 0.0001


def test_zero_value(db):
    run_sql(db, "CREATE TABLE t (val INTEGER)")
    run_sql(db, "INSERT INTO t VALUES (0)")
    r = run_sql(db, "SELECT val FROM t")
    _, rows = parse_rows(r)
    assert rows == [["0"]]


def test_where_compares_integers_correctly(db):
    run_sql(db, "CREATE TABLE t (val INTEGER)")
    run_sql(db, "INSERT INTO t VALUES (9)")
    run_sql(db, "INSERT INTO t VALUES (10)")
    run_sql(db, "INSERT INTO t VALUES (11)")
    r = run_sql(db, "SELECT val FROM t WHERE val > 9")
    _, rows = parse_rows(r)
    assert len(rows) == 2
    # Must be numeric comparison, not lexicographic
```

- [ ] **Step 4: Create test_error_messages.py**

```python
"""Adversarial: exact error message format."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_failure, run_sql


def test_unknown_table_error_message(db):
    r = run_sql(db, "SELECT * FROM nosuchable")
    assert_failure(r)
    assert "no such table" in r.stderr.lower()
    assert r.stdout.strip() == ""


def test_drop_unknown_table_error_message(db):
    r = run_sql(db, "DROP TABLE nosuchable")
    assert_failure(r)
    assert "no such table" in r.stderr.lower()


def test_select_unknown_column(db):
    run_sql(db, "CREATE TABLE t (id INTEGER)")
    r = run_sql(db, "SELECT nosuchcol FROM t")
    assert_failure(r)
    assert "no such column" in r.stderr.lower()


def test_unsupported_feature_primary_key(db):
    r = run_sql(db, "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    assert_failure(r)
    assert "unsupported" in r.stderr.lower()


def test_stderr_empty_on_success(db):
    run_sql(db, "CREATE TABLE t (id INTEGER)")
    r = run_sql(db, "INSERT INTO t VALUES (1)")
    assert r.stderr.strip() == ""


def test_stdout_empty_on_error(db):
    r = run_sql(db, "SELECT * FROM nosuchable")
    assert r.stdout.strip() == ""
```

- [ ] **Step 5: Create test_edge_cases.py**

```python
"""Adversarial: edge cases in SELECT output format and general behavior."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, parse_rows, run_sql


def test_large_text_value(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, val TEXT)")
    big = "X" * 100_000
    run_sql(db, f"INSERT INTO t VALUES (1, '{big}')")
    r = run_sql(db, "SELECT val FROM t")
    assert_success(r)
    assert big in r.stdout


def test_many_columns(db):
    cols = ", ".join(f"c{i} INTEGER" for i in range(20))
    run_sql(db, f"CREATE TABLE t ({cols})")
    vals = ", ".join(str(i) for i in range(20))
    run_sql(db, f"INSERT INTO t VALUES ({vals})")
    r = run_sql(db, "SELECT * FROM t")
    header, rows = parse_rows(r)
    assert len(header) == 20
    assert len(rows[0]) == 20


def test_many_rows(db):
    run_sql(db, "CREATE TABLE t (id INTEGER)")
    for i in range(100):
        run_sql(db, f"INSERT INTO t VALUES ({i})")
    r = run_sql(db, "SELECT id FROM t")
    _, rows = parse_rows(r)
    assert len(rows) == 100


def test_empty_table_after_delete_all(db):
    run_sql(db, "CREATE TABLE t (id INTEGER)")
    run_sql(db, "INSERT INTO t VALUES (1)")
    run_sql(db, "DELETE FROM t")
    r = run_sql(db, "SELECT * FROM t")
    lines = r.stdout.strip().splitlines()
    assert lines == ["id"]


def test_where_on_real_column(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, score REAL)")
    run_sql(db, "INSERT INTO t VALUES (1, 9.5)")
    run_sql(db, "INSERT INTO t VALUES (2, 7.0)")
    r = run_sql(db, "SELECT id FROM t WHERE score > 8.0")
    _, rows = parse_rows(r)
    assert rows == [["1"]]
```

- [ ] **Step 6: Commit tier3 + adversarial**

```bash
git add harnesses/mini-sqlite/tests/tier3/ harnesses/mini-sqlite/tests/adversarial/
git commit -m "feat: add mini-sqlite tier3 and adversarial tests

Joins, aggregates, transactions (tier3) and ~50 adversarial tests
covering SQL safety, NULL semantics, type handling, error messages."
```

---

## Chunk 4: Extension + Reliability + Performance

### Task 9: Extension tests — CREATE INDEX + EXPLAIN

**Files:**
- Create: `harnesses/mini-sqlite/tests/extension/prompt.md`
- Create: `harnesses/mini-sqlite/tests/extension/test_indexes.py`

- [ ] **Step 1: Create extension/prompt.md**

```markdown
# mini-sqlite Extension: Indexes

The mini-sqlite implementation now needs to support indexes.

Add the following:

- `CREATE INDEX name ON table(col)` — creates an index on a column; print `OK`
- `EXPLAIN query` — shows the query plan; when a query uses an index, output must contain the word `index` (case-insensitive); when no index would be used, output must NOT contain the word `index`

The EXPLAIN output format is up to you — a simple one-line description is fine.

Write tests for the new functionality.
```

- [ ] **Step 2: Create test_indexes.py**

```python
"""Extension: CREATE INDEX and EXPLAIN — 16 tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_failure, assert_success, assert_stdout, parse_rows, run_sql


def test_create_index_returns_ok(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT)")
    r = run_sql(db, "CREATE INDEX idx_name ON t(name)")
    assert_success(r)
    assert_stdout(r, "OK")


def test_create_index_on_nonexistent_table_exits_1(db):
    r = run_sql(db, "CREATE INDEX idx ON nosuchable(col)")
    assert_failure(r)


def test_explain_seq_scan_no_index_word(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT)")
    r = run_sql(db, "EXPLAIN SELECT * FROM t WHERE id = 1")
    assert_success(r)
    assert "index" not in r.stdout.lower()


def test_explain_with_index_contains_index_word(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT)")
    run_sql(db, "CREATE INDEX idx_id ON t(id)")
    r = run_sql(db, "EXPLAIN SELECT * FROM t WHERE id = 1")
    assert_success(r)
    assert "index" in r.stdout.lower()


def test_index_does_not_break_select(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, val TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 'a')")
    run_sql(db, "INSERT INTO t VALUES (2, 'b')")
    run_sql(db, "CREATE INDEX idx_id ON t(id)")
    r = run_sql(db, "SELECT val FROM t WHERE id = 2")
    assert_success(r)
    _, rows = parse_rows(r)
    assert rows == [["b"]]


def test_index_does_not_break_order(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, val TEXT)")
    run_sql(db, "INSERT INTO t VALUES (3, 'c')")
    run_sql(db, "INSERT INTO t VALUES (1, 'a')")
    run_sql(db, "INSERT INTO t VALUES (2, 'b')")
    run_sql(db, "CREATE INDEX idx_id ON t(id)")
    r = run_sql(db, "SELECT val FROM t ORDER BY id ASC")
    _, rows = parse_rows(r)
    assert [r[0] for r in rows] == ["a", "b", "c"]


def test_index_does_not_break_insert(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, val TEXT)")
    run_sql(db, "CREATE INDEX idx_id ON t(id)")
    run_sql(db, "INSERT INTO t VALUES (10, 'ten')")
    r = run_sql(db, "SELECT val FROM t WHERE id = 10")
    _, rows = parse_rows(r)
    assert rows == [["ten"]]


def test_index_does_not_break_update(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, val TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 'old')")
    run_sql(db, "CREATE INDEX idx_id ON t(id)")
    run_sql(db, "UPDATE t SET val = 'new' WHERE id = 1")
    r = run_sql(db, "SELECT val FROM t WHERE id = 1")
    _, rows = parse_rows(r)
    assert rows == [["new"]]


def test_index_does_not_break_delete(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, val TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 'a')")
    run_sql(db, "INSERT INTO t VALUES (2, 'b')")
    run_sql(db, "CREATE INDEX idx_id ON t(id)")
    run_sql(db, "DELETE FROM t WHERE id = 1")
    r = run_sql(db, "SELECT * FROM t")
    _, rows = parse_rows(r)
    assert len(rows) == 1


def test_create_index_on_text_column(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT)")
    r = run_sql(db, "CREATE INDEX idx_name ON t(name)")
    assert_success(r)


def test_explain_no_index_on_unindexed_col(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT, score REAL)")
    run_sql(db, "CREATE INDEX idx_id ON t(id)")
    # Query on 'score' which has no index
    r = run_sql(db, "EXPLAIN SELECT * FROM t WHERE score > 5.0")
    assert_success(r)
    assert "index" not in r.stdout.lower()


def test_explain_uses_index_on_indexed_col(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT, score REAL)")
    run_sql(db, "CREATE INDEX idx_score ON t(score)")
    r = run_sql(db, "EXPLAIN SELECT * FROM t WHERE score > 5.0")
    assert_success(r)
    assert "index" in r.stdout.lower()


def test_multiple_indexes(db):
    run_sql(db, "CREATE TABLE t (a INTEGER, b TEXT, c REAL)")
    run_sql(db, "CREATE INDEX idx_a ON t(a)")
    run_sql(db, "CREATE INDEX idx_b ON t(b)")
    r_a = run_sql(db, "EXPLAIN SELECT * FROM t WHERE a = 1")
    r_b = run_sql(db, "EXPLAIN SELECT * FROM t WHERE b = 'x'")
    assert "index" in r_a.stdout.lower()
    assert "index" in r_b.stdout.lower()


def test_index_persists_after_restart(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, val TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 'a')")
    run_sql(db, "CREATE INDEX idx_id ON t(id)")
    # New process — index must still work
    r = run_sql(db, "EXPLAIN SELECT * FROM t WHERE id = 1")
    assert_success(r)
    assert "index" in r.stdout.lower()


def test_explain_output_not_empty(db):
    run_sql(db, "CREATE TABLE t (id INTEGER)")
    r = run_sql(db, "EXPLAIN SELECT * FROM t")
    assert_success(r)
    assert r.stdout.strip() != ""


def test_index_name_can_be_reused_after_drop(db):
    """After DROP TABLE, the index name should be free to reuse."""
    run_sql(db, "CREATE TABLE t (id INTEGER)")
    run_sql(db, "CREATE INDEX idx ON t(id)")
    run_sql(db, "DROP TABLE t")
    run_sql(db, "CREATE TABLE t2 (val TEXT)")
    r = run_sql(db, "CREATE INDEX idx ON t2(val)")
    assert_success(r)
```

---

### Task 10: Reliability tests

**Files:**
- Create: `harnesses/mini-sqlite/tests/reliability/test_durability.py`
- Create: `harnesses/mini-sqlite/tests/reliability/test_corruption.py`

- [ ] **Step 1: Create test_durability.py**

```python
"""Reliability: persistence and data integrity."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, parse_rows, run_sql


def test_data_persists_after_process_exit(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 'Alice')")
    r = run_sql(db, "SELECT * FROM t")
    assert_success(r)
    _, rows = parse_rows(r)
    assert rows == [["1", "Alice"]]


def test_null_value_persists(db):
    run_sql(db, "CREATE TABLE t (a INTEGER, b TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, NULL)")
    r = run_sql(db, "SELECT * FROM t")
    _, rows = parse_rows(r)
    assert rows == [["1", ""]]


def test_large_value_persists(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, val TEXT)")
    big = "Z" * 100_000
    run_sql(db, f"INSERT INTO t VALUES (1, '{big}')")
    r = run_sql(db, "SELECT val FROM t")
    assert_success(r)
    assert big in r.stdout


def test_transaction_rollback_does_not_persist(db):
    run_sql(db, "CREATE TABLE t (id INTEGER)")
    run_sql(db, "BEGIN")
    run_sql(db, "INSERT INTO t VALUES (99)")
    run_sql(db, "ROLLBACK")
    r = run_sql(db, "SELECT * FROM t")
    _, rows = parse_rows(r)
    assert rows == []


def test_new_db_file_is_empty(tmp_path):
    db = tmp_path / "brand_new.db"
    run_sql(db, "CREATE TABLE t (id INTEGER)")
    r = run_sql(db, "SELECT * FROM t")
    lines = r.stdout.strip().splitlines()
    assert lines == ["id"]
```

- [ ] **Step 2: Create test_corruption.py**

```python
"""Reliability: corrupt database file handling."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import run_sql


def test_corrupt_db_exits_nonzero(tmp_path):
    db = tmp_path / "corrupt.db"
    db.write_bytes(b"\x00\xff\xde\xad\xbe\xef" * 100)
    r = run_sql(db, "SELECT * FROM t")
    assert r.returncode != 0
    assert r.stderr.strip() != ""
    assert "Traceback" not in r.stderr


def test_truncated_db_exits_nonzero(tmp_path):
    db = tmp_path / "truncated.db"
    # Write partial content
    db.write_text("partial json {")
    r = run_sql(db, "SELECT * FROM t")
    assert r.returncode != 0
    assert "Traceback" not in r.stderr
```

---

### Task 11: Performance benchmarks

**Files:**
- Create: `harnesses/mini-sqlite/tests/performance/conftest.py`
- Create: `harnesses/mini-sqlite/tests/performance/bench_select_1k.py`
- Create: `harnesses/mini-sqlite/tests/performance/bench_insert_100.py`
- Create: `harnesses/mini-sqlite/tests/performance/bench_join_1k.py`
- Create: `harnesses/mini-sqlite/tests/performance/thresholds.json`

- [ ] **Step 1: Create thresholds.json**

```json
{
  "_comment": "Performance thresholds for mini-sqlite.",
  "_scoring": "Score = 100 if p95 <= target_p95. Score = 0 if p95 >= fail_p95. Linear interpolation between.",
  "benchmarks": {
    "select_1k_rows": {
      "file": "bench_select_1k.py",
      "description": "SELECT * FROM table with 1,000 rows",
      "target_p95_seconds": 2.0,
      "fail_p95_seconds": 10.0,
      "weight": 0.40
    },
    "insert_100_rows": {
      "file": "bench_insert_100.py",
      "description": "INSERT 100 rows sequentially",
      "target_p95_seconds": 5.0,
      "fail_p95_seconds": 30.0,
      "weight": 0.35
    },
    "join_1k_rows": {
      "file": "bench_join_1k.py",
      "description": "INNER JOIN on two tables with 1,000 rows each",
      "target_p95_seconds": 3.0,
      "fail_p95_seconds": 15.0,
      "weight": 0.25
    }
  }
}
```

- [ ] **Step 2: Create performance/conftest.py**

```python
"""Performance test helpers for mini-sqlite."""

import os
import shlex
import subprocess
import time
from pathlib import Path
import pytest


def run_sql_raw(db_path: Path, statement: str) -> subprocess.CompletedProcess:
    cmd_str = os.environ.get("MINI_SQLITE_CMD", "")
    if not cmd_str:
        pytest.skip("MINI_SQLITE_CMD not set")
    cmd = shlex.split(cmd_str)
    return subprocess.run(cmd + [str(db_path), statement], capture_output=True, text=True)


def time_sql(db_path: Path, statement: str, n: int = 5) -> dict:
    samples = []
    for _ in range(n):
        start = time.perf_counter()
        run_sql_raw(db_path, statement)
        samples.append(time.perf_counter() - start)
    samples.sort()
    def p(pct): return samples[min(int(len(samples) * pct / 100), len(samples) - 1)]
    return {"p50": p(50), "p95": p(95), "p99": p(99)}
```

- [ ] **Step 3: Create bench_select_1k.py**

```python
"""Performance: SELECT * from table with 1,000 rows."""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from conftest import run_sql_raw, time_sql


@pytest.fixture(scope="module")
def db_1k(tmp_path_factory):
    db = tmp_path_factory.mktemp("perf") / "bench.db"
    run_sql_raw(db, "CREATE TABLE t (id INTEGER, name TEXT, score REAL)")
    for i in range(1_000):
        run_sql_raw(db, f"INSERT INTO t VALUES ({i}, 'name{i}', {i * 0.5})")
    return db


def test_select_1k_p95_within_target(db_1k):
    stats = time_sql(db_1k, "SELECT * FROM t", n=5)
    print(f"\nselect 1k rows — p50={stats['p50']:.3f}s p95={stats['p95']:.3f}s p99={stats['p99']:.3f}s")
    assert stats["p95"] < 10.0
    if stats["p95"] > 2.0:
        pytest.xfail(f"p95 {stats['p95']:.2f}s exceeds target 2.0s")
```

- [ ] **Step 4: Create bench_insert_100.py**

```python
"""Performance: INSERT 100 rows sequentially (measures total wall time)."""

import time
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from conftest import run_sql_raw


def test_insert_100_p95_within_target(tmp_path):
    db = tmp_path / "bench.db"
    run_sql_raw(db, "CREATE TABLE t (id INTEGER, val TEXT)")

    samples = []
    for trial in range(3):
        # Fresh db each trial
        trial_db = tmp_path / f"bench_{trial}.db"
        run_sql_raw(trial_db, "CREATE TABLE t (id INTEGER, val TEXT)")
        start = time.perf_counter()
        for i in range(100):
            run_sql_raw(trial_db, f"INSERT INTO t VALUES ({i}, 'value{i}')")
        samples.append(time.perf_counter() - start)

    samples.sort()
    p95 = samples[min(int(len(samples) * 0.95), len(samples) - 1)]
    p50 = samples[len(samples) // 2]
    print(f"\ninsert 100 rows — p50={p50:.3f}s p95={p95:.3f}s p99={p95:.3f}s")
    assert p95 < 30.0
    if p95 > 5.0:
        pytest.xfail(f"p95 {p95:.2f}s exceeds target 5.0s")
```

- [ ] **Step 5: Create bench_join_1k.py**

```python
"""Performance: INNER JOIN on two 1,000-row tables."""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from conftest import run_sql_raw, time_sql


@pytest.fixture(scope="module")
def db_join(tmp_path_factory):
    db = tmp_path_factory.mktemp("perf") / "bench.db"
    run_sql_raw(db, "CREATE TABLE a (id INTEGER, val TEXT)")
    run_sql_raw(db, "CREATE TABLE b (id INTEGER, a_id INTEGER, extra TEXT)")
    for i in range(1_000):
        run_sql_raw(db, f"INSERT INTO a VALUES ({i}, 'val{i}')")
        run_sql_raw(db, f"INSERT INTO b VALUES ({i}, {i % 100}, 'extra{i}')")
    return db


def test_join_1k_p95_within_target(db_join):
    stmt = "SELECT a.val, b.extra FROM a INNER JOIN b ON a.id = b.a_id LIMIT 100"
    stats = time_sql(db_join, stmt, n=3)
    print(f"\njoin 1k rows — p50={stats['p50']:.3f}s p95={stats['p95']:.3f}s p99={stats['p99']:.3f}s")
    assert stats["p95"] < 15.0
    if stats["p95"] > 3.0:
        pytest.xfail(f"p95 {stats['p95']:.2f}s exceeds target 3.0s")
```

---

### Task 12: Update .gitignore and finalize

- [ ] **Step 1: Add held-out to .gitignore**

Add to `.gitignore`:
```
harnesses/mini-sqlite/tests/held-out/test_*.py
```

- [ ] **Step 2: Verify all tests collect**

Run: `python -m pytest harnesses/mini-sqlite/tests/tier1/ harnesses/mini-sqlite/tests/tier2/ harnesses/mini-sqlite/tests/tier3/ --collect-only -q 2>&1 | tail -5`
Expected: No collection errors, test items listed.

- [ ] **Step 3: Verify scorer unit tests still pass**

Run: `python -m pytest tests/ -v`
Expected: 6 tests pass.

- [ ] **Step 4: Final commit**

```bash
git add harnesses/mini-sqlite/ .gitignore
git commit -m "feat: complete mini-sqlite harness

Extension tests (16 index tests), reliability tests (7 scenarios),
performance benchmarks (3 benchmarks with thresholds.json),
and .gitignore entry for held-out tests."
```
