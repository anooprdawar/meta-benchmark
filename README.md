# Meta-Benchmark

**A community standard for measuring AI coding agents on real software development.**

---

## The problem

AI coding agents have gotten dramatically better. But there's no rigorous way to measure it.

Current benchmarks (HumanEval, SWE-bench) measure narrow, atomic tasks designed for models, not agents. They operate at toy scale. They capture nothing developers actually care about: architectural coherence, code quality, knowing what to leave out, performance under load, reliability under failure.

Progress is felt, not measured. "GPT-4 is better at coding now" is a vibe, not a claim.

## The idea

This is the [CSS Zen Garden](https://csszengarden.com/) for AI coding agents.

A standardized application harness defines *what to build* — a fixed canvas. Agents build against it. Their output is scored on dimensions that actually matter. Results are public and reproducible.

> "gpt-5.4 built mini-git with 97% functional completeness, 88% adversarial survival, 100% mutation kill rate on its own tests, p95 latency under target on every benchmark, and 71% reliability — verified including private held-out tests not in this repo."

That's a precise, reproducible claim. You can verify it. You can compare it. You can beat it.

## Harnesses

Each harness is a complete build-from-scratch challenge. Agents receive a single prompt. No hints about the test suite, scoring rubric, or what dimensions are measured. They have to figure it out.

### mini-git

A from-scratch implementation of git — content-addressable object storage, staging index, branches, merges.

**Why mini-git?** The spec is git itself. Content-addressable storage (SHA1 blob/tree/commit objects) is non-trivial architecturally — it separates agents that *understand* git from agents that *fake* it.

| Tier | Commands | Tests |
|------|----------|-------|
| Tier 1 — Core | `init`, `add`, `commit`, `log`, `status` | 34 |
| Tier 2 — Branching | `branch`, `checkout`, `merge`, `diff` | 22 |
| Tier 3 — Advanced | merge conflicts, `reset`, `stash` | 16 |

Plus 155 adversarial edge cases, 16 extension tests, performance benchmarks, reliability chaos tests, and LLM judge scoring.

### mini-redis

A Redis-compatible key-value store — strings, lists, sets, sorted sets, hashes, TTL expiry, transactions, persistence.

**Why mini-redis?** Redis commands have precise, documented semantics. TTL expiry and transactions create real concurrency and correctness challenges. Persistence (JSON-backed) tests whether agents handle I/O properly.

| Tier | Commands | Tests |
|------|----------|-------|
| Tier 1 — Strings | `SET`, `GET`, `DEL`, `EXISTS`, `INCR`/`DECR`, `TTL`/`EXPIRE` | 17 |
| Tier 2 — Data structures | `LPUSH`/`RPUSH`/`LPOP`/`RPOP`/`LRANGE`, `SADD`/`SMEMBERS`/`SINTER`/`SUNION`, `HSET`/`HGET`/`HGETALL` | 23 |
| Tier 3 — Advanced | `ZADD`/`ZRANGE`/`ZRANGEBYSCORE`, `MULTI`/`EXEC`/`DISCARD`, `KEYS` glob, `PERSIST`, `RENAME` | 25 |

Plus 46 adversarial tests, 16 extension tests, 3 performance benchmarks, 8 reliability scenarios.

### mini-sqlite

A SQL database engine from scratch — parser, query executor, on-disk storage. `import sqlite3` is forbidden.

**Why mini-sqlite?** SQL parsing is genuinely hard. Agents must build a real query engine — tokenizer, parser, planner, executor, storage — all in one file. This is the hardest harness so far.

| Tier | Features | Tests |
|------|----------|-------|
| Tier 1 — Core | `CREATE TABLE`, `INSERT`, `SELECT`, `DELETE`, `DROP TABLE` | 21 |
| Tier 2 — Queries | `WHERE`, `UPDATE`, `ORDER BY`, `LIMIT`/`OFFSET`, operators | 23 |
| Tier 3 — Advanced | `JOIN`, `GROUP BY`/`HAVING`, aggregates, `BEGIN`/`COMMIT`/`ROLLBACK` | 21 |

Plus 30 adversarial tests, 16 extension tests, 3 performance benchmarks, 7 reliability scenarios.

## Scoring

Seven dimensions, all automated. Same framework across all harnesses:

| Dimension | Weight | How |
|-----------|--------|-----|
| Functional completeness | 35% | Behavioral tests across 3 tiers (pytest, black-box) |
| Adversarial survival | 18% | Public + private held-out edge cases |
| Extension readiness | 12% | Second-prompt round: agent adds new features. 16 tests. |
| Mutation kill rate | 0%* | Does the agent's own test suite catch code mutations? (mutmut) |
| Performance | 15% | Latency benchmarks with defined thresholds |
| Reliability | 10% | Crash recovery, concurrent writes, disk-full, corruption |
| Code quality | 10% | Multi-model LLM judge, calibrated against human expert scores |

*Mutation is scored when available but currently weighted at 0% — it's tracked for analysis but doesn't affect the total.

When a dimension is not applicable (e.g. extension tests timeout), its weight is redistributed proportionally across functional, adversarial, and extension — keeping scores on a consistent 0-100 scale.

**Output:** A structured JSON scorecard + human-readable report. All runs are public.

## Results

Single runs, not best-of-N. Scores from `scorecard.json` files in `submissions/`. The leaderboard (`leaderboard/data/runs.json`) is the canonical source for mini-git scores; mini-redis and mini-sqlite scores are from individual submission scorecards and will be added to the leaderboard as we stabilize the pipeline.

### mini-git

| Model | Score | Functional | Adversarial | Extension | Performance | Quality | Cost |
|-------|-------|-----------|-------------|-----------|-------------|---------|------|
| gemini-2.5-pro | **79.86** | 70/72 (97%) | 146/166 (88%) | 4/16 | 100 | 37.3 | $0.14 |
| gpt-5.4 | **79.32** | 70/72 (97%) | 146/166 (88%) | 4/16 | 100 | 60.5 | $0.15 |
| gpt-5.3-codex | **78.73** | 70/72 (97%) | 146/166 (88%) | 4/16 | 100 | 26.0 | $0.04 |
| claude-opus-4-6 | **76.13** | 70/72 (97%) | 146/166 (88%) | 4/16 | 100 | — | $1.40 |

claude-opus-4-6 quality is `—` because that run used `dry_run=True` for the LLM judge. A separate non-dry-run submission scored 72.8 quality but with a different total (73.64). We don't mix numbers across runs.

### mini-redis

| Model | Score | Functional | Adversarial | Reliability | Quality | Cost |
|-------|-------|-----------|-------------|-------------|---------|------|
| claude-opus-4-6 | **82.45** | 65/65 (100%) | 46/46 (100%) | 7/8 (88%) | 55.2 | ~$1.00 |
| gpt-5.4 | **81.46** | 60/65 (92%) | 46/46 (100%) | 8/8 (100%) | 60.3 | ~$0.15 |
| gemini-2.5-pro | **80.53** | 59/65 (91%) | 45/46 (98%) | 8/8 (100%) | 61.9 | ~$0.12 |

### mini-sqlite

| Model | Score | Functional | Adversarial | Reliability | Quality | Cost |
|-------|-------|-----------|-------------|-------------|---------|------|
| claude-opus-4-6 | **74.31** | 56/65 (86%) | 25/30 (83%) | 5/7 (71%) | 58.6 | ~$1.00 |
| gpt-5.4 | **69.76** | 50/65 (77%) | 24/30 (80%) | 5/7 (71%) | 49.0 | ~$0.15 |
| gemini-2.5-pro | **68.17** | 46/65 (71%) | 21/30 (70%) | 6/7 (86%) | 53.5 | ~$0.12 |

### Cross-harness average

| Model | mini-git | mini-redis | mini-sqlite | Average |
|-------|----------|-----------|-------------|---------|
| claude-opus-4-6 | 76.13 | 82.45 | 74.31 | **77.63** |
| gpt-5.4 | 79.32 | 81.46 | 69.76 | **76.85** |
| gemini-2.5-pro | 79.86 | 80.53 | 68.17 | **76.19** |

All three frontier models are within ~1.5 points of each other on average. The ranking changes by harness — there's no single winner. mini-sqlite (the hardest harness) shows the widest spread. All models hit 0/16 on extension tests across mini-redis and mini-sqlite — second-prompt adaptability remains an open problem.

## Architecture

```
meta-benchmark/
  harnesses/
    mini-git/              ← Git implementation challenge
    mini-redis/            ← Redis key-value store challenge
    mini-sqlite/           ← SQL database engine challenge
    your-harness/          ← Add your own (see "Adding a harness" below)
      spec.md              ← Full PRD: what to build
      prompt.md            ← The single seed prompt the agent receives
      rubric.md            ← Scoring dimensions and weights
      tests/
        tier1/             ← Core functionality tests
        tier2/             ← Intermediate feature tests
        tier3/             ← Advanced feature tests
        adversarial/       ← Edge cases and abuse scenarios
        held-out/          ← Gitignored, maintainer-only (anti-Goodhart)
        extension/         ← Second-prompt feature addition tests
        performance/       ← Latency benchmarks with thresholds
        reliability/       ← Crash, corruption, concurrency scenarios
      judge/
        rubric.md          ← LLM judge qualitative rubric
        calibration/       ← Human-scored reference implementations
  runner/
    cli.py                 ← benchmark run / score / list-harnesses
    agents/
      anthropic_api.py     ← Anthropic API (claude-opus-4-6, sonnet, etc.)
      gemini_api.py        ← Gemini API (gemini-2.5-pro, flash, etc.)
      openai_api.py        ← OpenAI API (gpt-5.4, gpt-5.3-codex, etc.)
      claude_code.py       ← Claude Code subprocess integration
      README.md            ← Manual submission format
  scorer/
    behavioral.py          ← Tier 1-3 behavioral tests
    adversarial.py         ← Public + held-out edge cases
    extension.py           ← Second-prompt feature tests
    mutation.py            ← Mutation testing via mutmut
    performance.py         ← Latency benchmarks
    reliability.py         ← Chaos scenarios
    judge.py               ← Multi-model LLM judge
    scorecard.py           ← Aggregates everything -> JSON
  leaderboard/
    index.html             ← Static leaderboard site (no build step)
    data/runs.json         ← All public runs
  tests/                   ← Scorer infrastructure unit tests
  submissions/             ← Agent outputs + scorecards (gitignored)
```

## Quickstart

```bash
git clone https://github.com/anoopdawar/meta-benchmark
cd meta-benchmark

# Core install (scoring infrastructure + pytest)
pip install -e .

# Add the agents you want to use
pip install -e ".[anthropic]"    # Claude models
pip install -e ".[openai]"      # GPT models
pip install -e ".[gemini]"      # Gemini models
pip install -e ".[all]"         # everything

# See available harnesses
python -m runner.cli list-harnesses

# Run a fresh benchmark (requires API key)
python -m runner.cli run --harness mini-redis --agent claude-api --model claude-opus-4-6

# Score it
python -m runner.cli score --submission submissions/mini-redis-<timestamp> --harness mini-redis
```

See [TESTING.md](TESTING.md) for a complete step-by-step walkthrough.

## API keys

Each agent checks for a `*_META_BENCHMARK_KEY` env var first, then falls back to the standard key:

| Provider | Primary env var | Fallback | Where to get it |
|----------|----------------|----------|-----------------|
| Anthropic | `ANTHROPIC_META_BENCHMARK_KEY` | `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |
| Google | `GEMINI_META_BENCHMARK_KEY` | `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) |
| OpenAI | `OPENAI_META_BENCHMARK_KEY` | `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) |

> **Note:** The `ANTHROPIC_API_KEY` in a Claude Code session is an internal session token. It returns 401 for direct API calls. You need a separate key from the Anthropic console.

## Anti-Goodhart measures

Benchmarks rot when they become training targets. These countermeasures are implemented today, not planned.

**1. Private held-out tests**

Every harness has a `tests/held-out/` directory that is gitignored. It never appears in the public repo. The scorer finds it automatically — if it exists, those tests run and count toward the adversarial score. Leaderboard entries scored with held-out tests are marked `verified: true` in the scorecard JSON.

**2. Harness versioning**

Each harness has a `harness_version` field. When requirements change, the version increments and old scores are not comparable. Currently all harnesses at v1.0.0.

**3. Harness velocity**

One harness is a benchmark. Ten harnesses is a standard. Three harnesses cover very different domains (version control, key-value stores, SQL engines). The community adds harnesses faster than models can be tuned against any one of them.

## Adding a harness

We added mini-redis and mini-sqlite because mini-git alone was one data point. Different harnesses stress different capabilities: mini-redis tests data structure correctness and TTL semantics; mini-sqlite tests parsing, query planning, and on-disk storage. More harnesses = harder to game, more signal.

A harness is a directory under `harnesses/` with this structure:

```
harnesses/your-harness/
  spec.md              ← Full PRD with version number
  prompt.md            ← The exact prompt agents receive (one file, no hints about tests)
  rubric.md            ← Scoring weights (must use the 7-dimension framework)
  tests/
    conftest.py        ← Fixtures: discover the submission via YOUR_HARNESS_CMD env var
    tier1/             ← Core features (easiest)
    tier2/             ← Intermediate features
    tier3/             ← Advanced features
    adversarial/       ← Edge cases, malformed input, abuse
    extension/         ← Second-prompt feature addition (16 tests recommended)
    performance/       ← Latency benchmarks with pass/fail thresholds
    reliability/       ← Crash recovery, concurrency, corruption
    pytest.ini         ← timeout and markers config
  judge/
    rubric.md          ← LLM judge rubric (what "good code" means for this domain)
    calibration/       ← Reference implementations with known scores
```

### What makes a good harness

The pattern: **non-trivial, well-specified, deterministically testable**.

- The spec must be precise enough that "correct" is unambiguous. Redis commands have exact semantics. SQL has a grammar. Git has content-addressable objects. Vague specs produce vague scores.
- The challenge must require architecture, not just string manipulation. Good harnesses have multiple interacting subsystems (parser + executor + storage, or networking + persistence + data structures).
- Tests must be black-box. They invoke the submission as a CLI subprocess — they never import the agent's code. This means any language could work (though we currently target Python).
- Aim for 60-70 behavioral tests across three tiers, 30-50 adversarial tests, and 16 extension tests.

### How the scorer discovers submissions

The `conftest.py` in each harness discovers the submission via an environment variable:

- `MINI_GIT_CMD` for mini-git
- `MINI_REDIS_CMD` for mini-redis
- `MINI_SQLITE_CMD` for mini-sqlite

The scorer sets this automatically when scoring. For manual testing: `export MINI_REDIS_CMD="python path/to/mini_redis.py"`.

### Candidates for new harnesses

- A compiler for a simple language (tokenizer + parser + codegen)
- A job queue with retry logic and dead-letter handling
- A diff/patch tool (line-level and word-level)
- A CSV query engine with joins and aggregates
- An HTTP/1.1 server with routing and middleware

## Submitting a run

Any agent, any framework. If you can produce code, you can submit.

```bash
# Via the CLI runner
python -m runner.cli run --harness mini-redis --agent openai-api --model gpt-5.4
python -m runner.cli score --submission submissions/<run-dir> --harness mini-redis

# Manual submission (Cursor, Devin, Copilot, raw API, etc.)
# -> See runner/agents/README.md for the metadata.json format
```

To add your run to the public leaderboard, open a PR adding your `metadata.json` and `scorecard.json` under `submissions/<your-run>/`.

## The leaderboard

```bash
cd leaderboard && python -m http.server 8080
# open http://localhost:8080
```

Sortable by any dimension. Filter by model, framework, and harness version. Drill into any run for the full scorecard.

---

*Built to be forked, extended, and argued about. The goal is a common canvas — one place where "this model is better at coding" becomes a falsifiable claim.*
