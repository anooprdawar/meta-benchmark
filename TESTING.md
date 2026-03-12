# Testing Guide

Everything you need to try the benchmark, step by step.

---

## One-time setup

```bash
git clone https://github.com/anoopdawar/meta-benchmark
cd meta-benchmark

# Core install (scoring infrastructure + pytest)
pip install -e .

# Add the agents you need
pip install -e ".[anthropic]"    # for Claude models
pip install -e ".[openai]"      # for GPT models
pip install -e ".[gemini]"      # for Gemini models
pip install -e ".[all]"         # everything including mutmut
```

Check it works:

```bash
python -m runner.cli list-harnesses
# Available harnesses (3):
#   mini-git     Mini-Git: Product Requirements Document
#   mini-redis   mini-redis: Product Requirements Document
#   mini-sqlite  mini-sqlite: Product Requirements Document
```

---

## Step 1: Read what agents receive

Each harness has a single prompt file — the *only* thing the agent sees. No hints about tests, scoring, or dimensions.

```bash
cat harnesses/mini-git/prompt.md
cat harnesses/mini-redis/prompt.md
cat harnesses/mini-sqlite/prompt.md
```

---

## Step 2: Run a benchmark

Pick a harness, pick a model. The CLI creates a submission directory, calls the API, and writes the generated code.

```bash
# Anthropic
python -m runner.cli run --harness mini-redis --agent claude-api --model claude-opus-4-6

# Google
python -m runner.cli run --harness mini-redis --agent gemini-api --model gemini-2.5-pro

# OpenAI
python -m runner.cli run --harness mini-redis --agent openai-api --model gpt-5.4
```

Output:

```
Running harness 'mini-redis' with agent 'claude-api' (model: claude-opus-4-6)
Workspace: submissions/mini-redis-claude-opus-4-6-20260311T225723Z/workspace
  Calling claude-opus-4-6 via Anthropic API (streaming)...
  API call complete in 87.2s
  Files written: 2
    mini_redis.py
    test_mini_redis.py

Submission created: submissions/mini-redis-claude-opus-4-6-20260311T225723Z
Duration: 87.6s
Tokens: 1,024 in / 11,832 out
Est. cost: $0.93
```

---

## Step 3: Score the submission

```bash
python -m runner.cli score \
  --submission submissions/mini-redis-claude-opus-4-6-20260311T225723Z \
  --harness mini-redis
```

Output:

```
Scoring submission: submissions/mini-redis-claude-opus-4-6-20260311T225723Z

Running behavioral tests...
  Functional: 100.0/100 (65/65 tests)
Running adversarial tests...
  Adversarial: 100.0/100 (46/46 survived)
Running extension tests...
  Extension: 0.0/100 (0/16) [static]
Running mutation testing...
  Mutation: 0.0/100 (unavailable)
Running performance benchmarks...
  Performance: 100.0/100
Running reliability tests...
  Reliability: 87.5/100 (7/8)
Running LLM judge...
  Quality: 55.3/100

Total score: 82.5/100
```

The scorecard is written to `submissions/<run>/scorecard.json`.

> **Weight redistribution:** When a dimension can't be scored (e.g. mutation requires test files the agent didn't write), its weight is redistributed proportionally across functional, adversarial, and extension. Scores stay on a consistent 0-100 scale.

---

## Step 4: Run harness tests manually

You can run any harness's test suite directly against a submission:

```bash
# Set the command env var for the harness you're testing
export MINI_REDIS_CMD="python submissions/mini-redis-claude-opus-4-6-20260311T225723Z/workspace/mini_redis.py"

# Run by tier
python -m pytest harnesses/mini-redis/tests/tier1/ -v
python -m pytest harnesses/mini-redis/tests/tier2/ -v
python -m pytest harnesses/mini-redis/tests/tier3/ -v

# Run adversarial tests
python -m pytest harnesses/mini-redis/tests/adversarial/ -v --tb=short

# Run everything
python -m pytest harnesses/mini-redis/tests/ -q
```

The env var pattern is `MINI_<HARNESS>_CMD` with the harness name uppercased and hyphens replaced with underscores:

| Harness | Env var | Example |
|---------|---------|---------|
| mini-git | `MINI_GIT_CMD` | `python path/to/mini_git.py` |
| mini-redis | `MINI_REDIS_CMD` | `python path/to/mini_redis.py` |
| mini-sqlite | `MINI_SQLITE_CMD` | `python path/to/mini_sqlite.py` |

---

## Step 5: Verify scorer infrastructure

The `tests/` directory at the project root contains unit tests for the scoring infrastructure itself — not the harness tests.

```bash
python -m pytest tests/ -v
```

Expected: 6 tests pass covering:
- `_extract_timing`: performance benchmark output parser handles all print formats
- `_redistribute_na_weight`: N/A dimension weight redistribution is proportional and sums to 1.0

---

## Step 6: Understand the held-out tests

Each harness has a `tests/held-out/` directory that is **gitignored** — it never appears in the public repo. The scorer finds it automatically and includes those tests in the adversarial score.

Entries scored with held-out tests are marked `"verified": true` in the scorecard JSON.

To add your own held-out tests: create `harnesses/<harness>/tests/held-out/test_*.py` following the same conftest pattern. They run automatically next time you score.

---

## Step 7: Score a manual submission

Output from Cursor, Copilot, Devin, a raw API call, anything:

```bash
mkdir -p submissions/my-run/workspace

# Copy the generated code
cp /path/to/generated/mini_redis.py submissions/my-run/workspace/

# Write metadata
cat > submissions/my-run/metadata.json << 'EOF'
{
  "model": "gpt-4o",
  "agent_framework": "cursor",
  "agent_framework_version": "0.43.0",
  "scaffolding_config": {},
  "date": "2026-03-11T14:23:00Z",
  "harness": "mini-redis",
  "harness_version": "1.0.0",
  "wall_clock_seconds": 1200,
  "tokens_input": 50000,
  "tokens_output": 15000,
  "cost_usd": 3.50,
  "notes": ""
}
EOF

# Score it
python -m runner.cli score \
  --submission submissions/my-run \
  --harness mini-redis
```

---

## Test categories by harness

### mini-git (72 behavioral + 155 adversarial)

| Category | Tests | What it covers |
|----------|-------|----------------|
| tier1 | 34 | init, add, commit, log, status |
| tier2 | 22 | branch, checkout, merge, diff |
| tier3 | 16 | merge conflicts, reset, stash |
| adversarial | 155 | unicode filenames, binary files, corrupt objects, 100k+ files |
| extension | 16 | tag support (tag, tag -d, listing, log annotations) |
| performance | 3 | 10k commits, 100k files, 1k diffs |
| reliability | 14 | SIGKILL mid-commit, concurrent writes, disk full, corrupt store |

### mini-redis (65 behavioral + 46 adversarial)

| Category | Tests | What it covers |
|----------|-------|----------------|
| tier1 | 17 | SET/GET/DEL, EXISTS, INCR/DECR, TTL/EXPIRE |
| tier2 | 23 | LPUSH/RPUSH/LPOP/RPOP/LRANGE, SADD/SMEMBERS/SINTER/SUNION, HSET/HGET/HGETALL |
| tier3 | 25 | ZADD/ZRANGE/ZRANGEBYSCORE, MULTI/EXEC/DISCARD, KEYS glob, PERSIST, RENAME |
| adversarial | 46 | binary-safe keys, massive values, TTL races, type confusion |
| extension | 16 | pub/sub, Lua-like scripting, or persistence snapshots |
| performance | 3 | bulk inserts, large list operations, sorted set queries |
| reliability | 8 | crash recovery, persistence corruption, concurrent access |

### mini-sqlite (65 behavioral + 30 adversarial)

| Category | Tests | What it covers |
|----------|-------|----------------|
| tier1 | 21 | CREATE TABLE, INSERT, SELECT, DELETE, DROP TABLE |
| tier2 | 23 | WHERE, UPDATE, ORDER BY, LIMIT/OFFSET, operators |
| tier3 | 21 | JOIN, GROUP BY/HAVING, aggregates, BEGIN/COMMIT/ROLLBACK |
| adversarial | 30 | SQL injection attempts, NULL semantics, type coercion, empty tables |
| extension | 16 | subqueries, CREATE INDEX, ALTER TABLE |
| performance | 3 | bulk inserts, large table scans, join performance |
| reliability | 7 | crash during transaction, corrupt database file, concurrent writes |

---

## Troubleshooting

**`benchmark: command not found`**
```bash
pip install -e .
# or use: python -m runner.cli
```

**Tests all skipping**
```bash
echo $MINI_REDIS_CMD              # must be set
python $MINI_REDIS_CMD SET x 1    # verify it runs
```

**`--timeout` unrecognized**
```bash
pip install pytest-timeout
```

**`--json-report` unrecognized**
```bash
pip install pytest-json-report
```

**Mutation always 0 / `mutmut: command not found`**
```bash
pip install "mutmut<3"   # mutmut 3.x has a different API; use 2.x
```

**`google-genai` import error**
```bash
pip install google-genai
```

**Anthropic 401**
The `ANTHROPIC_API_KEY` from Claude Code is a session token, not an API key. Get a real key at [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys). Or set `ANTHROPIC_META_BENCHMARK_KEY` which is checked first.

**Gemini 429 quota exceeded**
`gemini-2.5-pro` requires a paid tier. Switch to `gemini-2.5-flash`:
```bash
python -m runner.cli run --harness mini-redis --agent gemini-api --model gemini-2.5-flash
```

**Scorer shows 0 behavioral tests**
Run from the project root, not a subdirectory:
```bash
cd meta-benchmark
python -m runner.cli score --submission submissions/my-run --harness mini-redis
```

**Leaderboard shows "Failed to load data"**
Must be served via HTTP:
```bash
cd leaderboard && python -m http.server 8080
# open http://localhost:8080  (not file:///...)
```

---

## Score interpretation

| Score | What it means |
|-------|---------------|
| 85-100 | Near-perfect. All tiers, adversarial handled, extends cleanly, fast and reliable. |
| 70-85 | Strong. Core solid, most edge cases handled, good performance. |
| 55-70 | Competent. All commands present, some correctness or quality gaps. |
| 30-55 | Partial. Tier 1 works, Tier 2 rough, Tier 3 gaps. |
| < 30 | Broken. Core implementation bug stops most tests. |

From scored runs: frontier models score 68-83 depending on harness difficulty. mini-git clusters at 76-80, mini-redis at 80-83, mini-sqlite at 68-75. The spread within a harness is typically 4-6 points between the top and bottom frontier model.
