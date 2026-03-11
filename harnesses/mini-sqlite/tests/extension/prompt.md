# mini-sqlite Extension: Indexes

The mini-sqlite implementation now needs to support indexes.

Add the following:

- `CREATE INDEX name ON table(col)` — creates an index on a column; print `OK`
- `EXPLAIN query` — shows the query plan; when a query uses an index, output must contain the word `index` (case-insensitive); when no index would be used, output must NOT contain the word `index`

The EXPLAIN output format is up to you — a simple one-line description is fine.

Write tests for the new functionality.
