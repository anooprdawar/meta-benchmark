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

Seven dimensions, all automated:

| Dimension | Weight | How |
|-----------|--------|-----|
| Functional completeness | 30% | 72 behavioral tests across 3 tiers (pytest, black-box) |
| Adversarial survival | 15% | 155 public + private held-out edge cases |
| Extension readiness | 10% | Second-prompt round: agent given 15 min to add lightweight tag support (`tag`, `tag -d`, `tag` listing, log annotations). 16 tests. |
| Mutation kill rate | 10% | Does the agent's own test suite catch code mutations? (mutmut) |
| Performance | 15% | p95 latency: `git log` on 10k commits, `git add` on 100k files, `git diff` on 1k changes |
| Reliability | 10% | SIGKILL mid-commit, concurrent writes, disk-full, corrupt object store |
| Code quality | 10% | Multi-model LLM judge, calibrated against human expert scores |

When a dimension is not applicable (e.g. the agent produced no test files, so mutation can't run), its weight is redistributed proportionally across functional, adversarial, and extension — keeping scores on a consistent 0–100 scale regardless of which dimensions apply.

**Output:** A structured JSON scorecard + human-readable report. All runs are public.

## Real results

All scores are from actual API calls, actual generated code, actual test runs — including private held-out tests:

| Model | Score | Functional | Adversarial | Extension | Mutation | Performance | Quality | Cost |
|-------|-------|-----------|-------------|-----------|----------|-------------|---------|------|
| gemini-2.5-pro | **79.9/100** ✓ | 70/72 (97%) | 146/166 (88%) | 4/16 | — | 100/100 | 37.3/100 | $0.14 |
| gpt-5.4 | **79.3/100** ✓ | 70/72 (97%) | 146/166 (88%) | 4/16 | 63.8% | 100/100 | 60.5/100 | $0.15 |
| gpt-5.3-codex | **78.7/100** ✓ | 70/72 (97%) | 146/166 (88%) | 4/16 | — | 100/100 | 26.0/100 | $0.04 |
| claude-opus-4-6 | **76.1/100** ✓ | 70/72 (97%) | 146/166 (88%) | 4/16 | 100% | 35.4/100 | 72.8/100 | $1.40 |
| gemini-2.5-flash | **7.3/100** | 0/72 (0%) | 1/155 (1%) | — | — | 0/100 | — | $0.02 |

✓ = scored with private held-out tests included. Extension = second-prompt delta test (agent given 15 min to add remote operations after initial submission).

What the data shows: All capable models pass the same functional and adversarial tests — the differentiation is performance, code quality, and mutation kill rate. OpenAI and Gemini are dramatically faster (100/100 performance vs Claude's 35.4). Claude writes the highest quality code (72.8 judge score) and comprehensively tests what it builds (100% mutation kill rate). All models pass only 4/16 extension tests — they add tags partially but miss log annotations and edge cases. Gemini 2.5 Flash's 0% functional score is a real bug in its generated code.

## Architecture

```
meta-benchmark/
  harnesses/
    mini-git/
      spec.md          ← Full PRD: what to build
      prompt.md        ← The single seed prompt the agent receives
      rubric.md        ← Scoring dimensions and weights
      tests/
        tier1/         ← init, add, commit, log, status   (34 tests)
        tier2/         ← branch, checkout, merge, diff    (22 tests)
        tier3/         ← merge conflicts, reset, stash    (16 tests)
        adversarial/   ← 155 public edge cases
        held-out/      ← gitignored, maintainer-only tests (anti-Goodhart)
        extension/     ← remote operations tests
        performance/   ← latency benchmarks with thresholds
        reliability/   ← chaos scenarios
      judge/
        rubric.md      ← LLM judge qualitative rubric
        calibration/   ← Human-scored reference implementations
  runner/
    cli.py             ← benchmark run / score / list-harnesses
    agents/
      anthropic_api.py ← Direct Anthropic API agent (claude-opus-4-6, sonnet, etc.)
      gemini_api.py    ← Direct Gemini API agent (gemini-2.5-flash, pro, etc.)
      openai_api.py    ← Direct OpenAI API agent (gpt-5.4, gpt-5.3-codex, etc.)
      claude_code.py   ← Claude Code subprocess integration
      README.md        ← Manual submission format (Cursor, Devin, Copilot, etc.)
  scorer/
    behavioral.py      ← Tier 1-3 behavioral tests
    adversarial.py     ← Public + held-out edge cases
    extension.py       ← Remote operations tests
    mutation.py        ← Mutation testing via mutmut
    performance.py     ← Latency benchmarks
    reliability.py     ← Chaos scenarios
    judge.py           ← Multi-model LLM judge (3 models, calibration anchoring)
    scorecard.py       ← Aggregates everything → JSON
  leaderboard/
    index.html         ← Static leaderboard site (no build step)
    data/runs.json     ← All public runs
  run_benchmark.py     ← Orchestrates full model runs end-to-end
  submissions/         ← Agent outputs + scorecards (gitignored)
```

## Quickstart

```bash
git clone https://github.com/anoopdawar/meta-benchmark
cd meta-benchmark
pip install -e .
pip install pytest pytest-timeout pytest-json-report "mutmut<3"

# See what agents are asked to build
cat harnesses/mini-git/prompt.md

# Run the test suite against the included Claude submission
export MINI_GIT_CMD="python submissions/mini-git-claude-opus-4-6-live/workspace/mini_git.py"
python -m pytest harnesses/mini-git/tests/tier1/ -v

# Score it
python -m scorer.scorecard \
  --submission submissions/mini-git-claude-opus-4-6-live \
  --harness mini-git \
  --dry-run

# Run a fresh benchmark (requires API key)
export ANTHROPIC_API_KEY=sk-ant-...
python run_benchmark.py --models claude-opus-4-6 --dry-run

# View the leaderboard
cd leaderboard && python -m http.server 8080
```

See [TESTING.md](TESTING.md) for a complete step-by-step walkthrough.

## API keys

| Model | Environment variable | Where to get it |
|-------|---------------------|-----------------|
| claude-opus-4-6, claude-sonnet-4-6, etc. | `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) → API Keys |
| gemini-2.5-flash, gemini-2.5-pro, etc. | `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) → Get API key |
| gpt-5.4, gpt-5.3-codex, o3, etc. | `OPENAI_META_BENCHMARK_KEY` | [platform.openai.com](https://platform.openai.com) → API Keys |

> **Note:** The `ANTHROPIC_API_KEY` in a Claude Code session is an internal session token. It returns 401 for direct API calls. You need a separate key from the Anthropic console.

## Anti-Goodhart measures

Benchmarks rot when they become training targets. These are real, implemented countermeasures — not aspirations.

**1. Private held-out tests**

`harnesses/mini-git/tests/held-out/` is gitignored. It never appears in the public repo. The adversarial scorer checks for this directory automatically — if it exists, those tests run and count toward the score. Leaderboard entries scored by a maintainer are marked `verified: true` in the scorecard JSON.

Anyone can add their own held-out tests locally. The scoring infrastructure handles it automatically.

**2. Harness versioning**

Each harness has a `harness_version` field. The leaderboard filters by version. When requirements change, the version increments and old scores are not comparable. Currently v1.0.0.

**3. Harness velocity**

One harness is a benchmark. Ten harnesses is a standard. The community adds harnesses faster than models can be tuned against any one of them. See *Contributing harnesses* below.

## Submitting a run

Any agent, any framework. If you can produce code, you can submit.

```bash
# Via the benchmark runner (Anthropic or Gemini API)
python run_benchmark.py --models claude-opus-4-6

# Manual submission (Cursor, Devin, Copilot, raw API, etc.)
# → See runner/agents/README.md for the metadata.json format
```

To add your run to the public leaderboard, open a PR adding your `metadata.json` and `scorecard.json` under `submissions/<your-run>/`.

## Contributing harnesses

A harness is a directory under `harnesses/` with:

```
harnesses/your-harness/
  spec.md          ← What to build (the PRD)
  prompt.md        ← The seed prompt agents receive
  rubric.md        ← Scoring dimensions and weights
  tests/           ← Automated test suite
  judge/rubric.md  ← LLM judge rubric
```

Good harness candidates: a compiler for a simple language, a key-value store with persistence, a job queue with retry logic, a diff/patch tool, a CSV query engine.

The pattern: **non-trivial, well-specified, deterministically testable**.

See [harnesses/mini-git/](harnesses/mini-git/) as the reference implementation.

## The leaderboard

```bash
cd leaderboard && python -m http.server 8080
# open http://localhost:8080
```

Sortable by any dimension. Filter by model, framework, and harness version. Drill into any run for the full scorecard — tier breakdown, adversarial detail, performance latency, judge dimension scores.

Currently showing five real runs. Runs scored without the LLM judge (using `--dry-run`) display `—` in the Quality column rather than 0 — so a missing quality score is always distinguishable from a genuinely bad one. Add yours.

---

*Built to be forked, extended, and argued about. The goal is a common canvas — one place where "this model is better at coding" becomes a falsifiable claim.*
