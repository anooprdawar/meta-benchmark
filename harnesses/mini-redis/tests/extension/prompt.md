# mini-redis Extension: Sorted Sets

The mini-redis implementation now needs to support Sorted Sets.

Add the following commands:

- `ZADD key score member [score member ...]` — add members with scores; print `(integer) N` (new members added; updating an existing member's score counts as 0)
- `ZRANGE key start stop` — list members by rank (ascending score), 0-indexed, negatives supported; print numbered list
- `ZRANK key member` — print `(integer) N` (0-based rank ascending) or `(nil)` if not found
- `ZSCORE key member` — print quoted score (e.g. `"1"` or `"1.5"`) or `(nil)` if not found
- `ZREM key member [member ...]` — remove members; print `(integer) N` removed

Rules:
- Scores are 64-bit floats
- Ties in score are broken lexicographically by member name
- ZRANGE does not support WITHSCORES (out of scope)
- Wrong type: exit 1, WRONGTYPE error

Write tests for the new functionality.
