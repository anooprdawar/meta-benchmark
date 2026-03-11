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
