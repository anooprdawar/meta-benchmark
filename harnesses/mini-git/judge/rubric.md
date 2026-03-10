# Mini-Git: LLM Judge Rubric

**Harness ID:** mini-git
**Rubric Type:** Qualitative (Code Quality Dimension)
**Version:** 1.0.0

---

## Overview

This rubric is used by LLM judges to assess the code quality of a mini-git implementation. Three judges score independently; scores are averaged. The code quality score is one of seven dimensions in the overall mini-git scoring rubric (weight: 10% of final score).

**Do not look at test pass rates or benchmark results when scoring.** This rubric is about the quality of the implementation's design and code, not its correctness. An implementation that passes all tests can still score poorly on code quality, and vice versa.

---

## Scoring Scale

Each dimension is scored **0 to 100** in increments of at most 5 points. Anchors are provided at 0, 25, 50, 75, and 100. Use your judgment to interpolate.

The **code quality score** is the unweighted average of all five dimension scores.

---

## Dimension 1: Plumbing vs. Porcelain Separation

**What this measures:** Real git has a clean separation between "plumbing" (low-level object manipulation: `hash-object`, `cat-file`, `update-index`, `write-tree`, `commit-tree`) and "porcelain" (user-facing commands: `add`, `commit`, `status`). Porcelain commands are thin orchestration layers over plumbing. This separation makes the system easier to understand, test, and extend.

**What to look for:**

Examine how `git add`, `git commit`, and `git checkout` are implemented. Are they written as a sequence of calls to lower-level functions (e.g., `write_blob(data)`, `write_tree(entries)`, `write_commit(tree, parent, message)`)? Or is all the SHA1 hashing, file writing, and ref manipulation inlined directly in the command handler?

**Scoring Anchors:**

| Score | Description |
|-------|-------------|
| **0** | No separation whatsoever. All SHA1 computation, zlib compression, file writing, and ref manipulation is inlined directly in command handler functions. A single `do_commit()` function is 200+ lines of mixed I/O and hashing. Adding a new command requires copy-pasting file manipulation code. |
| **25** | Some helper functions exist but are ad hoc. For example, there's a `compute_sha1(content)` helper, but tree building, object writing, and ref updating are all inlined in command handlers. The separation is incidental, not architectural. |
| **50** | Object writing is factored out into dedicated functions (`write_object`, `read_object`) that command handlers call. However, tree construction logic or ref manipulation is still inlined in commands. The plumbing/porcelain distinction exists for object I/O but not for higher-level primitives. |
| **75** | Clear separation exists. There is an identifiable plumbing layer (object read/write, index read/write, ref read/write) and command handlers are thin orchestrators that call these functions. You could test the plumbing layer independently. Some minor violations (e.g., one command handler directly opens an object file) but overall the structure is sound. |
| **100** | Excellent separation. There is a well-defined plumbing API (functions or class methods) that handles all storage concerns. Command handlers contain no file I/O directly — they only call plumbing functions. The plumbing layer is independently unit-testable. New commands could be added by composing existing plumbing functions without touching storage code. |

---

## Dimension 2: Object Model Abstraction Quality

**What this measures:** The quality of the abstraction for the three object types (Blob, Tree, Commit). Is there a clean representation for each object type, or is SHA1 hashing and serialization logic scattered throughout the codebase?

**What to look for:**

Look for how Blob, Tree, and Commit objects are represented in code. Is there a class, struct, or module for each? Is serialization logic (the `{type} {len}\0{content}` format) centralized in one place? Can you call something like `Blob(content).sha1` without knowing the serialization format? Or does every call site that needs a SHA1 have to construct the header string itself?

**Scoring Anchors:**

| Score | Description |
|-------|-------------|
| **0** | No abstraction. The string `"blob "` is concatenated with content in multiple places throughout the codebase. Tree entry serialization (`mode + " " + name + "\0" + raw_sha1`) is duplicated. There is no single place where you can find "this is how a Commit is serialized." |
| **25** | There are helper functions like `make_blob_object(data)` and `make_commit_object(tree, parent, message)` but they return raw bytes without providing a way to work with objects as first-class values. The abstraction is a bag of serializers, not a model. |
| **50** | There is some structure — perhaps a dictionary-based representation of each object type — but the abstraction leaks. For example, commit parsing and serialization are in different locations, or tree entry sort order is enforced at the call site rather than inside the Tree abstraction. |
| **75** | Clean class or module-level abstraction for each object type. Blob, Tree, and Commit have `serialize()` / `deserialize()` methods (or equivalent). SHA1 is computed from the serialized form and cached. Tree sorting is handled inside the Tree abstraction. A few minor leaks (e.g., the object read path reconstructs the header outside the class) but overall quality is high. |
| **100** | Excellent abstraction. Each object type is a clean, self-contained unit with: (a) a structured in-memory representation, (b) a `from_bytes()` / `deserialize()` classmethod, (c) a `to_bytes()` / `serialize()` method, (d) a `sha1` property computed from serialized form. The object store (read/write) accepts these objects. SHA1 logic does not appear outside the object classes. Tree entries are sorted internally. The object model is easy to navigate and extend. |

---

## Dimension 3: Naming and Pattern Consistency

**What this measures:** Whether the codebase uses consistent naming conventions, consistent patterns for similar operations, and coherent variable names across files.

**What to look for:**

Read through multiple command handlers and the storage layer. Do similar operations use similar naming patterns? For example, if `git add` uses `object_path = os.path.join(objects_dir, sha[:2], sha[2:])`, does `git checkout` use the same pattern — or does it recompute the path differently? Are variable names that refer to the same concept always the same (e.g., always `commit_sha`, never sometimes `commit_sha`, sometimes `sha`, sometimes `hash_str`)? Are command handler functions named consistently (e.g., `cmd_add`, `cmd_commit`, `cmd_log` — or a mix of conventions)?

**Scoring Anchors:**

| Score | Description |
|-------|-------------|
| **0** | Pervasive inconsistency. Object paths are computed three different ways in three files. Variables named `sha`, `hash_val`, `obj_hash`, `digest`, and `sha1_hex` all refer to the same concept in different parts of the code. Command handlers use completely different structural patterns. Reading the code is disorienting. |
| **25** | Some consistency within files, but cross-file inconsistency is common. The storage module uses one naming convention; the command module uses another. Similar patterns are reinvented for each command. |
| **50** | Naming is mostly consistent within modules. A few cross-module inconsistencies are present (e.g., `sha1` in one place vs. `object_hash` in another). Command handlers follow roughly the same pattern but with some variation. The code is readable with some mental adjustment. |
| **75** | High consistency. Naming conventions are uniform across files. Similar operations (e.g., reading a ref, writing a ref) use the same function signatures and return types everywhere. A few minor inconsistencies but they do not impede readability. |
| **100** | Excellent consistency. A developer can read one command handler and immediately understand the pattern for all others. Variable names for the same concept are identical everywhere. Helper functions for common operations are defined once and used consistently. The codebase has a coherent "voice." |

---

## Dimension 4: Test Quality and Coverage Intent

**What this measures:** Whether the agent's tests are substantive — testing real behavior rather than trivially passing assertions — and whether they cover edge cases and failure modes in addition to the happy path.

**What to look for:**

Read the test file(s). Count how many tests exist. For each test, ask: does this test verify something that could realistically be broken by a bug? Or is it a smoke test that would pass even with a half-broken implementation?

Look for: tests that verify the SHA1 of written objects, tests that verify the structure of written tree objects, tests that check error messages (not just exit codes), tests for empty repositories, tests for binary files, tests that check what happens when the index is modified between add and commit.

Penalize: tests that only check exit code 0, tests that only verify a file exists (without checking its content), tests with no assertions.

**Scoring Anchors:**

| Score | Description |
|-------|-------------|
| **0** | No tests, or tests exist but make no assertions (e.g., `def test_init(): subprocess.run(["mini-git", "init"])`). Tests that run the binary but check nothing meaningful. |
| **25** | Tests exist and make some assertions (file existence, exit code 0), but no test verifies actual content correctness. No edge cases tested. All tests are happy-path. A naive implementation that always exits 0 and creates `.git/HEAD` would pass most tests. |
| **50** | Happy-path tests are solid: they verify commit SHA1s, verify object file existence, verify status output text. However, edge cases are largely untested: no binary file test, no empty file test, no error condition tests, no adversarial inputs. |
| **75** | Good test coverage. Happy paths and most error conditions are tested. At least 3-5 edge cases are covered (empty files, files with spaces in names, empty repo operations, corrupt index, etc.). Tests verify content, not just existence. Test organization is clear. |
| **100** | Excellent tests. Every command has happy-path tests AND error condition tests. Adversarial inputs are tested (binary files, unicode filenames, very long commit messages, corrupt objects). Tests verify SHA1 correctness for blob and commit objects. Object round-trips are tested (write then read then compare). Tests are well-named, well-organized, and each test asserts exactly one behavior. |

---

## Dimension 5: Scope Discipline

**What this measures:** Whether the agent built exactly what was asked — no feature creep (building things not requested), no scope skipping (implementing a subset and calling it done), and no gold-plating (over-engineering what should be simple).

**What to look for:**

Compare the implementation to the prompt. Did the agent implement features that were explicitly out of scope (networking, hooks, packfiles, config file parsing beyond what's needed)? Did the agent skip any clearly requested feature without explanation? Did the agent spend significant effort on infrastructure that wasn't requested (e.g., a full plugin system, a REST API, a GUI)?

Also look for: did the agent explicitly call out what it did and didn't implement? An agent that says "I implemented Tier 1 and Tier 2 but not Tier 3, here's why" is exercising good scope discipline even if Tier 3 is missing. An agent that silently omits features is not.

**Scoring Anchors:**

| Score | Description |
|-------|-------------|
| **0** | Severe scope violation. Either: (a) the agent built something completely different from what was asked, or (b) the agent implemented less than 50% of the requested commands with no explanation, or (c) the agent spent the majority of effort on out-of-scope infrastructure (e.g., a full networking stack). |
| **25** | Significant scope issues. Multiple out-of-scope features implemented (e.g., `git remote`, `git fetch`, `git rebase`) that are clearly out of scope, OR multiple explicitly requested features are missing with no acknowledgment. |
| **50** | Mostly on-scope. One or two out-of-scope features implemented (minor), OR one clearly-requested feature is missing but the rest is complete. The agent may have mentioned the missing feature. |
| **75** | Good scope discipline. All requested features are present (or their absence is explicitly noted with a reasonable explanation). No significant out-of-scope features. Possibly one small extra (e.g., a `--verbose` flag on `log`) that doesn't detract from the core implementation. |
| **100** | Excellent scope discipline. Every feature requested in the prompt is implemented. No unrequested features are implemented. The agent's README accurately describes what is and isn't implemented. Where Tier 3 features are missing, this is noted explicitly. The implementation solves exactly the problem posed, no more and no less. |

---

## Judge Instructions

### How to Score

1. Read the implementation fully before scoring any dimension. Do not score as you read — form a holistic view first.
2. Score each dimension independently. Your score for Dimension 1 should not influence your score for Dimension 4.
3. Use the anchors as reference points, not as a checklist. A score of 75 does not require meeting every criterion listed in the 75 anchor — it means the implementation is at approximately that quality level.
4. If you are uncertain between two scores (e.g., 50 vs. 75), pick the midpoint (62 or 63) rather than defaulting to the higher or lower.
5. Provide a brief (2-4 sentence) justification for each dimension score. The justification should cite specific evidence from the code (e.g., "The `cmd_commit` handler directly calls `zlib.compress` rather than delegating to the object store — a plumbing violation.").

### How to Handle Uncertainty

- **Missing implementation:** If a feature is missing, score Dimension 5 (scope discipline) lower. Do not score other dimensions lower just because a feature is missing — evaluate the quality of what was built.
- **Language you don't know well:** If the implementation is in a language you're less familiar with, focus on structural patterns (separation of concerns, consistent naming) that are language-agnostic. Do not penalize idiomatic language features.
- **Very short implementations:** A 200-line implementation that cleanly implements Tier 1 can still score 100 on all dimensions if the code is excellent. Length is not quality.
- **Auto-generated code:** If the implementation appears to be copied from real git's source or generated from templates, score Dimension 3 (naming consistency) and Dimension 5 (scope discipline) lower, and note your concern in the justification.

### Weighting

All five dimensions are weighted equally within the code quality score:

```
code_quality_score = (D1 + D2 + D3 + D4 + D5) / 5
```

Do not apply your own weighting — if you think Dimension 2 matters more than Dimension 4, that is noted for future rubric revisions, but do not adjust weights unilaterally.

### Output Format

Return your scores in the following JSON format:

```json
{
  "judge_id": "your-identifier",
  "harness": "mini-git",
  "dimensions": {
    "plumbing_porcelain_separation": {
      "score": 75,
      "justification": "..."
    },
    "object_model_abstraction": {
      "score": 80,
      "justification": "..."
    },
    "naming_consistency": {
      "score": 60,
      "justification": "..."
    },
    "test_quality": {
      "score": 50,
      "justification": "..."
    },
    "scope_discipline": {
      "score": 90,
      "justification": "..."
    }
  },
  "overall_code_quality": 71.0,
  "notes": "Any cross-cutting observations that don't fit a single dimension."
}
```

---

*Judge rubric version 1.0.0. Last updated: 2026-03-10.*
