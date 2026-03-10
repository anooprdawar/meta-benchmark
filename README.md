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

> "claude-opus-4-6 built mini-git with 91% functional completeness, survived 87% of adversarial edge cases, 12/14 reliability scenarios, and cost $2.01 in 283 seconds."

That's a precise, reproducible claim. You can verify it. You can compare it. You can beat it.

## The first harness: mini-git

A from-scratch implementation of git — content-addressable object storage, staging index, branches, merges, the works.

**Why mini-git?**
- The spec is git itself. Every developer knows what correct behavior looks like.
- Content-addressable storage (SHA1 blob/tree/commit objects) is non-trivial architecturally — it separates agents that *understand* git from agents that *fake* it.
- Performance and reliability are well-defined and measurable.
- The test suite writes itself.

**Feature tiers:**

| Tier | Weight | Commands |
|------|--------|----------|
| Tier 1 — Core | 40% | `init`, `add`, `commit`, `log`, `status` |
| Tier 2 — Branching | 35% | `branch`, `checkout`, `merge`, `diff` |
| Tier 3 — Advanced | 25% | merge conflicts, `reset`, `stash` |

## Scoring

Seven dimensions, all automatable except code quality:

| Dimension | Weight | How |
|-----------|--------|-----|
| Functional completeness | 35%\* | 72 behavioral tests (pytest, black-box) |
| Adversarial survival | 20%\* | 155 edge cases — unicode filenames, binary files, corrupt objects, 100k+ files |
| Extension readiness | 10% | Second prompt: "now add remotes" — tests run again |
| Mutation kill rate | 10% | Does the agent's own test suite actually verify its logic? |
| Performance | 15% | p95 latency on `git log` (10k commits), `git add` (100k files), `git diff` (1k changes) |
| Reliability | 10% | SIGKILL mid-commit, concurrent writes, disk-full, corrupt object store |
| Code quality | 10% | Multi-model LLM judge, calibrated against human expert scores |

\* *Mutation kill rate weight (10%) is redistributed equally to functional + adversarial when mutation tooling is unavailable.*

**Output:** A structured JSON scorecard + human-readable report. All runs are public.

## Real results

These are actual API calls, actual generated code, actual test runs:

| Model | Score | Functional | Adversarial | Reliability | Cost |
|-------|-------|-----------|-------------|-------------|------|
| claude-opus-4-6 | **62.5/100** | 66/72 (91%) | 136/155 (88%) | 12/14 (86%) | $2.01 |
| gemini-2.5-flash | **7.3/100** | 0/72 (0%) | 1/155 (1%) | 0/14 (0%) | $0.02 |

Gemini's 0% functional score isn't an infrastructure failure — its generated code has a struct packing bug that crashes on `git add`. The harness caught a real flaw.

## Architecture

```
meta-benchmark/
  harnesses/
    mini-git/
      spec.md          ← Full PRD: what to build
      prompt.md        ← The single seed prompt the agent receives
      rubric.md        ← Scoring dimensions and weights
      tests/
        tier1/         ← init, add, commit, log, status  (34 tests)
        tier2/         ← branch, checkout, merge, diff   (22 tests)
        tier3/         ← merge conflicts, reset, stash   (16 tests)
        adversarial/   ← 155 edge cases
        extension/     ← remote operations (second prompt)
        performance/   ← latency benchmarks
        reliability/   ← chaos scenarios
      judge/
        rubric.md      ← LLM judge qualitative rubric
        calibration/   ← Human-scored reference implementations
  runner/
    cli.py             ← benchmark run / score / list-harnesses
    agents/
      anthropic_api.py ← Direct Anthropic API agent
      gemini_api.py    ← Direct Gemini API agent
      claude_code.py   ← Claude Code subprocess integration
      README.md        ← Manual submission format (for Cursor, Devin, etc.)
  scorer/
    behavioral.py      ← Runs tier 1-3 tests
    adversarial.py     ← Runs edge case battery
    extension.py       ← Runs extension tests
    mutation.py        ← Mutation testing (mutmut / cosmic-ray)
    performance.py     ← Latency benchmarks
    reliability.py     ← Chaos scenarios
    judge.py           ← Multi-model LLM judge
    scorecard.py       ← Aggregates everything → JSON
  leaderboard/
    index.html         ← Static leaderboard site (no build step)
    data/runs.json     ← All public runs
  run_benchmark.py     ← Run one or both models end-to-end
  submissions/         ← All agent outputs + scorecards live here
```

## Quickstart

```bash
git clone <this-repo>
cd meta-benchmark
pip install -e .
pip install pytest pytest-timeout pytest-json-report

# Explore what agents are asked to build
cat harnesses/mini-git/prompt.md

# Run the test suite against the included Claude submission
export MINI_GIT_CMD="python submissions/mini-git-claude-opus-4-6-live/workspace/mini_git.py"
python -m pytest harnesses/mini-git/tests/tier1/ -v

# Run a full benchmark against a model (requires API key)
export ANTHROPIC_API_KEY=sk-ant-...   # real key from console.anthropic.com
python run_benchmark.py --models claude-opus-4-6 --dry-run

# Score any submission
python -m scorer.scorecard \
  --submission submissions/mini-git-claude-opus-4-6-live \
  --harness mini-git \
  --dry-run

# View the leaderboard
cd leaderboard && python -m http.server 8080
# open http://localhost:8080
```

See [TESTING.md](TESTING.md) for a step-by-step walkthrough from zero.

## API keys

| Model | Key var | Where to get it |
|-------|---------|-----------------|
| claude-opus-4-6, claude-sonnet-4-6 | `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| gemini-2.5-flash, gemini-2.5-pro | `GEMINI_API_KEY` | aistudio.google.com → Get API key |

> **Note:** The `ANTHROPIC_API_KEY` injected by Claude Code itself is a session token and will return 401 if used for direct API calls. You need a separate key from the Anthropic console.

## Anti-Goodhart measures

Benchmarks rot when they become training targets.

1. **Private held-out tests** — A meaningful slice of adversarial + reliability tests is never published. Scores on the leaderboard include held-out test performance, verified by maintainers.
2. **Harness versioning** — v1, v2, v3. New requirements with each version. Old scores don't carry forward.
3. **Harness velocity** — The community grows the harness library faster than any model can be fine-tuned against it.

## Submitting a run

Any agent, any framework. If you can produce code, you can submit.

```bash
# Via the benchmark runner (Claude or Gemini API)
python run_benchmark.py --models claude-opus-4-6

# Manual (Cursor, Devin, Copilot, raw API, etc.)
# → See runner/agents/README.md for the submission format
```

To add your run to the leaderboard, open a PR with your `metadata.json` and `scorecard.json`.

## Contributing harnesses

A harness is a directory under `harnesses/` with:
- `spec.md` — What to build
- `prompt.md` — The seed prompt
- `rubric.md` — Scoring dimensions and weights
- `tests/` — The test suite
- `judge/rubric.md` — LLM judge rubric

Good harness candidates: a compiler for a simple language, a key-value store with persistence, a job queue with retry logic, a diff/patch tool, a CSV query engine. The pattern: **non-trivial, well-specified, testable**.

See [harnesses/mini-git/](harnesses/mini-git/) as the reference implementation.

## The leaderboard

```bash
cd leaderboard && python -m http.server 8080
```

Open `http://localhost:8080`. Sortable by any dimension. Filter by model, framework, harness version. Drill into any run for full scorecard detail.

The leaderboard currently shows two real runs (claude-opus-4-6 and gemini-2.5-flash). Add yours.

---

*Built to be forked, extended, and argued about. The goal is a common canvas — one place where "this model is better at coding" becomes a falsifiable claim.*
