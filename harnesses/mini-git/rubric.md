# Mini-Git: Scoring Rubric

**Harness ID:** mini-git
**Version:** 1.0.0
**Total Score:** 0–100 (weighted composite)

---

## Score Computation

```
total_score = sum(dimension_score_i * weight_i)  for all applicable dimensions

where dimension_score_i is in [0, 100]
and   weight_i is the declared weight

If a dimension is NOT APPLICABLE (see section 9), its weight is
redistributed proportionally among applicable dimensions before
the weighted sum is computed.
```

---

## Dimensions

| # | Dimension | Weight | Scoring Method |
|---|-----------|--------|----------------|
| 1 | Functional completeness | 30% | Automated behavioral test suite |
| 2 | Adversarial survival | 15% | Edge case battery |
| 3 | Extension readiness | 10% | Second-prompt delta test |
| 4 | Mutation kill rate | 10% | Mutation testing |
| 5 | Performance | 15% | p95 latency benchmarks |
| 6 | Reliability | 10% | Chaos scenario suite |
| 7 | Code quality | 10% | LLM judge (see judge/rubric.md) |

---

## 1. Functional Completeness (30%)

### Method

Automated behavioral tests exercise the CLI interface via subprocess. Each test invokes the mini-git binary and asserts on stdout, stderr, exit code, and/or file system state. Tests are organized by tier.

### Test Inventory

**Tier 1 tests (40% of this dimension's points):**

| Test ID | Command | Assertion |
|---------|---------|-----------|
| T1-01 | `init` | `.git/HEAD` exists, contains `ref: refs/heads/main` |
| T1-02 | `init` (existing repo) | Does not destroy existing objects; outputs "Reinitialized" |
| T1-03 | `add` single file | Blob written to `.git/objects/`; index updated |
| T1-04 | `add .` | All files in working tree staged |
| T1-05 | `add` nonexistent file | Exit non-zero; error message mentions the path |
| T1-06 | `add` empty file | Valid blob with empty content stored |
| T1-07 | `add` binary file | Does not crash; blob stored correctly |
| T1-08 | `status` clean | "nothing to commit, working tree clean" |
| T1-09 | `status` new staged file | Listed under "Changes to be committed" |
| T1-10 | `status` modified unstaged | Listed under "Changes not staged" |
| T1-11 | `status` untracked | Listed under "Untracked files" |
| T1-12 | `status` deleted unstaged | Listed as "deleted" under not-staged |
| T1-13 | `commit -m` | Commit object written; branch ref updated; index unchanged |
| T1-14 | `commit` nothing staged | Non-zero exit; "nothing to commit" message |
| T1-15 | `commit` empty message | Non-zero exit; error message |
| T1-16 | `log` | Shows commit SHA1, author, date, message |
| T1-17 | `log --oneline` | Short SHA1 + first line of message |
| T1-18 | `log` no commits | Non-zero exit; "does not have any commits yet" |
| T1-19 | Blob round-trip | Write file → add → cat-file equivalent read → content matches |
| T1-20 | SHA1 deduplication | Two files with same content produce one object file |

**Tier 2 tests (35% of this dimension's points):**

| Test ID | Command | Assertion |
|---------|---------|-----------|
| T2-01 | `branch` | Lists all branches; marks current with `*` |
| T2-02 | `branch <name>` | New ref created pointing to HEAD commit |
| T2-03 | `branch -d` | Ref file removed |
| T2-04 | `branch -d` current branch | Non-zero exit; refused |
| T2-05 | `branch` duplicate name | Non-zero exit; "already exists" message |
| T2-06 | `checkout <branch>` | HEAD updated; working tree matches branch tip |
| T2-07 | `checkout -b <name>` | Branch created and HEAD switched |
| T2-08 | `checkout` dirty tree | Refused when changes would be overwritten |
| T2-09 | `checkout <sha1>` | Detached HEAD; warning shown |
| T2-10 | `merge` fast-forward | Branch ref updated; working tree matches merged state |
| T2-11 | `merge` already up-to-date | "Already up to date." |
| T2-12 | `diff` working vs staged | Unified diff output for modified file |
| T2-13 | `diff --staged` | Unified diff of staged vs HEAD |
| T2-14 | `diff <c1> <c2>` | Diff between two historical commits |
| T2-15 | `diff` binary file | "Binary files differ" line, no crash |

**Tier 3 tests (25% of this dimension's points):**

| Test ID | Command | Assertion |
|---------|---------|-----------|
| T3-01 | Merge conflict | Conflict markers written to file |
| T3-02 | Merge conflict | MERGE_HEAD created |
| T3-03 | Post-conflict commit | Merge commit has two parents |
| T3-04 | `reset --soft` | HEAD moved; index unchanged; working tree unchanged |
| T3-05 | `reset --mixed` | HEAD moved; index reset; working tree unchanged |
| T3-06 | `reset --hard` | HEAD moved; index reset; working tree reset |
| T3-07 | `reset HEAD <file>` | Single file unstaged; others remain staged |
| T3-08 | `stash` | Changes removed from working tree; stash entry created |
| T3-09 | `stash list` | Lists stash entries with correct format |
| T3-10 | `stash pop` | Working tree restored; stash entry removed |
| T3-11 | `stash drop` | Stash entry removed without applying |
| T3-12 | `stash pop` empty | "No stash entries found." |

### Scoring Formula

```
tier1_score  = (passing_t1_tests / total_t1_tests) * 100
tier2_score  = (passing_t2_tests / total_t2_tests) * 100
tier3_score  = (passing_t3_tests / total_t3_tests) * 100

functional_score = 0.40 * tier1_score
                 + 0.35 * tier2_score
                 + 0.25 * tier3_score
```

If the agent implements no Tier 2 features, Tier 2 score is 0 (not N/A). Tier 3 is N/A only if Tier 1 is also incomplete (score < 50). In that case, Tier 3 weight is redistributed.

---

## 2. Adversarial Survival (15%)

### Method

The harness runner executes an adversarial edge case battery against the agent's implementation. These tests are NOT disclosed to the agent in the prompt.

### Adversarial Test Cases

| ID | Scenario | What's tested |
|----|---------|---------------|
| A-01 | `git add` a file whose content changes between add and commit | Blob captures snapshot at add-time, not commit-time |
| A-02 | File path with spaces and unicode: `"héllo wörld.txt"` | Encoding-safe path handling |
| A-03 | File with a NUL byte in its content | Binary-safe blob storage |
| A-04 | Commit with a message containing newlines | Multi-line message preserved in log |
| A-05 | 1,000-commit deep history `git log` | Does not stack overflow; handles long chains |
| A-06 | Delete `.git/objects/{prefix}/` after committing; run status | Detects corruption; exits non-zero with message |
| A-07 | Manually corrupt an object file (flip one byte); then checkout | Detects SHA1 mismatch; reports corrupt object |
| A-08 | `git checkout` when HEAD is a detached SHA1 | Works correctly without crashing |
| A-09 | Nested subdirectories (5 levels deep) added with `add .` | All blobs and subtrees written; tree structure correct |
| A-10 | `git stash` twice, `stash list` shows 2, `stash pop` twice | Stack discipline; correct entry ordering |
| A-11 | `git reset --hard` on a repo with no commits | Graceful error, not crash |
| A-12 | Two files with the same content at different paths | Both tracked under different names; one blob object |
| A-13 | `git add .` in an empty directory | No crash; nothing staged; status shows clean |
| A-14 | `git commit` when index has a file that was deleted from disk | Status shows as deleted; commit succeeds with the staged snapshot |
| A-15 | Branch name with a slash: `feature/my-thing` | Ref stored correctly in `refs/heads/feature/my-thing` |
| A-16 | `git diff` on a file with no trailing newline | Diff output is correct; no phantom newline diff |
| A-17 | `git merge` a branch that is an ancestor of current HEAD | "Already up to date." — no regression |
| A-18 | `git stash pop` when stash changes conflict with working tree | Conflict markers written; non-zero exit with message |
| A-19 | Two simultaneous `git add` processes (race) | At minimum: no crash; repository not permanently corrupted |
| A-20 | `git log -n 0` | Prints nothing (not an error) |

### Scoring Formula

```
adversarial_score = (passing_adversarial_tests / 20) * 100
```

---

## 3. Extension Readiness (10%)

### Method

After the agent submits its initial implementation, the runner issues a second prompt (the "extension prompt") asking the agent to add one new feature. The agent has 15 minutes of additional interaction. The feature is then tested with a new test suite.

### Extension Prompt

```
The mini-git implementation now needs to support a `mini-git tag <name> [commit]`
command that creates a lightweight tag: a ref stored in .git/refs/tags/<name>
pointing to the specified commit (or HEAD if omitted). Also add:
- `mini-git tag` (no args): list all tags alphabetically
- `mini-git tag -d <name>`: delete a tag
- In `mini-git log`, show tags alongside commits (format: "tag: <name>")

Write tests for the new functionality.
```

### Extension Tests

| ID | Test |
|----|------|
| E-01 | `tag <name>` creates `.git/refs/tags/<name>` pointing to HEAD |
| E-02 | `tag <name> <sha1>` creates tag pointing to specified commit |
| E-03 | `tag` lists all tags alphabetically |
| E-04 | `tag -d <name>` removes the tag ref |
| E-05 | `log` output shows tag annotations next to tagged commits |
| E-06 | Duplicate tag name is rejected with error |
| E-07 | Agent's own tests for tags pass |

### Scoring Formula

```
extension_score = (passing_extension_tests / 7) * 100
                * (1 if agent also wrote tests, else 0.8)
```

N/A if agent did not produce a working Tier 1 implementation (functional_score < 40).

---

## 4. Mutation Kill Rate (10%)

### Method

Automated mutation testing is run against the agent's own test suite. The runner uses `mutmut` (Python) or `cargo-mutants` (Rust) or equivalent, generating at minimum 50 mutants from the implementation code. The agent's tests are run against each mutant.

### Mutant Categories Generated

| Category | Example Mutation |
|----------|-----------------|
| SHA1 computation | Remove the type header from the hash input |
| Object write | Skip zlib compression |
| Tree sort order | Do not sort tree entries |
| Ref update | Write ref before writing objects (atomicity violation) |
| Parent linking | Always set parent to None |
| Index update | Do not update index after `git add` |
| Exit codes | Always exit 0 |

### Scoring Formula

```
mutation_kill_rate = killed_mutants / total_mutants

mutation_score = mutation_kill_rate * 100
```

N/A if the agent produced fewer than 5 test functions. In that case, mutation testing weight is redistributed.

Partial credit: if fewer than 50 mutants are generated (e.g., implementation is too short to generate sufficient mutants), score = `(killed / generated) * 100` with a maximum of 80 (implementation is too small to fully score).

---

## 5. Performance (15%)

### Method

Each benchmark is run 5 times. The p95 latency (4th of 5 sorted measurements) is compared to the target. Results are measured on CI runner hardware.

### Benchmark Definitions

| ID | Benchmark | Setup | Target | Notes |
|----|-----------|-------|--------|-------|
| P-01 | `git log` deep history | 10,000-commit linear chain | < 2.0s | Repo pre-seeded by harness |
| P-02 | `git add .` many small files | 100,000 files × 1 KB | < 30s | Repo pre-seeded by harness |
| P-03 | `git add .` fewer large files | 1,000 files × 1 MB | < 60s | Repo pre-seeded by harness |
| P-04 | `git status` large tree | 100,000 file working tree, 50% modified | < 10s | |
| P-05 | `git diff` between commits | 10,000 file tree, 1,000 changed files | < 5s | |
| P-06 | `git commit` bulk | 100,000 staged files | < 30s | |
| P-07 | Object read latency | Single 10 KB blob, cold page cache | < 50ms | |

### Scoring Formula

```
For each benchmark:
  if p95 <= target:         sub_score = 100
  elif p95 <= 2 * target:   sub_score = 50 * (2 - p95/target)
  else:                     sub_score = 0

performance_score = mean(sub_scores for all applicable benchmarks)
```

N/A for a specific benchmark if the relevant command is not implemented.

---

## 6. Reliability (10%)

### Method

The runner executes chaos scenarios that simulate system-level failures. Each scenario is run 3 times; all 3 must pass.

### Chaos Scenarios

| ID | Scenario | Pass Criterion |
|----|---------|----------------|
| R-01 | SIGTERM sent during `git add` of 10,000 files | Repository is in a valid state afterwards; no corrupt objects |
| R-02 | SIGTERM sent during `git commit` after all objects written but before ref update | Repository is in a valid state; either commit succeeded or HEAD unchanged |
| R-03 | Disk full simulation (fill disk during object write) | Process exits non-zero with an I/O error message; does not corrupt existing objects |
| R-04 | Object file corrupted (random byte flip) then `git log` | Error detected and reported; process exits non-zero |
| R-05 | Object file corrupted then `git checkout` | Same: error detected and reported |
| R-06 | `.git/index` truncated mid-write | Next `git status` detects and reports invalid index; does not crash |
| R-07 | `git commit` in a repo with 0 bytes disk space | Non-zero exit with helpful message |

### Scoring Formula

```
reliability_score = (passing_chaos_scenarios / 7) * 100
```

---

## 7. Code Quality (10%)

### Method

A panel of LLM judges scores the implementation against the qualitative rubric defined in `judge/rubric.md`. Three judges score independently. Final score is the average.

The judge rubric covers five dimensions (each 0–100). The code quality score is the average of the five judge dimension scores.

See `harnesses/mini-git/judge/rubric.md` for complete judging instructions.

---

## 8. Not Applicable (N/A) Handling

A dimension is N/A when the scoring method cannot be applied due to missing agent output.

| Condition | Affected Dimension | Treatment |
|-----------|--------------------|-----------|
| Agent produced < 5 test functions | Mutation kill rate (D4) | Weight redistributed proportionally to D1, D2, D3 |
| Agent produced no working Tier 1 | Extension readiness (D3) | Weight redistributed to D1 |
| A specific command not implemented | Relevant performance benchmarks (D5 sub-tests) | Only applicable sub-tests averaged |
| Agent produced no code at all | All dimensions except D7 | D7 scores 0; other weights collapse to D7 |

Redistributed weight formula:
```
new_weight_i = weight_i + (na_weight * weight_i / sum_of_applicable_weights)
```

---

## 9. Final Score Example

Suppose an agent scores:

| Dimension | Raw Score | Weight | Contribution |
|-----------|-----------|--------|--------------|
| Functional completeness | 82 | 30% | 24.6 |
| Adversarial survival | 65 | 15% | 9.75 |
| Extension readiness | 71 | 10% | 7.1 |
| Mutation kill rate | 55 | 10% | 5.5 |
| Performance | 90 | 15% | 13.5 |
| Reliability | 43 | 10% | 4.3 |
| Code quality | 78 | 10% | 7.8 |
| **Total** | | **100%** | **72.55** |

Final score: **72.55 / 100**

---

## 10. Score Reporting

The runner outputs a JSON score report:

```json
{
  "harness": "mini-git",
  "harness_version": "1.0.0",
  "run_id": "{uuid}",
  "agent_id": "{agent-identifier}",
  "timestamp": "{iso8601}",
  "dimensions": {
    "functional_completeness": {
      "raw_score": 82.0,
      "weight": 0.30,
      "tier_scores": { "tier1": 95.0, "tier2": 73.3, "tier3": 60.0 },
      "passing_tests": 38,
      "total_tests": 47
    },
    "adversarial_survival": {
      "raw_score": 65.0,
      "weight": 0.15,
      "passing_tests": 13,
      "total_tests": 20
    },
    "extension_readiness": {
      "raw_score": 71.0,
      "weight": 0.10,
      "agent_wrote_tests": true
    },
    "mutation_kill_rate": {
      "raw_score": 55.0,
      "weight": 0.10,
      "killed": 44,
      "total": 80,
      "applicable": true
    },
    "performance": {
      "raw_score": 90.0,
      "weight": 0.15,
      "benchmarks": {
        "P-01": { "p95_seconds": 1.2, "target": 2.0, "sub_score": 100 },
        "P-02": { "p95_seconds": 28.0, "target": 30.0, "sub_score": 100 }
      }
    },
    "reliability": {
      "raw_score": 43.0,
      "weight": 0.10,
      "passing": 3,
      "total": 7
    },
    "code_quality": {
      "raw_score": 78.0,
      "weight": 0.10,
      "judge_scores": [75, 81, 78],
      "dimensions": {
        "plumbing_porcelain_separation": 80,
        "object_model_abstraction": 85,
        "naming_consistency": 70,
        "test_quality": 72,
        "scope_discipline": 83
      }
    }
  },
  "total_score": 72.55
}
```

---

*Rubric version 1.0.0. Last updated: 2026-03-10.*
