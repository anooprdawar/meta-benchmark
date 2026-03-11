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
