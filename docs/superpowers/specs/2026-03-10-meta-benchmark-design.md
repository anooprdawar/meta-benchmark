# Meta-Benchmark: A Community Standard for Measuring AI Coding Agents

**Document type:** Design Specification
**Status:** Draft v1.0
**Date:** 2026-03-10
**Author:** Meta-Benchmark Working Group

---

## 1. Context and Motivation

### 1.1 The Measurement Problem

AI coding agents have improved rapidly. In 2024, the state of the art on SWE-bench was below 20%. By early 2026, leading agents routinely exceed 55% on the public split. But SWE-bench is now a known quantity — it has been in training data, the public test cases are memorized, and the benchmark has become a marketing surface rather than a measurement tool.

The field needs something harder, more realistic, and more resistant to Goodharting.

### 1.2 What Existing Benchmarks Miss

Most existing benchmarks for coding agents share three failure modes:

**Decomposition too fine.** HumanEval, MBPP, and their descendants test function-level code completion. Real software development involves designing systems, navigating tradeoffs, managing complexity across files, and recovering from mistakes. A benchmark that tests "write a function to reverse a linked list" tells us nothing about whether an agent can design and build a 1,000-line system.

**Static ground truth.** Benchmarks with fixed test suites are solvable by memorization and test-case-specific optimization. Once a benchmark is public, it stops measuring capability and starts measuring contamination.

**No adversarial or reliability dimension.** Passing unit tests on happy paths is table stakes. Real software must survive edge cases, partial failures, and hostile inputs. Existing benchmarks do not measure this.

### 1.3 The CSS Zen Garden Analogy

The CSS Zen Garden (csszengarden.com) is instructive. It presents a fixed HTML document and asks designers to style it however they like. The constraint (fixed content) forces creativity and reveals true skill. The open-endedness (any CSS approach allowed) prevents gaming — there is no "correct" implementation to memorize.

Meta-Benchmark applies this principle to code. Each **harness** specifies:
- A fixed problem statement (the HTML document)
- Behavioral tests that are partially hidden from agents (the judging criteria)
- Open-ended implementation space (the agents choose architecture, language, approach)

The result is a benchmark where agents cannot memorize solutions — they must genuinely solve the problem.

---

## 2. System Components

Meta-Benchmark consists of four components: Harness Format, Runner, Scorer, and Leaderboard.

### 2.1 Harness Format

A harness is a self-contained problem specification. Each harness defines:
- A problem description (the "spec")
- A seed prompt (what the agent receives)
- A behavioral test suite (some public, some private)
- A scoring rubric
- An extension prompt (for testing extensibility)
- A judge rubric (for qualitative scoring)

Harnesses are versioned. A new version of a harness invalidates all prior scores for that harness on the leaderboard.

### 2.2 Runner

The Runner is a CLI tool that:
1. Presents the seed prompt to an agent (via API or local process)
2. Collects the agent's output (source files, test files, README)
3. Executes the behavioral test suite against the agent's implementation
4. Runs benchmarks, chaos scenarios, mutation tests
5. Calls LLM judge API for qualitative scoring
6. Produces a machine-readable score report (JSON)

### 2.3 Scorer

The Scorer aggregates dimension scores using the rubric's weighting formula and produces the final composite score. It also handles N/A dimension redistribution.

### 2.4 Leaderboard

The Leaderboard is a public registry of scores. Each entry records:
- Agent identifier (model name + version + any system prompt hash)
- Harness name and version
- Run timestamp
- Score breakdown by dimension
- Total score
- Hardware metadata (for performance benchmarks)
- Mandatory metadata tags (see Section 7)

---

## 3. Harness Directory Structure

Each harness lives under `harnesses/{harness-name}/`. The structure is:

```
harnesses/
└── mini-git/
    ├── spec.md                  # Full PRD — what the system must do
    ├── prompt.md                # The single seed prompt the agent receives
    ├── rubric.md                # Scoring dimensions, weights, test inventory
    ├── judge/
    │   └── rubric.md            # Qualitative rubric for LLM judge
    ├── tests/
    │   ├── public/              # Tests visible to agents (sample cases)
    │   │   ├── test_tier1.py
    │   │   ├── test_tier2.py
    │   │   └── test_tier3.py
    │   └── private/             # Tests NOT disclosed to agents
    │       ├── test_adversarial.py
    │       ├── test_chaos.py
    │       └── test_extension.py
    ├── benchmarks/
    │   ├── setup/               # Scripts to seed benchmark repos
    │   │   ├── seed_10k_commits.py
    │   │   ├── seed_100k_files.py
    │   │   └── seed_large_tree.py
    │   └── run_benchmarks.py
    ├── extension/
    │   └── prompt.md            # Second prompt for extension readiness test
    └── fixtures/
        ├── sample_repo/         # Pre-built fixture repository for tests
        └── corrupt_objects/     # Fixtures for corruption detection tests
```

The `tests/private/` directory is excluded from the repository that agents can access. It is only present on the CI runner.

---

## 4. Runner CLI Interface

```
meta-benchmark run [OPTIONS] <harness> <agent>

Arguments:
  harness     Harness name (e.g., "mini-git") or path to harness directory
  agent       Agent identifier: "openai:gpt-5", "anthropic:claude-4-opus",
              "local:./my_agent.sh", or an agent config file path

Options:
  --tier          [1|2|3|all]      Run only up to a specific tier (default: all)
  --timeout       SECONDS          Max wall-clock time for agent interaction (default: 1800)
  --output        PATH             Write JSON score report to PATH
  --no-llm-judge                   Skip qualitative judge scoring
  --no-chaos                       Skip chaos/reliability scenarios
  --no-perf                        Skip performance benchmarks
  --no-mutation                    Skip mutation testing
  --public-only                    Run only public tests (for agent self-evaluation)
  --extension                      Run extension prompt after initial submission
  --hardware-tag  STRING           Tag the run with hardware description
  --metadata      KEY=VALUE        Additional metadata tags (repeatable)
  --sandbox       [docker|nsjail|none]  Execution sandbox (default: docker)
  --verbose                        Print test-by-test results to stdout

Examples:
  # Full evaluation
  meta-benchmark run mini-git anthropic:claude-4-opus --output results/claude4.json

  # Quick self-check (public tests only, no benchmarks)
  meta-benchmark run mini-git local:./my_submission/ --public-only --no-perf --no-chaos

  # Tier 1 only with verbose output
  meta-benchmark run mini-git openai:gpt-5 --tier 1 --verbose
```

### 4.1 Agent Interface

The runner communicates with agents via one of three protocols:

**API agent:** The runner calls the model API with the seed prompt. The agent's response is parsed for file artifacts (code blocks labeled with filenames). The runner materializes those files into a temporary directory, then runs evaluation.

**Local agent:** The runner invokes `./agent.sh <prompt_file>` and collects the output directory. Useful for testing local models or agent harness wrappers.

**Interactive agent:** The runner spawns an interactive session and streams the prompt. The agent may ask clarifying questions (the runner answers with "not available — work from the prompt"). The session ends when the agent signals completion.

---

## 5. Scoring Dimensions

All harnesses share the same seven scoring dimensions. Individual harness rubrics specify the concrete tests and thresholds for each dimension.

### 5.1 Functional Completeness (30%)

**Method:** Behavioral test suite executed against the agent's implementation via subprocess. Tests are organized by tier (typically Tier 1/2/3 weighted as 40/35/25%).

**Score:** Weighted pass rate across all tiers, 0–100.

**Rationale:** This is the baseline — does the implementation do what was asked?

### 5.2 Adversarial Survival (15%)

**Method:** Edge case battery not disclosed to the agent. Tests are written to probe boundary conditions, unusual inputs, and failure modes that a naive implementation would miss.

**Score:** Pass rate on the private adversarial test suite, 0–100.

**Rationale:** Passing unit tests on happy paths is necessary but not sufficient. Real software must survive hostile inputs. This dimension rewards implementations that handle the unexpected gracefully.

### 5.3 Extension Readiness (10%)

**Method:** After initial submission, the runner issues a second prompt asking the agent to add a new feature. The feature is designed to be a natural extension of the existing system (e.g., adding `git tag` to mini-git). A new test suite for the extension is run.

**Score:** Pass rate on extension tests, scaled by whether the agent also wrote tests for the extension.

**Rationale:** Clean code is extensible code. This dimension rewards implementations with good separation of concerns and tests that an extension can leverage. It also tests whether the agent can work incrementally on its own code — an increasingly important capability.

### 5.4 Mutation Kill Rate (10%)

**Method:** Automated mutation testing against the agent's own test suite. Mutations are applied to the implementation (not the tests). The mutation kill rate is the fraction of mutants that cause at least one test to fail.

**Score:** Kill rate as a percentage, 0–100.

**Rationale:** High mutation kill rate means the tests are actually verifying behavior, not just exercising code paths. An agent that writes tests that don't actually assert behavior will score near 0 on this dimension even if the tests "pass."

### 5.5 Performance (15%)

**Method:** Timed benchmarks with pre-seeded workloads. p95 latency is measured over 5 runs. Score is based on how close the p95 latency is to the target threshold (linear interpolation from 100% at threshold to 0% at 2x threshold).

**Score:** Weighted average of per-benchmark sub-scores, 0–100.

**Rationale:** Correctness at scale is different from correctness on small inputs. This dimension rewards implementations that think about algorithmic complexity, not just correctness.

### 5.6 Reliability (10%)

**Method:** Chaos scenarios that simulate system-level failures (SIGTERM, disk full, corrupt files, truncated index). Each scenario is run 3 times.

**Score:** Pass rate on chaos scenarios, 0–100.

**Rationale:** A production-quality implementation must not corrupt data under failure conditions. Atomic writes and corruption detection are engineering fundamentals that are easy to skip when only testing happy paths.

### 5.7 Code Quality (10%)

**Method:** A panel of LLM judges scores the implementation against the harness-specific judge rubric. Three judges score independently; scores are averaged. The judge rubric covers qualitative dimensions like separation of concerns, abstraction quality, naming consistency, test quality, and scope discipline.

**Score:** Average of judge dimension scores, 0–100.

**Rationale:** Passing tests is necessary but not sufficient for good code. This dimension captures whether the implementation is maintainable, readable, and well-designed — properties that are hard to measure automatically but easy to assess with a well-calibrated judge.

---

## 6. Mini-Git Harness Detail

### 6.1 Problem Summary

Build a minimal implementation of git from scratch. Store objects as content-addressable blobs, trees, and commits using SHA1 hashing, mirroring real git's object model. Implement the core CLI commands, branching, merging, diffing, resetting, and stashing.

**Why mini-git?** It is a well-scoped, well-understood problem with a complete specification (real git's design). It exercises file I/O, serialization, DAG traversal, hash addressing, CLI design, atomic writes, and testing — a broad cross-section of software development skills. It is small enough to complete in a bounded session but large enough to reveal architectural decision-making.

### 6.2 Feature Tiers

| Tier | Features | Functional Weight |
|------|----------|------------------|
| 1 | `init`, `add`, `status`, `commit`, `log` | 40% |
| 2 | `branch`, `checkout`, `merge` (FF), `diff` | 35% |
| 3 | Merge conflicts, `reset`, `stash` | 25% |

### 6.3 Object Model

Mini-git must implement real git's object format:

```
Object on disk: zlib(  "{type} {length}\0{content}"  )
Object path:    .git/objects/{sha1[0:2]}/{sha1[2:40]}
Object key:     sha1( "{type} {length}\0{content}" )
```

The three object types:
- **Blob:** raw file bytes
- **Tree:** sorted list of `{mode} {name}\0{20-byte-sha1}` entries
- **Commit:** text body with `tree`, `parent`, `author`, `committer`, message

### 6.4 Performance Benchmarks

| Benchmark | Workload | Target |
|-----------|----------|--------|
| Deep history traversal | 10,000-commit chain | `git log` < 2s p95 |
| Bulk staging (small files) | 100,000 × 1 KB files | `git add .` < 30s p95 |
| Bulk staging (large files) | 1,000 × 1 MB files | `git add .` < 60s p95 |
| Large working tree status | 100,000 files | `git status` < 10s p95 |
| Diff between commits | 10,000 files, 1,000 changed | `git diff` < 5s p95 |
| Bulk commit | 100,000 staged files | `git commit` < 30s p95 |
| Cold read | Single 10 KB blob | < 50ms p95 |

### 6.5 Reliability Scenarios

| Scenario | Pass Criterion |
|----------|----------------|
| SIGTERM during `git add` | No corrupt objects; repo usable |
| SIGTERM during `git commit` (post-object-write, pre-ref-update) | Either committed cleanly or HEAD unchanged |
| Disk full during object write | Non-zero exit; existing objects intact |
| Object file corrupted | Error detected on read; non-zero exit |
| Index truncated | Next operation detects and reports; no crash |
| `git commit` with 0 bytes disk space | Non-zero exit; helpful error message |

### 6.6 Extension Prompt

After initial submission, the following extension prompt is issued:

> "Add `mini-git tag <name> [commit]` (create lightweight tag), `mini-git tag` (list tags), `mini-git tag -d <name>` (delete tag), and show tags in `git log` output. Write tests."

Extension tests cover: tag creation, tag listing, tag deletion, tag visibility in log, duplicate rejection.

### 6.7 Adversarial Battery (Sample)

The private adversarial test battery includes 20 cases. A representative sample:
- File path with unicode characters (`héllo wörld.txt`)
- File with NUL bytes in content (binary)
- 1,000-commit deep history `git log` without stack overflow
- Manually corrupted object → `git checkout` must detect and report
- Nested 5-level subdirectory tree staged with `git add .`
- Branch name with slash (`feature/my-thing`)
- `git diff` on a file with no trailing newline
- `git merge` where merge target is an ancestor of HEAD

---

## 7. Anti-Goodhart Measures

Goodhart's Law: when a measure becomes a target, it ceases to be a good measure. The benchmark is designed with several structural countermeasures.

### 7.1 Private Tests

The adversarial test battery, chaos scenarios, and extension tests are not disclosed to agents. Agents receive:
- The seed prompt (`prompt.md`)
- A sample of public tests (demonstrating test format)
- The scoring rubric (dimension names and weights)

Agents do NOT receive the private test cases. The rubric tells them what is being measured; it does not tell them the specific inputs being used to measure it.

### 7.2 Harness Versioning

Each harness is versioned. When private tests are discovered to be guessable (e.g., through model memorization), a new harness version is released with a refreshed private test suite. Scores from different harness versions are not compared directly.

### 7.3 Velocity Scoring

The leaderboard tracks not just absolute scores but score velocity — how much an agent's score improves after the benchmark is published vs. how much it improves before. High post-publication improvement relative to pre-publication capability is a flag for contamination.

### 7.4 Structural Diversity

Harnesses are designed to be structurally diverse (different domains, different languages, different evaluation methods). An agent that is over-optimized for one harness will not generalize across the suite.

### 7.5 Novel Harnesses

The working group commits to releasing at least 2 new harnesses per quarter, targeting problem domains not yet represented. Existing harnesses are never modified in a way that changes their difficulty — only new versions are released.

---

## 8. Variable Isolation (Mandatory Metadata)

Leaderboard entries must include mandatory metadata tags to enable meaningful comparison. Without variable isolation, score comparisons across runs are ambiguous.

### 8.1 Required Tags

| Tag | Description | Example |
|-----|-------------|---------|
| `model_id` | Full model identifier including version | `claude-sonnet-4-6` |
| `model_context_window` | Context window used for the run | `200000` |
| `temperature` | Sampling temperature | `0.7` |
| `system_prompt_hash` | SHA1 of system prompt (or "none") | `abc123` |
| `tool_use` | Whether the agent used tool calls | `true` |
| `agentic_scaffold` | Scaffold used, if any | `claude-code-v1.3` |
| `hardware` | CPU, RAM, OS of evaluation machine | `m4-pro-24gb-macos` |
| `python_version` | Python version used for test runner | `3.12.2` |
| `harness_version` | Harness version | `1.0.0` |
| `run_date` | ISO 8601 date | `2026-03-10` |

### 8.2 Optional Tags

| Tag | Description |
|-----|-------------|
| `few_shot_examples` | Number of examples provided before seed prompt |
| `chain_of_thought` | Whether explicit CoT was prompted |
| `multi_turn` | Whether agent had multi-turn interaction |
| `agent_time_budget` | Wall-clock budget given to agent in seconds |

### 8.3 Tag Enforcement

The runner validates required tags before accepting a score submission. A run without all required tags is accepted as a local result but cannot be submitted to the public leaderboard.

---

## 9. Implementation Phases

### Phase 1: Foundation (Weeks 1–4)

**Deliverables:**
- [ ] Repository structure and harness format specification
- [ ] Mini-git harness: `spec.md`, `prompt.md`, `rubric.md`, `judge/rubric.md`
- [ ] Functional test suite for Tier 1 (public + private)
- [ ] Runner MVP: can present prompt to a local agent, collect output, run public tests

**Success criteria:** A human developer can use the runner to self-evaluate a mini-git implementation against public tests.

### Phase 2: Full Evaluation (Weeks 5–8)

**Deliverables:**
- [ ] Full mini-git test suite (all tiers, adversarial, chaos)
- [ ] Performance benchmark harness (benchmark seeding scripts, timing infrastructure)
- [ ] Mutation testing integration (`mutmut` for Python agents)
- [ ] LLM judge integration (judge rubric prompt, API calls, score aggregation)
- [ ] JSON score report schema and validation

**Success criteria:** Runner can produce a complete 7-dimension score report for a mini-git submission.

### Phase 3: Agent Integration (Weeks 9–12)

**Deliverables:**
- [ ] API agent protocol (send prompt → receive files → evaluate)
- [ ] Support for major model APIs (Anthropic, OpenAI, Google)
- [ ] Score submission endpoint (leaderboard backend)
- [ ] Leaderboard frontend (read-only, scores + metadata)

**Success criteria:** An external team can score their model on mini-git and submit to the leaderboard without manual steps.

### Phase 4: Harness Expansion (Weeks 13–20)

**Deliverables:**
- [ ] Second harness: `mini-redis` (in-memory key-value store with TTL, persistence, pub/sub)
- [ ] Third harness: `json-schema-validator` (implement JSON Schema draft-7 validator)
- [ ] Harness author guide (how to write a harness that meets quality standards)
- [ ] Cross-harness aggregation on leaderboard

**Success criteria:** Three harnesses available; composite leaderboard shows aggregate score.

### Phase 5: Anti-Goodhart Hardening (Weeks 21–26)

**Deliverables:**
- [ ] Private test refresh for mini-git (new adversarial cases, harness v1.1)
- [ ] Velocity score computation on leaderboard
- [ ] Contamination detection tooling (similarity analysis between agent submissions)
- [ ] Community process for harness proposals and review

**Success criteria:** Working group can detect and respond to evidence of benchmark gaming within 30 days.

---

## 10. Verification Criteria

The following criteria define "done" for v1.0 of the Meta-Benchmark system:

### Harness Quality
- [ ] Mini-git spec is complete and unambiguous (tested by having 3 independent human developers implement it correctly from spec alone)
- [ ] Public tests are executable with a single command on a fresh checkout
- [ ] Private tests are not guessable from the public tests or rubric description
- [ ] Performance benchmarks are reproducible within ±15% on the same hardware across 10 runs

### Runner Quality
- [ ] Runner produces identical scores for identical submissions (determinism, excluding LLM judge variance)
- [ ] Runner handles agent timeouts gracefully (non-zero exit, partial score reported)
- [ ] Runner can be run from a clean environment with `pip install meta-benchmark && meta-benchmark run mini-git ...`
- [ ] LLM judge score variance across 3 judges is < 15 points for any dimension on any submission

### Leaderboard Quality
- [ ] All required metadata tags are validated before leaderboard submission
- [ ] Scores are not directly comparable across harness versions (enforced by version tagging)
- [ ] Leaderboard correctly handles N/A dimension redistribution

### System Properties
- [ ] The system cannot be gamed by submitting the real `git` binary (behavioral tests check for implementation-specific outputs; SHA1 interoperability is tested but not required to be byte-perfect)
- [ ] A completely naïve implementation (e.g., empty files) scores < 10 on every dimension except possibly code quality
- [ ] A high-quality human implementation of mini-git scores > 85 overall

---

## Appendix A: Design Decisions and Rationale

### Why SHA1 and not SHA256?

Real git uses SHA1 (SHA256 is experimental in git 2.29+). Mini-git uses SHA1 to maintain conceptual fidelity with real git and to allow cross-validation: a correctly implemented mini-git should produce the same object SHAs as real git for the same content. This makes the test of "is the SHA correct" objective and automatable.

### Why Python as the specified language?

The prompt specifies Python as the suggested language but explicitly allows any language. Python is suggested because: (a) it is the most common language in agent training data, (b) it has good libraries for subprocess testing, and (c) the mutation testing toolchain (`mutmut`) is Python-native. Agents choosing other languages are not penalized; mutation testing falls back to language-appropriate tools.

### Why 7 dimensions?

Seven dimensions capture the distinct qualities of a good implementation without over-complicating the rubric. The weights reflect rough importance: correctness (30%) is most important, then performance (15%), adversarial survival (15%), with qualitative dimensions at 10% each. The weights were chosen by the working group through structured deliberation and are expected to evolve with community input.

### Why include a qualitative judge dimension?

Automated tests can measure correctness and performance. They cannot measure whether code is readable, well-structured, or appropriate in scope. These properties matter for a benchmark that aims to measure genuine engineering quality, not just test-case satisfaction. LLM judges are imperfect but significantly better than no qualitative signal.

### Why is networking out of scope for mini-git?

Networking significantly expands scope (pack protocol, HTTP transport, authentication, SSH) without illuminating the core object model. The benchmark would become a test of network protocol implementation rather than data structures and systems design. A separate harness for distributed systems (e.g., a mini Raft implementation) is more appropriate for that dimension.

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| Harness | A complete problem specification + test suite + rubric for a specific task |
| Runner | The CLI tool that orchestrates agent evaluation |
| Scorer | The component that computes final scores from raw test results |
| Plumbing | Low-level git operations (object read/write, index manipulation, ref update) |
| Porcelain | User-facing git commands that compose plumbing operations |
| Goodharting | Optimizing for the metric rather than the underlying quality it measures |
| Mutation kill rate | The fraction of code mutations that cause at least one test to fail |
| N/A redistribution | Proportionally reallocating the weight of inapplicable dimensions to applicable ones |
| Adversarial battery | Private test suite designed to find edge case failures |
| Chaos scenario | A test that simulates a system-level failure (SIGTERM, disk full, corruption) |

---

*Document version 1.0.0. Last updated: 2026-03-10.*
