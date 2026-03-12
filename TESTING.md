# Testing Guide

Everything you need to try the benchmark, step by step.

---

## One-time setup

```bash
git clone https://github.com/anoopdawar/meta-benchmark
cd meta-benchmark

# Install everything (the benchmark, test tools, and all model SDKs)
pip install -e ".[all]"
```

This installs:
- The `benchmark` CLI tool
- pytest + plugins (for running the test suites)
- The Anthropic, OpenAI, and Google Gemini Python SDKs (for calling model APIs)
- mutmut (for mutation testing)

If you only want to score existing submissions and never call a model API, the base install is enough:

```bash
pip install -e .
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

## Step 1: Set your API keys

You need keys for whichever model providers you want to benchmark. Set them as environment variables:

```bash
# Anthropic (for Claude models) — get one at console.anthropic.com
export ANTHROPIC_META_BENCHMARK_KEY=sk-ant-...

# OpenAI (for GPT models) — get one at platform.openai.com
export OPENAI_META_BENCHMARK_KEY=sk-proj-...

# Google (for Gemini models) — get one at aistudio.google.com
export GEMINI_META_BENCHMARK_KEY=AIza...
```

You don't need all three. If you only have an Anthropic key, you can only benchmark Claude models — that's fine.

> **Note:** If you're running this inside Claude Code, the `ANTHROPIC_API_KEY` that's already set is a session token — it won't work for direct API calls. You need a separate key from the Anthropic console.

---

## Step 2: Read what agents receive

Each harness has a single prompt file — the *only* thing the agent sees. No hints about tests, scoring, or dimensions.

```bash
cat harnesses/mini-git/prompt.md
cat harnesses/mini-redis/prompt.md
cat harnesses/mini-sqlite/prompt.md
```

---

## Step 3: Run a benchmark

Pick a harness, pick a model. The CLI calls the model API, gets back generated code, and saves it.

```bash
# Have Claude build a Redis implementation from scratch
python -m runner.cli run --harness mini-redis --agent claude-api --model claude-opus-4-6

# Have GPT do the same
python -m runner.cli run --harness mini-redis --agent openai-api --model gpt-5.4

# Have Gemini do the same
python -m runner.cli run --harness mini-redis --agent gemini-api --model gemini-2.5-pro
```

This takes 1-3 minutes per model. Output looks like:

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

The generated code is in `submissions/<run>/workspace/`.

---

## Step 4: Score the submission

Run the full test suite against the generated code:

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

Scoring calls three LLM judges (one per provider: Claude, GPT, Gemini) to evaluate code quality. This costs a few cents per run. If you don't have all three API keys, the judge uses whichever providers are available.

> **Weight redistribution:** When a dimension can't be scored (e.g. mutation requires test files the agent didn't write), its weight is redistributed proportionally across functional, adversarial, and extension. Scores stay on a consistent 0-100 scale.

---

## Step 5: Run tests manually (optional)

You can run any part of the test suite directly against a submission, outside the scorer:

```bash
# Tell the test suite where the implementation is (use an absolute path)
export MINI_REDIS_CMD="python /full/path/to/submissions/mini-redis-.../workspace/mini_redis.py"

# Run just the core tests
python -m pytest harnesses/mini-redis/tests/tier1/ -v

# Run adversarial edge cases
python -m pytest harnesses/mini-redis/tests/adversarial/ -v --tb=short

# Run everything
python -m pytest harnesses/mini-redis/tests/ -q
```

Each harness uses its own env var:

| Harness | Env var |
|---------|---------|
| mini-git | `MINI_GIT_CMD` |
| mini-redis | `MINI_REDIS_CMD` |
| mini-sqlite | `MINI_SQLITE_CMD` |

---

## Step 6: Verify the scoring infrastructure itself

The `tests/` directory at the project root has unit tests for the scorer (not for the harnesses):

```bash
python -m pytest tests/ -v
```

Expected: 6 tests pass. These verify the performance parser and weight redistribution logic.

---

## Step 7: Score someone else's code

You can score code from any source — Cursor, Copilot, Devin, hand-written, whatever:

```bash
# Create the submission structure
mkdir -p submissions/my-run/workspace

# Put the generated code there
cp /path/to/their/mini_redis.py submissions/my-run/workspace/

# Create a metadata file (fill in what you know)
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
The env var isn't set or the path is wrong:
```bash
echo $MINI_REDIS_CMD              # should print the command
python $MINI_REDIS_CMD SET x 1    # should print "OK"
```

**`--timeout` or `--json-report` unrecognized**
You didn't install with extras. Run:
```bash
pip install -e ".[all]"
```

**`google-genai` / `anthropic` / `openai` import error**
Same fix — install with extras:
```bash
pip install -e ".[all]"
```

**Anthropic 401 error**
The `ANTHROPIC_API_KEY` from a Claude Code session is a session token, not a real API key. Get one at [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) and set it as `ANTHROPIC_META_BENCHMARK_KEY`.

**Gemini 429 quota exceeded**
`gemini-2.5-pro` requires a paid tier on Google AI Studio.

**Scorer shows 0 behavioral tests**
Run from the project root:
```bash
cd meta-benchmark
python -m runner.cli score --submission submissions/my-run --harness mini-redis
```

**Leaderboard shows "Failed to load data"**
The leaderboard HTML must be served over HTTP, not opened as a file:
```bash
cd leaderboard && python -m http.server 8080
# open http://localhost:8080
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
