# Testing Guide

Everything you need to try the benchmark, step by step. No prior knowledge required.

---

## One-time setup

```bash
git clone https://github.com/anoopdawar/meta-benchmark
cd meta-benchmark

pip install -e .
pip install pytest pytest-timeout pytest-json-report "mutmut<3"
```

Check it works:

```bash
python -m runner.cli list-harnesses
# Available harnesses (1):
#   mini-git   Mini-Git: Product Requirements Document
```

---

## Step 1: Read the prompt agents receive

```bash
cat harnesses/mini-git/prompt.md
```

This is the *exact* prompt. One page. No hints about the test suite or scoring. From this single prompt, agents must produce a working git implementation.

---

## Step 2: Run the test suite against the included Claude submission

A real Claude-generated mini-git lives in `submissions/`. Run the harness tests against it:

```bash
export MINI_GIT_CMD="python submissions/mini-git-claude-opus-4-6-live/workspace/mini_git.py"

python -m pytest harnesses/mini-git/tests/tier1/ -v   # init, add, commit, log, status
python -m pytest harnesses/mini-git/tests/tier2/ -v   # branch, checkout, merge, diff
python -m pytest harnesses/mini-git/tests/tier3/ -v   # conflicts, reset, stash
```

Expected: ~70 of 72 behavioral tests pass. The implementation is real — it uses SHA1 object storage, zlib compression, and a proper staging index.

---

## Step 3: Score the submission

Run all 7 scoring dimensions at once:

```bash
python -m scorer.scorecard \
  --submission submissions/mini-git-claude-opus-4-6-live \
  --harness mini-git \
  --dry-run
```

`--dry-run` skips the LLM judge API call. You'll see output like:

```
Running behavioral tests...
  Functional: 96.8/100 (70/72 tests)
Running adversarial tests...
  [held-out] 10/11 additional adversarial tests passed
  Adversarial: 88.0/100 (146/166 survived)
Running extension tests...
  Extension: 25.0/100 (4/16)
Running mutation testing...
  Mutation: 100.0/100 (mutmut)
Running performance benchmarks...
  Performance: 35.4/100
Running reliability tests...
  Reliability: 71.4/100 (10/14)
Running LLM judge...
  Quality: 0.0/100 (dry_run=True)

Total score: 76.1/100
```

> **Note on N/A weight redistribution:** When a dimension can't be scored (e.g. mutation testing requires the agent to have produced test files), its weight is redistributed proportionally to functional, adversarial, and extension. This keeps scores on a comparable 0–100 scale across runs where different dimensions apply.

Remove `--dry-run` to run the LLM judge too (quality: ~72.8/100). Dry-run entries show `—` in the leaderboard Quality column — distinguishable from a genuine 0 quality score.

---

## Step 3b: Verify scorer integrity

The `tests/` directory at the project root contains unit tests for the scoring infrastructure itself — not the harness tests. Run them to confirm the scorer is working correctly:

```bash
python -m pytest tests/ -v
```

Expected: 6 tests pass covering:
- `_extract_timing`: verifies the performance benchmark output parser handles all four print formats
- `_redistribute_na_weight`: verifies N/A dimension weight redistribution is proportional (not equal-split) and always sums to 1.0

---

## Step 4: Understand the held-out tests

You'll notice `[held-out] 10/11 additional adversarial tests passed` in the output above. This is the private test mechanism working.

`harnesses/mini-git/tests/held-out/` is **gitignored** — it doesn't appear in the public repo. But the directory exists in your local clone after you run the setup. The scorer finds it automatically and includes those tests in the adversarial score.

Entries scored with held-out tests are marked `"verified": true` in the scorecard JSON:

```bash
python -m json.tool submissions/mini-git-claude-opus-4-6-live/scorecard.json \
  | grep -A5 '"adversarial"'
# "verified": true,
# "held_out_passed": 10,
# "held_out_total": 11,
```

To add your own held-out tests: create `harnesses/mini-git/tests/held-out/test_*.py`. They run automatically next time you score.

---

## Step 5: Check mutation testing

The mutation scorer runs `mutmut` against the agent's own test files. It asks: do the agent's tests actually catch bugs?

```bash
# See mutmut run standalone
cd submissions/mini-git-claude-opus-4-6-live/workspace
cat > setup.cfg << 'EOF'
[mutmut]
paths_to_mutate=mini_git.py
tests_dir=.
EOF
mutmut run
# then check: mutants/mini_git.py.meta
```

The scorer does this automatically — the 100% kill rate in Step 3 means every mutant was caught.

---

## Step 6: Open the leaderboard

```bash
cd leaderboard && python -m http.server 8080
# open http://localhost:8080
```

> Must be served via HTTP — opening the HTML file directly won't load the data.

Click any row to drill into the full scorecard: tier breakdown, adversarial survival detail, performance latency per benchmark, and judge dimension scores.

---

## Step 7: Run a fresh benchmark against a model

This calls the model API, has it generate a mini-git implementation from scratch, scores it, and updates the leaderboard.

### Anthropic (Claude):

```bash
# Real key from console.anthropic.com/settings/keys
export ANTHROPIC_API_KEY=sk-ant-...

python run_benchmark.py --models claude-opus-4-6 --dry-run
```

> The `ANTHROPIC_API_KEY` inside a Claude Code session is a session token — it returns 401 for direct API calls. You need a separate key from the console.

### Google (Gemini):

```bash
pip install google-genai
export GEMINI_API_KEY=...   # aistudio.google.com → Get API key

python run_benchmark.py --models gemini-2.5-pro --dry-run
```

> `gemini-2.5-pro` requires a paid tier. `gemini-2.5-flash` works on the free tier but scores much lower.

### OpenAI:

```bash
export OPENAI_META_BENCHMARK_KEY=sk-proj-...   # platform.openai.com → API Keys

python run_benchmark.py --models gpt-5.4 --dry-run
# or the dedicated coding model:
python run_benchmark.py --models gpt-5.3-codex --dry-run
```

### What happens:

1. A workspace is created under `submissions/`
2. The model receives `harnesses/mini-git/prompt.md` — nothing else
3. The model generates code (~3–6 min for Claude opus, ~5 min for Gemini flash)
4. All 7 scorers run against the output
5. Results written to `submissions/<run>/scorecard.json`
6. `leaderboard/data/runs.json` updated automatically

Remove `--dry-run` to also run the LLM judge (costs a small amount per run).

---

## Step 8: Score a manual submission

Output from Cursor, Copilot, Devin, a raw API call, anything:

```bash
mkdir -p submissions/my-run/workspace

# Copy the generated code
cp -r /path/to/generated/code/* submissions/my-run/workspace/

# Write metadata
cat > submissions/my-run/metadata.json << 'EOF'
{
  "model": "gpt-4o",
  "agent_framework": "cursor",
  "agent_framework_version": "0.43.0",
  "scaffolding_config": {},
  "date": "2026-03-10T14:23:00Z",
  "harness": "mini-git",
  "harness_version": "1.0.0",
  "wall_clock_seconds": 1200,
  "tokens_input": 50000,
  "tokens_output": 15000,
  "cost_usd": 3.50,
  "notes": ""
}
EOF

# Score it
python -m scorer.scorecard \
  --submission submissions/my-run \
  --harness mini-git \
  --dry-run
```

The scorer discovers the implementation at `workspace/mini_git.py`, `workspace/mini_git/__main__.py`, or `workspace/src/mini_git.py`.

---

## Run any test category standalone

```bash
export MINI_GIT_CMD="python /path/to/mini_git.py"

# Adversarial: unicode filenames, binary files, corrupt objects, 100k+ files
python -m pytest harnesses/mini-git/tests/adversarial/ -v --tb=short

# Extension: second-prompt tag support (tag, tag -d, log annotations)
python -m pytest harnesses/mini-git/tests/extension/ -v --tb=short

# Reliability: mid-commit kill, concurrent writes, disk full, corrupt store
python -m pytest harnesses/mini-git/tests/reliability/ -v --tb=short

# Performance benchmarks: 10k commits, 100k files, 1k diffs
python -m pytest harnesses/mini-git/tests/performance/ -v --tb=short

# Held-out tests (if you have them locally)
python -m pytest harnesses/mini-git/tests/held-out/ -v --tb=short

# Everything at once
python -m pytest harnesses/mini-git/tests/ -q
```

---

## Troubleshooting

**`benchmark: command not found`**
```bash
pip install -e .
# or use: python -m runner.cli
```

**Tests all skipping**
```bash
echo $MINI_GIT_CMD              # must be set
python $MINI_GIT_CMD init       # verify it runs
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
The `ANTHROPIC_API_KEY` from Claude Code is a session token, not an API key. Get a real key at [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys).

**Gemini 429 quota exceeded**
`gemini-2.5-pro` requires a paid tier. Switch to `gemini-2.5-flash`:
```bash
python run_benchmark.py --models gemini-2.5-flash --dry-run
```

**Scorer shows 0/72 behavioral tests**
Run from the project root, not a subdirectory:
```bash
cd meta-benchmark   # ← must be here
python -m scorer.scorecard --submission submissions/my-run --harness mini-git --dry-run
```

**Leaderboard shows "Failed to load data"**
Must be served via HTTP:
```bash
cd leaderboard && python -m http.server 8080
# open http://localhost:8080  (not file:///...)
```

---

## Score interpretation

| Score | What it means | Real examples |
|-------|---------------|---------------|
| 85–100 | Near-perfect. All tiers, adversarial handled, writes tests, fast, extends cleanly. | — |
| 70–85 | Strong. Core solid, edge cases handled, good performance. | **gemini-2.5-pro: 79.9, gpt-5.4: 79.3, gpt-5.3-codex: 78.7, claude-opus-4-6: 76.1** |
| 55–70 | Competent. All commands present, some perf or quality gaps. | — |
| 30–55 | Partial. Tier 1 works, Tier 2 rough, Tier 3 gaps. | — |
| < 30 | Broken. Core implementation bug stops most tests. | **gemini-2.5-flash: 7.3** |

All capable models cluster 76–80. Differentiation comes from performance benchmarks (OpenAI/Gemini: 100, Claude: 35), mutation kill rate (Claude: 100%, others vary), and code quality judge scores (Claude: 72.8, gpt-5.4: 60.5, others lower). Extension is a real second-prompt round — agents are given 15 minutes to add lightweight tag support. All current models pass only 4 of 16 extension tests.
