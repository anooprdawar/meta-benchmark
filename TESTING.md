# Testing Guide

A step-by-step walkthrough. No prior knowledge needed.

---

## Setup (do this once)

```bash
cd meta-benchmark

# Install the benchmark CLI and test dependencies
pip install -e .
pip install pytest pytest-timeout pytest-json-report
```

Verify it works:

```bash
python -m runner.cli list-harnesses
# Available harnesses (1):
#   mini-git   Mini-Git: Product Requirements Document
```

---

## Step 1: Look at what agents are asked to build

```bash
cat harnesses/mini-git/prompt.md
```

This is the *exact* prompt agents receive. One page. No hints about the test suite. From this, agents must produce a working git implementation.

---

## Step 2: Run the tests against the included Claude submission

There's a real Claude-generated mini-git already in `submissions/`. Let's run the tests against it:

```bash
export MINI_GIT_CMD="python submissions/mini-git-claude-opus-4-6-live/workspace/mini_git.py"

# Tier 1: init, add, commit, log, status
python -m pytest harnesses/mini-git/tests/tier1/ -v --tb=short

# Tier 2: branch, checkout, merge, diff
python -m pytest harnesses/mini-git/tests/tier2/ -v --tb=short

# Tier 3: merge conflicts, reset, stash
python -m pytest harnesses/mini-git/tests/tier3/ -v --tb=short
```

Expected output for tier1:
```
34 passed in ~20s
```

Run everything at once:
```bash
python -m pytest harnesses/mini-git/tests/tier1/ harnesses/mini-git/tests/tier2/ harnesses/mini-git/tests/tier3/ -q
# 70 passed, 2 failed in ~60s
```

---

## Step 3: Run the full scorer against that submission

This runs all 7 scoring dimensions and produces a JSON scorecard:

```bash
python -m scorer.scorecard \
  --submission submissions/mini-git-claude-opus-4-6-live \
  --harness mini-git \
  --output /tmp/scorecard.json \
  --dry-run
```

`--dry-run` skips the LLM judge API calls. You'll see:

```
Running behavioral tests...
  Functional: 96.8/100 (70/72 tests)
Running adversarial tests...
  Adversarial: 87.7/100 (136/155 survived)
Running extension tests...
  Extension: 25.0/100 (4/16)
Running mutation testing...
  Mutation: 0.0/100 (unavailable)
Running performance benchmarks...
  Performance: 35.1/100
Running reliability tests...
  Reliability: 71.4/100 (10/14)
Running LLM judge...
  Quality: 0.0/100 (dry_run=True)

Total score: 66.4/100
```

The JSON scorecard:
```bash
cat /tmp/scorecard.json | python -m json.tool | head -40
```

---

## Step 4: Open the leaderboard

```bash
cd leaderboard
python -m http.server 8080
# open http://localhost:8080 in a browser
```

> **Must be served via HTTP** — opening `index.html` directly as a file won't work.

You'll see two real runs: claude-opus-4-6 (62.5) and gemini-2.5-flash (7.3). Click any row for the full scorecard breakdown.

---

## Step 5: Run a fresh benchmark against a model (requires API key)

This calls the model API, has it generate a mini-git from scratch, then scores the output.

### For Claude (Anthropic):

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # from console.anthropic.com/settings/keys
python run_benchmark.py --models claude-opus-4-6 --dry-run
```

> The key injected by Claude Code itself (`$ANTHROPIC_API_KEY` in a Claude Code session) is a session token and **will return 401**. You need a separate key from the Anthropic console.

### For Gemini:

```bash
pip install google-genai
export GEMINI_API_KEY=...   # from aistudio.google.com → Get API key
python run_benchmark.py --models gemini-2.5-flash --dry-run
```

### What happens:

1. A clean workspace is created under `submissions/`
2. The model receives `harnesses/mini-git/prompt.md`
3. The model generates code (~3–6 minutes for claude-opus-4-6, ~5 minutes for gemini-2.5-flash)
4. The full scorer runs against the output
5. Results are written to `submissions/<run>/scorecard.json`
6. `leaderboard/data/runs.json` is updated

Output looks like:
```
============================================================
  Model:  claude-opus-4-6
  Agent:  claude-api
  Output: submissions/mini-git-claude-opus-4-6-20260310T191557Z
============================================================

  Calling claude-opus-4-6 via Anthropic API (streaming)...
  API call complete in 282.3s
  Files written: 5
    README.md
    requirements.txt
    mini_git.py
    ...

  Duration:  283.0s
  Tokens:    1,822 in / 26,492 out
  Est. cost: $2.01

Scoring claude-opus-4-6...
  Functional: 91.0/100 (66/72 tests)
  ...

Total score: 62.5/100
```

`--dry-run` skips the LLM judge API calls (saves money while you're testing the pipeline). Remove it for a full score.

---

## Step 6: Score a manual submission

Have output from Cursor, Copilot, Devin, or any other tool? Structure it like this:

```bash
mkdir -p submissions/my-run/workspace

# Copy the agent's generated code
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

The scorer will look for the implementation at `workspace/mini_git.py`, `workspace/mini_git/__main__.py`, or `workspace/src/mini_git.py`.

---

## Step 7: Run the LLM judge (requires API key)

The quality score is 0 in dry-run mode. To get a real quality score:

```bash
export ANTHROPIC_API_KEY=sk-ant-...

python -m scorer.scorecard \
  --submission submissions/mini-git-claude-opus-4-6-live \
  --harness mini-git
# (no --dry-run)
```

The judge evaluates: plumbing/porcelain separation, object model quality, naming consistency, test quality, scope discipline.

---

## Run individual test categories

```bash
export MINI_GIT_CMD="python /path/to/mini_git.py"

# Adversarial: unicode, binary files, corrupt objects, edge cases
python -m pytest harnesses/mini-git/tests/adversarial/ -v --tb=short

# Extension: remote operations (add/push/pull)
python -m pytest harnesses/mini-git/tests/extension/ -v --tb=short

# Reliability: mid-commit SIGKILL, concurrent writes, disk full
python -m pytest harnesses/mini-git/tests/reliability/ -v --tb=short

# Count all collectible tests
python -m pytest harnesses/mini-git/tests/ --collect-only -q | tail -3
# ~257 tests collected
```

Tests skip cleanly if the implementation doesn't support the command — you won't get floods of confusing errors.

---

## Troubleshooting

**`benchmark: command not found`**
```bash
pip install -e .
# or use: python -m runner.cli
```

**`--timeout` unrecognized argument**
```bash
pip install pytest-timeout
```

**`--json-report` unrecognized argument**
```bash
pip install pytest-json-report
```

**Tests all skipping (0 collected or all skip)**
```bash
echo $MINI_GIT_CMD    # must be set
python $MINI_GIT_CMD init   # verify it actually runs
```

**`google-genai` not installed**
```bash
pip install google-genai
```

**Anthropic 401 error**
The `ANTHROPIC_API_KEY` from a Claude Code session is a session token — it only works inside Claude Code, not for direct API calls. Get a real key at [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys).

**Gemini 429 quota exceeded**
`gemini-2.5-pro` requires a paid tier. Use `gemini-2.5-flash` on the free tier:
```bash
python run_benchmark.py --models gemini-2.5-flash --dry-run
```

**Scorer shows 0/72 even though my code runs**
Run from the project root (`meta-benchmark/`), not from inside a subdirectory:
```bash
cd meta-benchmark
python -m scorer.scorecard --submission submissions/my-run --harness mini-git --dry-run
```

**Leaderboard shows "Failed to load data"**
Must be served via HTTP, not opened as a local file:
```bash
cd leaderboard && python -m http.server 8080
# then open http://localhost:8080
```

---

## Score interpretation

| Score | What it means |
|-------|---------------|
| 85–100 | Near-perfect. All tiers pass, adversarial handled, clean architecture. |
| 70–85 | Strong. Core + branching solid, most edge cases handled. |
| 55–70 | Competent. All commands present, some edge cases failing. (Claude opus-4-6: 62.5) |
| 30–55 | Partial. Tier 1 works, Tier 2 rough, Tier 3 gaps. |
| < 30 | Broken. Core implementation bug stops most tests. (Gemini 2.5-flash: 7.3) |
