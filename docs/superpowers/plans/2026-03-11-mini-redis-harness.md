# mini-redis Harness Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a complete mini-redis harness to meta-benchmark, including all harness docs, test suite, and scorer generalization to support multiple harnesses.

**Architecture:** Generalize the scorer's hardcoded `MINI_GIT_CMD` references to derive env var names from harness names dynamically. Then create the mini-redis harness following the exact same directory structure as mini-git.

**Tech Stack:** Python 3.10+, pytest, JSON persistence, subprocess-based test harness

---

## Chunk 1: Scorer Generalization

### Task 1: Generalize scorer/behavioral.py

**Files:**
- Modify: `scorer/behavioral.py`

The scorer hardcodes `MINI_GIT_CMD` and mini_git filenames. We need to derive these from the harness name.

- [ ] **Step 1: Read the current file**

Run: `cat scorer/behavioral.py`

- [ ] **Step 2: Apply changes to behavioral.py**

Replace the `_find_mini_git_cmd` function and update `run_behavioral` and `_run_pytest_tier`:

```python
# Add these two new functions after the imports, before _find_mini_git_cmd:

def _harness_cmd_var(harness_name: str) -> str:
    """Derive env var name from harness name. 'mini-redis' → 'MINI_REDIS_CMD'."""
    return harness_name.upper().replace("-", "_") + "_CMD"


def _find_cmd(workspace: Path, harness_name: str) -> list[str]:
    """Find the CLI entry point for any harness in the workspace directory."""
    workspace = workspace.resolve()
    stem = harness_name.replace("-", "_")  # e.g. "mini_redis"
    candidates = [
        workspace / f"{stem}.py",
        workspace / f"{harness_name}.py",
        workspace / stem / "__main__.py",
        workspace / "src" / f"{stem}.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return [sys.executable, str(candidate)]
    for name in [stem, harness_name]:
        binary = workspace / name
        if binary.exists() and binary.stat().st_mode & 0o111:
            return [str(binary)]
    return [sys.executable, str(workspace / f"{stem}.py")]


def _find_mini_git_cmd(workspace: Path) -> list[str]:
    """Backwards-compat alias — delegates to _find_cmd."""
    return _find_cmd(workspace, "mini-git")
```

Update `run_behavioral` to use the harness name:

```python
def run_behavioral(
    submission_path: Path,
    harness_path: Path,
    python: str = sys.executable,
    timeout: int = 300,
) -> BehavioralResult:
    submission_path = Path(submission_path)
    harness_path = Path(harness_path)
    tests_root = harness_path / "tests"
    harness_name = harness_path.name
    cmd_var = _harness_cmd_var(harness_name)
    impl_cmd = _find_cmd(submission_path / "workspace", harness_name)

    tier_results: dict[str, TierResult] = {}
    for tier_name, weight in TIER_WEIGHTS.items():
        tier_path = tests_root / tier_name
        if not tier_path.exists():
            continue
        result = _run_pytest_tier(
            tier_path=tier_path,
            tests_root=tests_root,
            impl_cmd=impl_cmd,
            cmd_var=cmd_var,
            python=python,
            timeout=timeout,
        )
        tier_results[tier_name] = result

    weighted_score = sum(
        r.score * TIER_WEIGHTS.get(name, 0)
        for name, r in tier_results.items()
    )
    total_passed = sum(r.passed for r in tier_results.values())
    total_tests = sum(r.total for r in tier_results.values())
    return BehavioralResult(
        tier_results=tier_results,
        weighted_score=round(weighted_score, 2),
        total_passed=total_passed,
        total_tests=total_tests,
    )
```

Update `_run_pytest_tier` signature (rename `mini_git_cmd` → `impl_cmd`, add `cmd_var`):

```python
def _run_pytest_tier(
    tier_path: Path,
    tests_root: Path,
    impl_cmd: list[str],
    cmd_var: str = "MINI_GIT_CMD",
    python: str,
    timeout: int,
    # Keep old kwarg name as alias for callers that haven't updated yet
    mini_git_cmd: list[str] | None = None,
) -> TierResult:
    if mini_git_cmd is not None:
        impl_cmd = mini_git_cmd  # backwards compat
    tier_name = tier_path.name
    cmd = [
        python, "-m", "pytest",
        str(tier_path),
        "--tb=short",
        "--json-report",
        f"--json-report-file=/tmp/bench_{tier_name}.json",
        "-q",
        "--timeout=30",
        f"--rootdir={tests_root}",
    ]
    env_extra = {cmd_var: " ".join(impl_cmd)}
    import os
    env = {**os.environ, **env_extra}
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=env,
        )
    except subprocess.TimeoutExpired:
        return TierResult(
            tier=tier_name, passed=0, failed=0, errors=1, skipped=0,
            total=0, score=0.0,
            failures=[{"test": "timeout", "message": f"Tier timed out after {timeout}s"}],
        )
    report_file = Path(f"/tmp/bench_{tier_name}.json")
    if report_file.exists():
        try:
            report = json.loads(report_file.read_text())
            return _parse_json_report(tier_name, report)
        except (json.JSONDecodeError, KeyError):
            pass
    return _parse_pytest_stdout(tier_name, proc.stdout)
```

- [ ] **Step 3: Verify no syntax errors**

Run: `python -c "from scorer.behavioral import run_behavioral, _find_cmd, _harness_cmd_var; print('OK')"`
Expected: `OK`

---

### Task 2: Generalize scorer/adversarial.py

**Files:**
- Modify: `scorer/adversarial.py`

- [ ] **Step 1: Update import and run_adversarial**

Change line 14 import from:
```python
from scorer.behavioral import _find_mini_git_cmd, _run_pytest_tier, TierResult
```
to:
```python
from scorer.behavioral import _find_cmd, _harness_cmd_var, _run_pytest_tier, TierResult
```

Replace the body of `run_adversarial` to derive harness name:

```python
def run_adversarial(
    submission_path: Path,
    harness_path: Path,
    python: str = sys.executable,
    timeout: int = 300,
) -> AdversarialResult:
    submission_path = Path(submission_path)
    harness_path = Path(harness_path)
    tests_root = harness_path / "tests"
    adversarial_path = tests_root / "adversarial"
    harness_name = harness_path.name
    cmd_var = _harness_cmd_var(harness_name)

    if not adversarial_path.exists():
        return AdversarialResult(passed=0, failed=0, total=0, survival_rate=0.0, score=0.0)

    impl_cmd = _find_cmd(submission_path / "workspace", harness_name)

    public_result: TierResult = _run_pytest_tier(
        tier_path=adversarial_path,
        tests_root=tests_root,
        impl_cmd=impl_cmd,
        cmd_var=cmd_var,
        python=python,
        timeout=timeout,
    )

    passed = public_result.passed
    total = public_result.total
    failures = public_result.failures
    held_out_passed = 0
    held_out_total = 0
    verified = False

    held_out_path = tests_root / "held-out"
    if held_out_path.exists() and any(held_out_path.glob("test_*.py")):
        ho_result: TierResult = _run_pytest_tier(
            tier_path=held_out_path,
            tests_root=tests_root,
            impl_cmd=impl_cmd,
            cmd_var=cmd_var,
            python=python,
            timeout=timeout,
        )
        held_out_passed = ho_result.passed
        held_out_total = ho_result.total
        passed += ho_result.passed
        total += ho_result.total
        failures = failures + ho_result.failures
        verified = True
        print(f"  [held-out] {ho_result.passed}/{ho_result.total} additional adversarial tests passed")

    survival_rate = (passed / total * 100) if total > 0 else 0.0
    return AdversarialResult(
        passed=passed, failed=total - passed, total=total,
        survival_rate=round(survival_rate, 2), score=round(survival_rate, 2),
        held_out_passed=held_out_passed, held_out_total=held_out_total,
        verified=verified, failures=failures,
    )
```

- [ ] **Step 2: Verify**

Run: `python -c "from scorer.adversarial import run_adversarial; print('OK')"`

---

### Task 3: Generalize scorer/extension.py and scorer/reliability.py

**Files:**
- Modify: `scorer/extension.py`
- Modify: `scorer/reliability.py`

- [ ] **Step 1: Update extension.py**

Change import:
```python
from scorer.behavioral import _find_cmd, _harness_cmd_var, _run_pytest_tier
```

Update `run_extension` to derive harness name (replace the two `_find_mini_git_cmd` calls):
```python
    harness_name = harness_path.name
    cmd_var = _harness_cmd_var(harness_name)
    # ... (where agent.extend() is called:)
    impl_cmd = _find_cmd(workspace_path, harness_name)
    tier_result = _run_pytest_tier(
        tier_path=extension_path,
        tests_root=tests_root,
        impl_cmd=impl_cmd,
        cmd_var=cmd_var,
        python=python,
        timeout=timeout,
    )
```

- [ ] **Step 2: Update reliability.py**

Change import:
```python
from scorer.behavioral import _find_cmd, _harness_cmd_var, _run_pytest_tier
```

Update `run_reliability`:
```python
    harness_name = harness_path.name
    cmd_var = _harness_cmd_var(harness_name)
    impl_cmd = _find_cmd(submission_path / "workspace", harness_name)
    tier_result = _run_pytest_tier(
        tier_path=reliability_path,
        tests_root=tests_root,
        impl_cmd=impl_cmd,
        cmd_var=cmd_var,
        python=python,
        timeout=timeout,
    )
```

- [ ] **Step 3: Verify both**

Run: `python -c "from scorer.extension import run_extension; from scorer.reliability import run_reliability; print('OK')"`

---

### Task 4: Generalize scorer/performance.py and update mini-git thresholds.json

**Files:**
- Modify: `scorer/performance.py`
- Modify: `harnesses/mini-git/tests/performance/thresholds.json`

- [ ] **Step 1: Add `file` field to mini-git thresholds.json**

Update `harnesses/mini-git/tests/performance/thresholds.json` to add a `"file"` field to each benchmark entry:

```json
{
  "_comment": "Performance thresholds for mini-git. Measured on 4-core x86 CPU with SSD storage.",
  "_scoring": "Score = 100 if p95 <= target_p95. Score = 0 if p95 >= fail_p95. Linear interpolation between.",
  "benchmarks": {
    "log_10k_commits": {
      "file": "bench_log.py",
      "description": "git log on a repo with 10,000 commits",
      "target_p95_seconds": 2.0,
      "fail_p95_seconds": 10.0,
      "weight": 0.30
    },
    "add_100k_files": {
      "file": "bench_add.py",
      "description": "git add . on a working tree with 100,000 small files",
      "target_p95_seconds": 30.0,
      "fail_p95_seconds": 120.0,
      "weight": 0.25
    },
    "diff_1k_changed_files": {
      "file": "bench_diff.py",
      "description": "git diff across 1,000 changed files",
      "target_p95_seconds": 1.0,
      "fail_p95_seconds": 5.0,
      "weight": 0.20
    },
    "merge_deep_diverge": {
      "file": "bench_merge.py",
      "description": "git merge of branches with 500 commits divergence on each side",
      "target_p95_seconds": 5.0,
      "fail_p95_seconds": 30.0,
      "weight": 0.15
    },
    "status_large_repo": {
      "description": "git status on repo with 10,000 files (1,000 modified)",
      "target_p95_seconds": 2.0,
      "fail_p95_seconds": 10.0,
      "weight": 0.10
    }
  }
}
```

> **Note on `status_large_repo`:** This entry has no `"file"` field — the updated performance scorer skips entries without `"file"`. Its weight (0.10) is therefore excluded from scoring and the weighted total will be 0.90, slightly inflating the score by ~11%. This is intentional: `bench_status.py` is out of scope for this harness since mini-git's status doesn't need a dedicated bench file at this time. When/if added, include `"file": "bench_status.py"` here.

- [ ] **Step 2: Update performance.py**

Change import:
```python
from scorer.behavioral import _find_cmd, _harness_cmd_var
```

Replace the body of `run_performance`:

```python
def run_performance(
    submission_path: Path,
    harness_path: Path,
    python: str = sys.executable,
    timeout: int = 600,
) -> PerformanceResult:
    submission_path = Path(submission_path)
    harness_path = Path(harness_path)
    harness_name = harness_path.name
    cmd_var = _harness_cmd_var(harness_name)
    tests_root = harness_path / "tests"
    perf_path = tests_root / "performance"
    thresholds_file = perf_path / "thresholds.json"

    if not perf_path.exists() or not thresholds_file.exists():
        return PerformanceResult(
            benchmark_results={}, weighted_score=0.0,
            notes="Performance test directory not found.",
        )

    thresholds = json.loads(thresholds_file.read_text())["benchmarks"]
    impl_cmd = _find_cmd(submission_path / "workspace", harness_name)

    # Discover bench files from thresholds.json "file" field
    bench_files = {
        key: perf_path / thresh["file"]
        for key, thresh in thresholds.items()
        if "file" in thresh
    }

    results: dict[str, BenchmarkResult] = {}
    total_weight = 0.0
    weighted_sum = 0.0

    for bench_name, bench_file in bench_files.items():
        thresh = thresholds[bench_name]
        weight = thresh["weight"]
        if not bench_file.exists():
            result = BenchmarkResult(
                name=bench_name, p50=0, p95=0, p99=0,
                target_p95=thresh["target_p95_seconds"],
                fail_p95=thresh["fail_p95_seconds"],
                score=0.0, skipped=True, skip_reason="Benchmark file not found",
            )
        else:
            result = _run_benchmark(
                bench_file=bench_file,
                bench_name=bench_name,
                harness_tests_root=tests_root,
                impl_cmd=impl_cmd,
                cmd_var=cmd_var,
                thresh=thresh,
                python=python,
                timeout=timeout,
            )
        results[bench_name] = result
        total_weight += weight
        weighted_sum += result.score * weight

    weighted_score = (weighted_sum / total_weight) if total_weight > 0 else 0.0
    return PerformanceResult(
        benchmark_results=results,
        weighted_score=round(weighted_score, 2),
    )
```

Update `_run_benchmark` signature to accept `cmd_var`:
```python
def _run_benchmark(
    bench_file: Path,
    bench_name: str,
    harness_tests_root: Path,
    impl_cmd: list[str],
    cmd_var: str,
    thresh: dict,
    python: str,
    timeout: int,
    # backwards compat
    mini_git_cmd: list[str] | None = None,
) -> BenchmarkResult:
    if mini_git_cmd is not None:
        impl_cmd = mini_git_cmd
    import os, time
    cmd = [
        python, "-m", "pytest", str(bench_file),
        "-v", "--tb=short",
        f"--rootdir={harness_tests_root}",
        "--timeout=300", "-s",
    ]
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, cmd_var: " ".join(impl_cmd)},
        )
        elapsed = time.perf_counter() - start
    except subprocess.TimeoutExpired:
        return BenchmarkResult(
            name=bench_name, p50=timeout, p95=timeout, p99=timeout,
            target_p95=thresh["target_p95_seconds"],
            fail_p95=thresh["fail_p95_seconds"],
            score=0.0, skipped=True, skip_reason=f"Timed out after {timeout}s",
        )
    p50, p95, p99 = _extract_timing(proc.stdout + proc.stderr, elapsed)
    score = _compute_score(p95, thresh["target_p95_seconds"], thresh["fail_p95_seconds"])
    return BenchmarkResult(
        name=bench_name, p50=round(p50, 3), p95=round(p95, 3), p99=round(p99, 3),
        target_p95=thresh["target_p95_seconds"],
        fail_p95=thresh["fail_p95_seconds"],
        score=round(score, 2),
    )
```

- [ ] **Step 3: Verify full scorer stack still works for mini-git**

Run: `python -m pytest tests/ -v`
Expected: All 6 scorer unit tests pass.

- [ ] **Step 4: Commit scorer generalization**

```bash
git add scorer/behavioral.py scorer/adversarial.py scorer/extension.py scorer/performance.py scorer/reliability.py harnesses/mini-git/tests/performance/thresholds.json
git commit -m "feat: generalize scorer to support multiple harnesses

Derive MINI_*_CMD env var name and workspace filenames from harness
name at runtime, replacing hardcoded MINI_GIT_CMD references.
Add 'file' field to thresholds.json for bench file discovery."
```

---

## Chunk 2: Harness Scaffolding Docs

### Task 5: Create harnesses/mini-redis/prompt.md

**Files:**
- Create: `harnesses/mini-redis/prompt.md`

- [ ] **Step 1: Create the file**

```markdown
# mini-redis

Build me a Redis-compatible key-value store in a single Python file called `mini_redis.py`.

## What I need

A command-line tool that stores data persistently and supports the following commands.

### Strings (implement first)

- `SET key value` — store a string value; print `OK`
- `GET key` — retrieve a value; print `"value"` or `(nil)` if missing
- `DEL key [key ...]` — delete keys; print `(integer) N` (count deleted)
- `EXISTS key` — print `(integer) 1` if present, `(integer) 0` if not
- `MSET key value [key value ...]` — set multiple keys; print `OK`
- `MGET key [key ...]` — get multiple values in order; missing keys print `(nil)` at position

### Lists

- `LPUSH key value [value ...]` — push to left; print `(integer) N` (new length)
- `RPUSH key value [value ...]` — push to right; print `(integer) N` (new length)
- `LPOP key` — pop from left; print `"value"` or `(nil)` if empty/missing
- `RPOP key` — pop from right; print `"value"` or `(nil)` if empty/missing
- `LRANGE key start stop` — get elements by index; 0-indexed, negatives count from end, stop inclusive

### Hashes

- `HSET key field value [field value ...]` — set fields; print `(integer) N` (new fields added, updates don't count)
- `HGET key field` — get one field; print `"value"` or `(nil)`
- `HDEL key field [field ...]` — delete fields; print `(integer) N` deleted
- `HGETALL key` — print alternating unquoted field/value lines, alphabetical by field name
- `HKEYS key` — print numbered list of field names, alphabetical

### TTL and expiry

- `EXPIRE key seconds` — set expiry in seconds; print `(integer) 1` if key exists, `(integer) 0` if not
- `TTL key` — print `(integer) N` remaining, `(integer) -1` (no TTL), `(integer) -2` (missing)
- `PERSIST key` — remove TTL; print `(integer) 1` if removed, `(integer) 0` otherwise

### Sets

- `SADD key member [member ...]` — add members; print `(integer) N` (new members added)
- `SREM key member [member ...]` — remove members; print `(integer) N` removed
- `SMEMBERS key` — list all members in lexicographic order; print `(empty set)` if empty
- `SISMEMBER key member` — print `(integer) 1` or `(integer) 0`

### Counters

- `INCR key` — increment integer value; print `(integer) N`; missing key starts at 0
- `DECR key` — decrement; print `(integer) N`; missing key starts at 0

## Architecture requirement

The CLI must be a thin shell. All data structure logic must live in a `RedisStore` class (or equivalent). The CLI layer parses arguments and delegates — no business logic in `if __name__ == "__main__"`.

## Data persistence

Store data in a JSON file. Use the `MINI_REDIS_DATA` environment variable for the path; if unset, use `./mini_redis.json` in the current working directory.

After every successful write operation, the store must be fully written to disk (call `fsync` or equivalent) before the process exits. Reads never write to disk.

TTL deadlines are stored as absolute Unix epoch timestamps so they survive process restarts.

## Output format

All output ends with a newline. Exact rules:

- String values: `"value"` — double-quoted. Special chars inside quotes: `"` → `\"`, `\` → `\\`, newline → `\n`
- Integer results: `(integer) N`
- Float scores (ZSCORE): use Python `f"{score:g}"` formatting, then quote: `"1"` or `"1.5"`
- Missing key/member: `(nil)`
- Numbered list: `1) item\n2) item\n...`
- Empty list: `(empty list)`, empty set: `(empty set)`
- HGETALL: alternating unquoted `field\nvalue\nfield\nvalue` lines

## Exit codes and errors

- Exit 0: success
- Exit 1: command error. Print error to stderr, nothing to stdout.
- Exit 2: I/O error

Error messages:
- Unknown command: `ERR unknown command '<cmd>'`
- Wrong arity: `ERR wrong number of arguments for '<cmd>' command`
- Wrong type: `WRONGTYPE Operation against a key holding the wrong kind of value`
- Non-integer INCR/DECR: `ERR value is not an integer or out of range`
- Invalid EXPIRE time: `ERR invalid expire time in 'EXPIRE' command`

## Example session

```
$ python mini_redis.py SET greeting "hello world"
OK
$ python mini_redis.py GET greeting
"hello world"
$ python mini_redis.py LPUSH mylist a b c
(integer) 3
$ python mini_redis.py LRANGE mylist 0 -1
1) "c"
2) "b"
3) "a"
$ python mini_redis.py HSET user name Alice age 30
(integer) 2
$ python mini_redis.py HGETALL user
age
30
name
Alice
$ python mini_redis.py EXPIRE greeting 60
(integer) 1
$ python mini_redis.py TTL greeting
(integer) 59
$ python mini_redis.py SADD tags python redis
(integer) 2
$ python mini_redis.py SMEMBERS tags
1) "python"
2) "redis"
```

## Tests

Write a pytest test suite covering every command's happy path, error conditions, persistence across restarts, and edge cases (empty values, unicode, type errors).
```

- [ ] **Step 2: Verify file exists**

Run: `ls harnesses/mini-redis/prompt.md`

---

### Task 6: Create harnesses/mini-redis/spec.md

**Files:**
- Create: `harnesses/mini-redis/spec.md`

- [ ] **Step 1: Create the file**

```markdown
# mini-redis: Product Requirements Document

**Version:** 1.0.0
**Harness:** mini-redis

---

## 1. Overview

Agents implement a Redis-compatible key-value store as a single Python CLI. The CLI is a thin shell over a `RedisStore` class. Data is persisted to a JSON file. No networking required.

**Success criterion:** A fresh implementation produced from `prompt.md` alone passes ≥ 70% of the behavioral test suite and handles common adversarial inputs gracefully.

---

## 2. Scope

**In scope:** SET/GET/DEL/EXISTS/MSET/MGET, Lists (LPUSH/RPUSH/LPOP/RPOP/LRANGE), Hashes (HSET/HGET/HDEL/HGETALL/HKEYS), TTL (EXPIRE/TTL/PERSIST), Sets (SADD/SREM/SMEMBERS/SISMEMBER), Counters (INCR/DECR), JSON persistence, lazy TTL eviction.

**Out of scope:** Networking, RESP protocol, Pub/Sub, Lua, MULTI/EXEC transactions, `KEYS` glob patterns, streams, `SET` options (NX/XX/EX/PX/GET), `WITHSCORES`.

---

## 3. Interface Contract

### CLI invocation

```
python mini_redis.py COMMAND [arg ...]
```

Arguments are whitespace-delimited shell tokens. Values containing spaces must be quoted by the shell. The implementation receives them as `sys.argv[1:]`.

### Environment variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `MINI_REDIS_DATA` | Path to JSON data file | `./mini_redis.json` |

### Data file

Agent chooses internal JSON schema. File must be valid JSON on every read. If the file does not exist, the store is empty. Partial writes (crash before fsync) are not tested.

### Durability

Every successful mutation must call `os.fsync()` (or equivalent) on the data file before the process exits. Read-only commands must not write the file.

### TTL storage

Deadlines are stored as absolute Unix epoch timestamps (float). On load, expired keys are silently evicted before any command runs.

---

## 4. Output Format Specification

### Global rules

- All stdout ends with exactly one `\n`.
- Tests strip trailing whitespace before comparison.
- On error (exit ≠ 0): stderr contains the error message; stdout is empty.

### Result type → stdout

| Result | stdout |
|--------|--------|
| Successful mutation (no other value) | `OK` |
| String value | `"value"` — double-quoted |
| Integer | `(integer) N` |
| Float score | `f"{score:g}"` formatted, then quoted: `"1"` or `"1.5"` |
| Missing key/member | `(nil)` |
| Non-empty list/array | `1) item\n2) item\n...` (1-indexed) |
| Empty list | `(empty list)` |
| Empty set | `(empty set)` |

**String quoting:** inside double quotes, escape `"` → `\"`, `\` → `\\`, newline → `\n` (two chars).

**HGETALL exception:** alternating unquoted lines: `field1\nvalue1\nfield2\nvalue2\n...`. Alphabetical by field name. If hash is empty or key missing: `(empty list)`.

---

## 5. Command Reference

### Tier 1 — Strings

| Command | stdout on success | Error conditions |
|---------|------------------|-----------------|
| `SET key value` | `OK` | Wrong arity → exit 1 |
| `GET key` | `"value"` or `(nil)` | Wrong arity → exit 1 |
| `DEL key [key ...]` | `(integer) N` (deleted count) | No args → exit 1 |
| `EXISTS key` | `(integer) 1` or `(integer) 0` | Wrong arity → exit 1 |
| `MSET key value [key value ...]` | `OK` | Odd number of args → exit 1 |
| `MGET key [key ...]` | numbered list; `(nil)` at position of missing keys | No args → exit 1 |

### Tier 2 — Lists

| Command | stdout | Notes |
|---------|--------|-------|
| `LPUSH key value [value ...]` | `(integer) N` (new length) | Wrong type → exit 1, WRONGTYPE |
| `RPUSH key value [value ...]` | `(integer) N` | Wrong type → exit 1, WRONGTYPE |
| `LPOP key` | `"value"` or `(nil)` | Wrong type → exit 1 |
| `RPOP key` | `"value"` or `(nil)` | Wrong type → exit 1 |
| `LRANGE key start stop` | numbered list or `(empty list)` | Negative indices from end; stop inclusive; wrong type → exit 1 |

### Tier 2 — Hashes

| Command | stdout | Notes |
|---------|--------|-------|
| `HSET key field value [field value ...]` | `(integer) N` (new fields only) | Wrong type → exit 1 |
| `HGET key field` | `"value"` or `(nil)` | Wrong type → exit 1 |
| `HDEL key field [field ...]` | `(integer) N` deleted | Wrong type → exit 1 |
| `HGETALL key` | alternating field/value lines (alphabetical) or `(empty list)` | Wrong type → exit 1 |
| `HKEYS key` | numbered list of quoted field names (alphabetical) or `(empty list)` | Wrong type → exit 1. Note: field names are string-quoted per the standard list format (`1) "field"`); only `HGETALL` output has unquoted field names. |

### Tier 3 — TTL/Expiry

| Command | stdout | Notes |
|---------|--------|-------|
| `EXPIRE key seconds` | `(integer) 1` or `(integer) 0` | seconds ≤ 0 or non-integer → exit 1, `ERR invalid expire time in 'EXPIRE' command` |
| `TTL key` | `(integer) N` remaining / `(integer) -1` (no TTL) / `(integer) -2` (missing) | |
| `PERSIST key` | `(integer) 1` (TTL removed) / `(integer) 0` (no TTL or missing) | |

### Tier 3 — Sets

| Command | stdout | Notes |
|---------|--------|-------|
| `SADD key member [member ...]` | `(integer) N` (new members) | Wrong type → exit 1 |
| `SREM key member [member ...]` | `(integer) N` removed | Wrong type → exit 1 |
| `SMEMBERS key` | numbered list (lexicographic) or `(empty set)` | Wrong type → exit 1 |
| `SISMEMBER key member` | `(integer) 1` or `(integer) 0` | Wrong type → exit 1 |

### Tier 3 — Counters

| Command | stdout | Notes |
|---------|--------|-------|
| `INCR key` | `(integer) N` | Missing key starts at 0; non-integer value → exit 1 |
| `DECR key` | `(integer) N` | Missing key starts at 0; non-integer value → exit 1 |

---

## 6. Ordering Rules

| Operation | Order |
|-----------|-------|
| LRANGE | Left-to-right insertion order |
| HGETALL, HKEYS | Alphabetical by field name |
| SMEMBERS | Lexicographic |
| MGET | Preserves argument order; missing → `(nil)` |

---

## 7. Error Message Templates

| Condition | stderr |
|-----------|--------|
| Unknown command | `ERR unknown command '<cmd>'` |
| Wrong arity | `ERR wrong number of arguments for '<cmd>' command` |
| Wrong type | `WRONGTYPE Operation against a key holding the wrong kind of value` |
| Non-integer INCR/DECR | `ERR value is not an integer or out of range` |
| Invalid EXPIRE time | `ERR invalid expire time in 'EXPIRE' command` |
| I/O failure | `ERR persistence failure: <reason>` |

---

## 8. Performance Targets

| Benchmark | Target p95 | Fail p95 |
|-----------|-----------|---------|
| GET from 10k-key store | 1.0s | 5.0s |
| LRANGE on 10k-element list | 2.0s | 10.0s |
| HGETALL on 1k-field hash | 1.0s | 5.0s |

---

## 9. Reliability Requirements

1. Data survives a clean process exit (confirmed by subsequent read)
2. Corrupt JSON file: process must exit non-zero with stderr message, not crash with traceback
3. Missing data file: treat as empty store, do not crash
4. EXPIRE deadline persists across process restarts (stored as epoch timestamp)

---

## 10. Architecture Requirement

The implementation must have a clear `RedisStore` class (or equivalent) that owns all data structure and persistence logic. The CLI layer (argument parsing, stdout printing) must not contain data structure logic. This is evaluated by the LLM judge.
```

- [ ] **Step 2: Verify file exists**

Run: `ls harnesses/mini-redis/spec.md`

---

### Task 7: Create rubric.md and judge/rubric.md

**Files:**
- Create: `harnesses/mini-redis/rubric.md`
- Create: `harnesses/mini-redis/judge/rubric.md`
- Create: `harnesses/mini-redis/judge/calibration/README.md`
- Create: `harnesses/mini-redis/judge/calibration/scores.json`

- [ ] **Step 1: Create rubric.md**

```markdown
# mini-redis Scoring Rubric

**Harness version:** 1.0.0

All scores are in [0, 100]. Weights sum to 1.0.

---

## Dimension Weights

| Dimension | Weight |
|-----------|--------|
| Functional completeness | 0.30 |
| Adversarial survival | 0.15 |
| Extension readiness | 0.10 |
| Mutation kill rate | 0.10 |
| Performance | 0.15 |
| Reliability | 0.10 |
| Code quality | 0.10 |

**N/A redistribution:** If mutation has no tests to run (agent produced no test files), its 0.10 weight is redistributed proportionally to functional (0.30), adversarial (0.15), and extension (0.10). All other dimensions remain unchanged.

---

## D1: Functional Completeness (weight 0.30)

**Test tiers:**

| Tier | Weight within D1 | Commands |
|------|-----------------|---------|
| Tier 1 — Strings | 0.40 | SET, GET, DEL, EXISTS, MSET, MGET |
| Tier 2 — Collections | 0.35 | LPUSH, RPUSH, LPOP, RPOP, LRANGE, HSET, HGET, HDEL, HGETALL, HKEYS |
| Tier 3 — Advanced | 0.25 | EXPIRE, TTL, PERSIST, SADD, SREM, SMEMBERS, SISMEMBER, INCR, DECR |

**Formula:**
```
tier_score_i = (passed_i / total_i) * 100
D1 = 0.40 * tier1_score + 0.35 * tier2_score + 0.25 * tier3_score
```

**Not Applicable:** Never — if no tests run, score is 0.

---

## D2: Adversarial Survival (weight 0.15)

Tests ~150 public edge cases not disclosed to the agent: type errors, unicode keys/values, special characters in values, wrong-arity calls, unknown commands, boundary conditions on LRANGE/EXPIRE/TTL, and large datasets.

**Formula:**
```
D2 = (passed / total_adversarial_tests) * 100
total_adversarial_tests = public_count + held_out_count
```

Entries scored with held-out tests are marked `"verified": true`.

---

## D3: Extension Readiness (weight 0.10)

Second-prompt round: agent given 15 minutes to add Sorted Set support (ZADD, ZRANGE, ZRANK, ZSCORE, ZREM). 16 tests.

**Formula:**
```
D3 = (passed / 16) * 100
```

**Not Applicable:** If tier1 score < 40%, extension is skipped and weight redistributed. Score is 0 for static submissions (no live agent).

---

## D4: Mutation Kill Rate (weight 0.10)

Automated mutation testing of the agent's own test suite using mutmut.

**Formula:**
```
D4 = (killed / total_mutants) * 100
```

**Not Applicable:** If agent produced < 5 test functions, weight redistributed to D1+D2+D3.

---

## D5: Performance (weight 0.15)

Three benchmarks. Each scored piecewise linear:
- p95 ≤ target → 100
- p95 ≥ fail → 0
- Between → `100 * (fail - p95) / (fail - target)`

| Benchmark | Target p95 | Fail p95 | Weight |
|-----------|-----------|---------|--------|
| get_10k_keys | 1.0s | 5.0s | 0.40 |
| lrange_10k_list | 2.0s | 10.0s | 0.35 |
| hgetall_1k_fields | 1.0s | 5.0s | 0.25 |

**D5 = weighted average of benchmark scores.**

---

## D6: Reliability (weight 0.10)

7 chaos scenarios, each pass/fail:

1. Data survives clean process exit
2. Second read after write returns correct value
3. Corrupt JSON file → non-zero exit with stderr (no traceback)
4. Missing data file → empty store (no crash)
5. EXPIRE deadline survives process restart
6. TTL expired key → (nil) on read (lazy eviction)
7. Large value (1MB string) stored and retrieved correctly

**Formula:**
```
D6 = (passed / 7) * 100
```

---

## D7: Code Quality (weight 0.10)

Multi-model LLM judge evaluates 5 qualitative dimensions (see `judge/rubric.md`). Score is average across judge instances and dimensions.

**Dry run:** If `--dry-run` is used, D7 = 0 and is noted as `dry_run: true` in the scorecard. Leaderboard shows `—` not 0 for dry-run entries.

---

## Score Report Schema

```json
{
  "harness": "mini-redis",
  "harness_version": "1.0.0",
  "submission_id": "...",
  "model": "...",
  "agent_framework": "...",
  "date": "...",
  "scores": {
    "functional": {"score": 85.0, "weight": 0.30, "detail": {...}},
    "adversarial": {"score": 72.0, "weight": 0.15, "detail": {...}},
    "extension":   {"score": 25.0, "weight": 0.10, "detail": {...}},
    "mutation":    {"score": 80.0, "weight": 0.10, "detail": {...}},
    "performance": {"score": 90.0, "weight": 0.15, "detail": {...}},
    "reliability": {"score": 85.7, "weight": 0.10, "detail": {...}},
    "quality":     {"score": 70.0, "weight": 0.10, "detail": {...}}
  },
  "total_score": 81.2,
  "metadata": {...}
}
```
```

- [ ] **Step 2: Create judge/rubric.md**

```markdown
# mini-redis LLM Judge Rubric

You are evaluating a mini-redis implementation. Score each dimension 0–100. Be calibrated: most implementations will score 40–70. Reserve 90–100 for exceptional work.

## Dimension 1: Separation of Concerns

Does the implementation cleanly separate CLI (argument parsing, printing) from data store logic?

- **0:** All logic in `main()` or `if __name__ == "__main__"`. No class or module structure.
- **25:** A function `handle_command()` exists but contains data structure logic.
- **50:** A class exists but CLI and store logic are tangled (e.g., printing inside the store).
- **75:** Clear `RedisStore` class. CLI delegates to it. Minor leakage (e.g., one helper duplicated).
- **100:** Perfect separation. `RedisStore` is independently testable. CLI is a thin dispatcher.

## Dimension 2: Data Structure Abstraction Quality

Are the Redis data types (strings, lists, hashes, sets) represented cleanly?

- **0:** Everything is a flat string dict. Type detection by string parsing.
- **25:** Python dicts/lists used but type metadata is stringly typed (e.g., `{"type": "list", "data": [...]}`).
- **50:** Python native types used correctly (dict for hash, list for list, set for set) but type system is ad hoc.
- **75:** Clean internal representation. Type errors detected by isinstance checks. Consistent schema.
- **100:** Excellent abstraction. Data classes or typed container. Serialization/deserialization centralized.

## Dimension 3: Naming and Pattern Consistency

Are names, patterns, and conventions consistent across the codebase?

- **0:** Mixed naming (camelCase and snake_case), different patterns for similar operations.
- **25:** Consistent within a file, inconsistent across files.
- **50:** Mostly consistent; 2-3 outliers.
- **75:** High consistency. Similar operations use the same patterns throughout.
- **100:** Excellent. Any developer reading one command understands all others.

## Dimension 4: Test Quality and Coverage

Does the agent's own test suite test meaningfully?

- **0:** No tests, or tests with no assertions.
- **25:** Tests only check exit code 0. No content assertions.
- **50:** Happy-path tests with content assertions. No error/edge cases.
- **75:** Happy paths + most error conditions. Some edge cases (unicode, empty, wrong type).
- **100:** Comprehensive. Every command has happy + error tests. Persistence tested. Type errors tested.

## Dimension 5: Scope Discipline

Did the agent build exactly what was asked?

- **0:** Built something entirely different, or < 50% of commands implemented.
- **25:** Multiple unrequested features or multiple missing required commands.
- **50:** Mostly on-scope. 1-2 missing or extra features.
- **75:** All features present. Possibly one minor addition.
- **100:** Exact implementation of the prompt. Nothing extra. Missing features (if any) documented.

---

## Output Format

```json
{
  "dimensions": {
    "separation_of_concerns": {"score": 75, "reasoning": "..."},
    "data_structure_abstraction": {"score": 60, "reasoning": "..."},
    "naming_consistency": {"score": 80, "reasoning": "..."},
    "test_quality": {"score": 50, "reasoning": "..."},
    "scope_discipline": {"score": 90, "reasoning": "..."}
  },
  "aggregate_score": 71.0,
  "overall_notes": "..."
}
```
```

- [ ] **Step 3: Create calibration files**

Create `harnesses/mini-redis/judge/calibration/README.md`:
```markdown
# Judge Calibration

Reference implementations for calibrating the LLM judge.

- `sample_good/` — well-structured implementation (expected judge score ~75-85)
- `sample_bad/` — minimal, tangled implementation (expected judge score ~20-35)

`scores.json` contains human expert scores for each sample.
```

Create `harnesses/mini-redis/judge/calibration/scores.json`:
```json
{
  "calibration_version": "1.0.0",
  "samples": {}
}
```

- [ ] **Step 4: Commit harness docs**

```bash
git add harnesses/mini-redis/
git commit -m "feat: add mini-redis harness scaffold docs

prompt.md, spec.md, rubric.md, judge/rubric.md with complete
output contracts and scoring formulas."
```

---

## Chunk 3: Test Infrastructure + Tier 1 + Tier 2

### Task 8: Create test infrastructure

**Files:**
- Create: `harnesses/mini-redis/tests/__init__.py`
- Create: `harnesses/mini-redis/tests/conftest.py`
- Create: `harnesses/mini-redis/tests/pytest.ini`
- Create: `harnesses/mini-redis/tests/tier1/__init__.py`
- Create: `harnesses/mini-redis/tests/tier2/__init__.py`
- Create: `harnesses/mini-redis/tests/tier3/__init__.py`
- Create: `harnesses/mini-redis/tests/adversarial/__init__.py`
- Create: `harnesses/mini-redis/tests/extension/__init__.py`
- Create: `harnesses/mini-redis/tests/held-out/.gitkeep`
- Create: `harnesses/mini-redis/tests/reliability/__init__.py`
- Create: `harnesses/mini-redis/tests/performance/__init__.py`

- [ ] **Step 1: Create conftest.py**

```python
"""
conftest.py — shared fixtures and helpers for mini-redis tests.

Environment variables:
    MINI_REDIS_CMD  — command to invoke the mini-redis implementation.
    MINI_REDIS_DATA — path to the JSON data file (set per-test via tmp_path).
"""

import os
import shlex
import subprocess
from pathlib import Path
from typing import List, Optional

import pytest


def _discover_cmd() -> Optional[List[str]]:
    env_cmd = os.environ.get("MINI_REDIS_CMD")
    if env_cmd:
        return shlex.split(env_cmd)
    return None


_CMD: Optional[List[str]] = _discover_cmd()
CMD_NOT_FOUND: bool = _CMD is None


def run_redis(args: list, data_path=None) -> subprocess.CompletedProcess:
    """Run mini-redis CLI with args. Returns CompletedProcess (no exit code check)."""
    if _CMD is None:
        pytest.skip("MINI_REDIS_CMD not set")
    env = os.environ.copy()
    if data_path is not None:
        env["MINI_REDIS_DATA"] = str(data_path)
    return subprocess.run(
        _CMD + [str(a) for a in args],
        capture_output=True,
        text=True,
        env=env,
    )


def assert_success(result: subprocess.CompletedProcess) -> None:
    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


def assert_failure(result: subprocess.CompletedProcess, code: int = 1) -> None:
    assert result.returncode == code, (
        f"Expected exit {code} but got {result.returncode}\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


def assert_stdout(result: subprocess.CompletedProcess, expected: str) -> None:
    assert result.stdout.strip() == expected.strip(), (
        f"stdout mismatch.\nExpected: {expected!r}\nGot:      {result.stdout!r}"
    )


@pytest.fixture
def db(tmp_path: Path) -> Path:
    """Path to a fresh mini-redis data file (does not exist yet)."""
    return tmp_path / "mini_redis.json"


@pytest.fixture
def r(db):
    """Shorthand: run a redis command against the tmp db."""
    def _run(*args):
        return run_redis(list(args), data_path=db)
    return _run
```

- [ ] **Step 2: Create pytest.ini**

```ini
[pytest]
testpaths = .
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

- [ ] **Step 3: Create all __init__.py and .gitkeep files**

```bash
touch harnesses/mini-redis/tests/__init__.py
touch harnesses/mini-redis/tests/tier1/__init__.py
touch harnesses/mini-redis/tests/tier2/__init__.py
touch harnesses/mini-redis/tests/tier3/__init__.py
touch harnesses/mini-redis/tests/adversarial/__init__.py
touch harnesses/mini-redis/tests/extension/__init__.py
touch harnesses/mini-redis/tests/reliability/__init__.py
touch harnesses/mini-redis/tests/performance/__init__.py
touch harnesses/mini-redis/tests/held-out/.gitkeep
```

---

### Task 9: Tier 1 tests — strings and persistence

**Files:**
- Create: `harnesses/mini-redis/tests/tier1/test_strings.py`
- Create: `harnesses/mini-redis/tests/tier1/test_persistence.py`

- [ ] **Step 1: Create test_strings.py**

```python
"""Tier 1: SET, GET, DEL, EXISTS, MSET, MGET."""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_failure, assert_success, assert_stdout, run_redis


def test_set_and_get_basic(db):
    r = run_redis(["SET", "foo", "bar"], data_path=db)
    assert_success(r)
    assert_stdout(r, "OK")
    r2 = run_redis(["GET", "foo"], data_path=db)
    assert_success(r2)
    assert_stdout(r2, '"bar"')


def test_get_missing_key_returns_nil(db):
    r = run_redis(["GET", "nosuchkey"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(nil)")


def test_set_overwrites_value(db):
    run_redis(["SET", "k", "first"], data_path=db)
    run_redis(["SET", "k", "second"], data_path=db)
    r = run_redis(["GET", "k"], data_path=db)
    assert_stdout(r, '"second"')


def test_del_existing_key(db):
    run_redis(["SET", "k", "v"], data_path=db)
    r = run_redis(["DEL", "k"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(integer) 1")
    r2 = run_redis(["GET", "k"], data_path=db)
    assert_stdout(r2, "(nil)")


def test_del_missing_key_returns_zero(db):
    r = run_redis(["DEL", "nosuchkey"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(integer) 0")


def test_del_multiple_keys(db):
    run_redis(["SET", "a", "1"], data_path=db)
    run_redis(["SET", "b", "2"], data_path=db)
    r = run_redis(["DEL", "a", "b", "c"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(integer) 2")


def test_exists_present(db):
    run_redis(["SET", "k", "v"], data_path=db)
    r = run_redis(["EXISTS", "k"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(integer) 1")


def test_exists_missing(db):
    r = run_redis(["EXISTS", "nosuchkey"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(integer) 0")


def test_mset_and_mget(db):
    r = run_redis(["MSET", "a", "1", "b", "2", "c", "3"], data_path=db)
    assert_success(r)
    assert_stdout(r, "OK")
    r2 = run_redis(["MGET", "a", "b", "c"], data_path=db)
    assert_success(r2)
    lines = r2.stdout.strip().splitlines()
    assert lines == ['1) "1"', '2) "2"', '3) "3"']


def test_mget_with_missing_key(db):
    run_redis(["SET", "a", "alpha"], data_path=db)
    run_redis(["SET", "c", "gamma"], data_path=db)
    r = run_redis(["MGET", "a", "missing", "c"], data_path=db)
    assert_success(r)
    lines = r.stdout.strip().splitlines()
    assert lines == ['1) "alpha"', "2) (nil)", '3) "gamma"']


def test_set_wrong_arity_exits_1(db):
    r = run_redis(["SET", "onlykey"], data_path=db)
    assert_failure(r, code=1)
    assert r.stdout.strip() == ""
    assert "ERR" in r.stderr


def test_get_wrong_arity_exits_1(db):
    r = run_redis(["GET"], data_path=db)
    assert_failure(r, code=1)
```

- [ ] **Step 2: Create test_persistence.py**

```python
"""Tier 1: data file creation and persistence across process restarts."""

import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, assert_stdout, run_redis


def test_data_file_created_after_set(db):
    assert not db.exists()
    run_redis(["SET", "k", "v"], data_path=db)
    assert db.exists(), "Data file must be created after SET"


def test_data_file_not_created_by_get(db):
    run_redis(["GET", "nosuchkey"], data_path=db)
    assert not db.exists(), "GET on missing key must not create data file"


def test_data_survives_restart(db):
    run_redis(["SET", "persist_key", "persist_val"], data_path=db)
    # Second process invocation
    r = run_redis(["GET", "persist_key"], data_path=db)
    assert_success(r)
    assert_stdout(r, '"persist_val"')


def test_multiple_keys_survive_restart(db):
    run_redis(["SET", "x", "10"], data_path=db)
    run_redis(["SET", "y", "20"], data_path=db)
    r_x = run_redis(["GET", "x"], data_path=db)
    r_y = run_redis(["GET", "y"], data_path=db)
    assert_stdout(r_x, '"10"')
    assert_stdout(r_y, '"20"')


def test_empty_store_when_file_missing(tmp_path):
    nonexistent = tmp_path / "does_not_exist.json"
    r = run_redis(["GET", "k"], data_path=nonexistent)
    assert_success(r)
    assert_stdout(r, "(nil)")
```

- [ ] **Step 3: Verify tests are discoverable**

Run: `python -m pytest harnesses/mini-redis/tests/tier1/ --collect-only -q 2>&1 | head -20`
Expected: Lists ~15 test items (skip warnings OK, no collection errors)

---

### Task 10: Tier 2 tests — lists and hashes

**Files:**
- Create: `harnesses/mini-redis/tests/tier2/test_lists.py`
- Create: `harnesses/mini-redis/tests/tier2/test_hashes.py`

- [ ] **Step 1: Create test_lists.py**

```python
"""Tier 2: LPUSH, RPUSH, LPOP, RPOP, LRANGE."""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_failure, assert_success, assert_stdout, run_redis


def test_rpush_creates_list_and_returns_length(db):
    r = run_redis(["RPUSH", "mylist", "a"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(integer) 1")


def test_rpush_multiple_values_returns_new_length(db):
    r = run_redis(["RPUSH", "mylist", "a", "b", "c"], data_path=db)
    assert_stdout(r, "(integer) 3")


def test_lpush_prepends(db):
    run_redis(["RPUSH", "mylist", "b"], data_path=db)
    run_redis(["LPUSH", "mylist", "a"], data_path=db)
    r = run_redis(["LRANGE", "mylist", "0", "-1"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ['1) "a"', '2) "b"']


def test_lrange_full_list(db):
    run_redis(["RPUSH", "mylist", "x", "y", "z"], data_path=db)
    r = run_redis(["LRANGE", "mylist", "0", "-1"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ['1) "x"', '2) "y"', '3) "z"']


def test_lrange_partial(db):
    run_redis(["RPUSH", "mylist", "a", "b", "c", "d"], data_path=db)
    r = run_redis(["LRANGE", "mylist", "1", "2"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ['1) "b"', '2) "c"']


def test_lrange_negative_indices(db):
    run_redis(["RPUSH", "mylist", "a", "b", "c"], data_path=db)
    r = run_redis(["LRANGE", "mylist", "-2", "-1"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ['1) "b"', '2) "c"']


def test_lrange_empty_list(db):
    run_redis(["RPUSH", "mylist", "x"], data_path=db)
    run_redis(["LPOP", "mylist"], data_path=db)
    r = run_redis(["LRANGE", "mylist", "0", "-1"], data_path=db)
    assert_stdout(r, "(empty list)")


def test_lrange_missing_key(db):
    r = run_redis(["LRANGE", "nosuchkey", "0", "-1"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(empty list)")


def test_lpop_returns_and_removes(db):
    run_redis(["RPUSH", "mylist", "first", "second"], data_path=db)
    r = run_redis(["LPOP", "mylist"], data_path=db)
    assert_success(r)
    assert_stdout(r, '"first"')
    r2 = run_redis(["LRANGE", "mylist", "0", "-1"], data_path=db)
    lines = r2.stdout.strip().splitlines()
    assert lines == ['1) "second"']


def test_rpop_returns_and_removes(db):
    run_redis(["RPUSH", "mylist", "a", "b"], data_path=db)
    r = run_redis(["RPOP", "mylist"], data_path=db)
    assert_stdout(r, '"b"')


def test_lpop_on_empty_key_returns_nil(db):
    r = run_redis(["LPOP", "nosuchkey"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(nil)")


def test_lpush_multiple_values_order(db):
    # LPUSH a b c → list is [c, b, a] (each pushed to left)
    run_redis(["LPUSH", "mylist", "a", "b", "c"], data_path=db)
    r = run_redis(["LRANGE", "mylist", "0", "-1"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ['1) "c"', '2) "b"', '3) "a"']
```

- [ ] **Step 2: Create test_hashes.py**

```python
"""Tier 2: HSET, HGET, HDEL, HGETALL, HKEYS."""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_failure, assert_success, assert_stdout, run_redis


def test_hset_and_hget(db):
    r = run_redis(["HSET", "user", "name", "Alice"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(integer) 1")
    r2 = run_redis(["HGET", "user", "name"], data_path=db)
    assert_stdout(r2, '"Alice"')


def test_hset_multiple_fields(db):
    r = run_redis(["HSET", "user", "name", "Alice", "age", "30"], data_path=db)
    assert_stdout(r, "(integer) 2")


def test_hset_update_existing_returns_zero(db):
    run_redis(["HSET", "h", "f", "v1"], data_path=db)
    r = run_redis(["HSET", "h", "f", "v2"], data_path=db)
    assert_stdout(r, "(integer) 0")
    r2 = run_redis(["HGET", "h", "f"], data_path=db)
    assert_stdout(r2, '"v2"')


def test_hget_missing_field(db):
    run_redis(["HSET", "h", "f", "v"], data_path=db)
    r = run_redis(["HGET", "h", "nosuchfield"], data_path=db)
    assert_stdout(r, "(nil)")


def test_hget_missing_key(db):
    r = run_redis(["HGET", "nosuchkey", "f"], data_path=db)
    assert_stdout(r, "(nil)")


def test_hdel_field(db):
    run_redis(["HSET", "h", "f1", "v1", "f2", "v2"], data_path=db)
    r = run_redis(["HDEL", "h", "f1"], data_path=db)
    assert_stdout(r, "(integer) 1")
    r2 = run_redis(["HGET", "h", "f1"], data_path=db)
    assert_stdout(r2, "(nil)")


def test_hdel_missing_field_returns_zero(db):
    run_redis(["HSET", "h", "f", "v"], data_path=db)
    r = run_redis(["HDEL", "h", "nosuchfield"], data_path=db)
    assert_stdout(r, "(integer) 0")


def test_hgetall_alphabetical_order(db):
    run_redis(["HSET", "h", "zebra", "z", "apple", "a", "mango", "m"], data_path=db)
    r = run_redis(["HGETALL", "h"], data_path=db)
    assert_success(r)
    lines = r.stdout.strip().splitlines()
    assert lines == ["apple", "a", "mango", "m", "zebra", "z"]


def test_hgetall_empty_key(db):
    r = run_redis(["HGETALL", "nosuchkey"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(empty list)")


def test_hkeys_alphabetical(db):
    run_redis(["HSET", "h", "c", "3", "a", "1", "b", "2"], data_path=db)
    r = run_redis(["HKEYS", "h"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ['1) "a"', '2) "b"', '3) "c"']


def test_hkeys_empty(db):
    r = run_redis(["HKEYS", "nosuchkey"], data_path=db)
    assert_stdout(r, "(empty list)")
```

- [ ] **Step 3: Verify tier2 tests collect**

Run: `python -m pytest harnesses/mini-redis/tests/tier2/ --collect-only -q 2>&1 | head -20`

- [ ] **Step 4: Commit tier1 + tier2 tests**

```bash
git add harnesses/mini-redis/tests/
git commit -m "feat: add mini-redis test infrastructure and tier1/tier2 tests

conftest.py, pytest.ini, and 30 tests covering strings,
persistence, lists, and hashes."
```

---

## Chunk 4: Tier 3 + Adversarial Tests

### Task 11: Tier 3 tests

**Files:**
- Create: `harnesses/mini-redis/tests/tier3/test_ttl.py`
- Create: `harnesses/mini-redis/tests/tier3/test_sets.py`
- Create: `harnesses/mini-redis/tests/tier3/test_counters.py`

- [ ] **Step 1: Create test_ttl.py**

```python
"""Tier 3: EXPIRE, TTL, PERSIST."""

import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, assert_stdout, run_redis


def test_expire_existing_key_returns_1(db):
    run_redis(["SET", "k", "v"], data_path=db)
    r = run_redis(["EXPIRE", "k", "60"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(integer) 1")


def test_expire_missing_key_returns_0(db):
    r = run_redis(["EXPIRE", "nosuchkey", "60"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(integer) 0")


def test_ttl_returns_remaining_seconds(db):
    run_redis(["SET", "k", "v"], data_path=db)
    run_redis(["EXPIRE", "k", "100"], data_path=db)
    r = run_redis(["TTL", "k"], data_path=db)
    assert_success(r)
    out = r.stdout.strip()
    assert out.startswith("(integer) ")
    secs = int(out.split()[-1])
    assert 95 <= secs <= 100, f"Expected ~100 seconds remaining, got {secs}"


def test_ttl_no_expiry_returns_minus_1(db):
    run_redis(["SET", "k", "v"], data_path=db)
    r = run_redis(["TTL", "k"], data_path=db)
    assert_stdout(r, "(integer) -1")


def test_ttl_missing_key_returns_minus_2(db):
    r = run_redis(["TTL", "nosuchkey"], data_path=db)
    assert_stdout(r, "(integer) -2")


def test_persist_removes_ttl(db):
    run_redis(["SET", "k", "v"], data_path=db)
    run_redis(["EXPIRE", "k", "60"], data_path=db)
    r = run_redis(["PERSIST", "k"], data_path=db)
    assert_stdout(r, "(integer) 1")
    r2 = run_redis(["TTL", "k"], data_path=db)
    assert_stdout(r2, "(integer) -1")


def test_persist_no_ttl_returns_0(db):
    run_redis(["SET", "k", "v"], data_path=db)
    r = run_redis(["PERSIST", "k"], data_path=db)
    assert_stdout(r, "(integer) 0")


def test_expire_zero_seconds_exits_1(db):
    run_redis(["SET", "k", "v"], data_path=db)
    r = run_redis(["EXPIRE", "k", "0"], data_path=db)
    assert r.returncode == 1
    assert r.stdout.strip() == ""


def test_expire_negative_seconds_exits_1(db):
    run_redis(["SET", "k", "v"], data_path=db)
    r = run_redis(["EXPIRE", "k", "-5"], data_path=db)
    assert r.returncode == 1


def test_expired_key_returns_nil_on_get(db):
    """Key expired in a previous invocation returns (nil) in next invocation."""
    import time
    run_redis(["SET", "k", "v"], data_path=db)
    run_redis(["EXPIRE", "k", "1"], data_path=db)
    time.sleep(1.1)
    r = run_redis(["GET", "k"], data_path=db)
    assert_stdout(r, "(nil)")
```

- [ ] **Step 2: Create test_sets.py**

```python
"""Tier 3: SADD, SREM, SMEMBERS, SISMEMBER."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, assert_stdout, run_redis


def test_sadd_new_members(db):
    r = run_redis(["SADD", "s", "a", "b", "c"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(integer) 3")


def test_sadd_duplicate_not_counted(db):
    run_redis(["SADD", "s", "a", "b"], data_path=db)
    r = run_redis(["SADD", "s", "b", "c"], data_path=db)
    assert_stdout(r, "(integer) 1")  # only "c" is new


def test_srem_removes_member(db):
    run_redis(["SADD", "s", "a", "b", "c"], data_path=db)
    r = run_redis(["SREM", "s", "b"], data_path=db)
    assert_stdout(r, "(integer) 1")


def test_srem_missing_member_returns_0(db):
    run_redis(["SADD", "s", "a"], data_path=db)
    r = run_redis(["SREM", "s", "nosuchmember"], data_path=db)
    assert_stdout(r, "(integer) 0")


def test_smembers_lexicographic_order(db):
    run_redis(["SADD", "s", "banana", "apple", "cherry"], data_path=db)
    r = run_redis(["SMEMBERS", "s"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ['1) "apple"', '2) "banana"', '3) "cherry"']


def test_smembers_empty_set(db):
    r = run_redis(["SMEMBERS", "nosuchkey"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(empty set)")


def test_sismember_present(db):
    run_redis(["SADD", "s", "member"], data_path=db)
    r = run_redis(["SISMEMBER", "s", "member"], data_path=db)
    assert_stdout(r, "(integer) 1")


def test_sismember_absent(db):
    run_redis(["SADD", "s", "a"], data_path=db)
    r = run_redis(["SISMEMBER", "s", "notamember"], data_path=db)
    assert_stdout(r, "(integer) 0")
```

- [ ] **Step 3: Create test_counters.py**

```python
"""Tier 3: INCR, DECR."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_failure, assert_success, assert_stdout, run_redis


def test_incr_missing_key_starts_at_1(db):
    r = run_redis(["INCR", "counter"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(integer) 1")


def test_incr_existing_integer(db):
    run_redis(["SET", "counter", "5"], data_path=db)
    r = run_redis(["INCR", "counter"], data_path=db)
    assert_stdout(r, "(integer) 6")


def test_decr_missing_key_starts_at_minus_1(db):
    r = run_redis(["DECR", "counter"], data_path=db)
    assert_stdout(r, "(integer) -1")


def test_decr_existing_integer(db):
    run_redis(["SET", "counter", "10"], data_path=db)
    r = run_redis(["DECR", "counter"], data_path=db)
    assert_stdout(r, "(integer) 9")


def test_incr_on_non_integer_exits_1(db):
    run_redis(["SET", "k", "notanumber"], data_path=db)
    r = run_redis(["INCR", "k"], data_path=db)
    assert_failure(r, code=1)
    assert r.stdout.strip() == ""
    assert "ERR" in r.stderr


def test_decr_on_non_integer_exits_1(db):
    run_redis(["SET", "k", "notanumber"], data_path=db)
    r = run_redis(["DECR", "k"], data_path=db)
    assert_failure(r, code=1)


def test_incr_survives_restart(db):
    run_redis(["INCR", "counter"], data_path=db)
    run_redis(["INCR", "counter"], data_path=db)
    r = run_redis(["GET", "counter"], data_path=db)
    assert_stdout(r, '"2"')
```

---

### Task 12: Adversarial tests

**Files:**
- Create: `harnesses/mini-redis/tests/adversarial/test_type_errors.py`
- Create: `harnesses/mini-redis/tests/adversarial/test_error_handling.py`
- Create: `harnesses/mini-redis/tests/adversarial/test_edge_cases.py`
- Create: `harnesses/mini-redis/tests/adversarial/test_encoding.py`
- Create: `harnesses/mini-redis/tests/adversarial/test_boundary.py`

- [ ] **Step 1: Create test_type_errors.py**

```python
"""Adversarial: operations on keys holding wrong type."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_failure, run_redis


def _setup_string(db, key="k"):
    run_redis(["SET", key, "value"], data_path=db)

def _setup_list(db, key="k"):
    run_redis(["RPUSH", key, "item"], data_path=db)

def _setup_hash(db, key="k"):
    run_redis(["HSET", key, "field", "value"], data_path=db)

def _setup_set(db, key="k"):
    run_redis(["SADD", key, "member"], data_path=db)


def test_lpush_on_string_exits_1(db):
    _setup_string(db)
    r = run_redis(["LPUSH", "k", "item"], data_path=db)
    assert_failure(r)
    assert "WRONGTYPE" in r.stderr

def test_rpush_on_string_exits_1(db):
    _setup_string(db)
    r = run_redis(["RPUSH", "k", "item"], data_path=db)
    assert_failure(r)

def test_get_on_list_exits_1(db):
    _setup_list(db)
    r = run_redis(["GET", "k"], data_path=db)
    assert_failure(r)
    assert "WRONGTYPE" in r.stderr

def test_hset_on_list_exits_1(db):
    _setup_list(db)
    r = run_redis(["HSET", "k", "f", "v"], data_path=db)
    assert_failure(r)

def test_sadd_on_string_exits_1(db):
    _setup_string(db)
    r = run_redis(["SADD", "k", "member"], data_path=db)
    assert_failure(r)

def test_incr_on_list_exits_1(db):
    _setup_list(db)
    r = run_redis(["INCR", "k"], data_path=db)
    assert_failure(r)

def test_lrange_on_hash_exits_1(db):
    _setup_hash(db)
    r = run_redis(["LRANGE", "k", "0", "-1"], data_path=db)
    assert_failure(r)

def test_smembers_on_list_exits_1(db):
    _setup_list(db)
    r = run_redis(["SMEMBERS", "k"], data_path=db)
    assert_failure(r)

def test_hget_on_set_exits_1(db):
    _setup_set(db)
    r = run_redis(["HGET", "k", "field"], data_path=db)
    assert_failure(r)
```

- [ ] **Step 2: Create test_error_handling.py**

```python
"""Adversarial: wrong arity, unknown commands, malformed input."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_failure, run_redis


def test_unknown_command_exits_1(db):
    r = run_redis(["XREAD", "k"], data_path=db)
    assert_failure(r)
    assert "ERR unknown command" in r.stderr

def test_set_no_args_exits_1(db):
    r = run_redis(["SET"], data_path=db)
    assert_failure(r)

def test_set_one_arg_exits_1(db):
    r = run_redis(["SET", "onlykey"], data_path=db)
    assert_failure(r)

def test_get_no_args_exits_1(db):
    r = run_redis(["GET"], data_path=db)
    assert_failure(r)

def test_del_no_args_exits_1(db):
    r = run_redis(["DEL"], data_path=db)
    assert_failure(r)

def test_mset_odd_args_exits_1(db):
    r = run_redis(["MSET", "k1", "v1", "k2"], data_path=db)
    assert_failure(r)

def test_expire_no_seconds_exits_1(db):
    run_redis(["SET", "k", "v"], data_path=db)
    r = run_redis(["EXPIRE", "k"], data_path=db)
    assert_failure(r)

def test_expire_non_integer_seconds_exits_1(db):
    run_redis(["SET", "k", "v"], data_path=db)
    r = run_redis(["EXPIRE", "k", "notanint"], data_path=db)
    assert_failure(r)

def test_hset_odd_field_value_args_exits_1(db):
    r = run_redis(["HSET", "h", "field_only"], data_path=db)
    assert_failure(r)

def test_no_command_exits_1(db):
    r = run_redis([], data_path=db)
    assert_failure(r)

def test_empty_string_command_exits_1(db):
    r = run_redis([""], data_path=db)
    assert_failure(r)
```

- [ ] **Step 3: Create test_edge_cases.py**

```python
"""Adversarial: edge cases — empty values, large values, key edge cases."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, assert_stdout, run_redis


def test_empty_string_value(db):
    r = run_redis(["SET", "k", ""], data_path=db)
    assert_success(r)
    r2 = run_redis(["GET", "k"], data_path=db)
    assert_stdout(r2, '""')


def test_value_with_spaces(db):
    run_redis(["SET", "k", "hello world"], data_path=db)
    r = run_redis(["GET", "k"], data_path=db)
    assert_stdout(r, '"hello world"')


def test_numeric_string_value(db):
    run_redis(["SET", "k", "42"], data_path=db)
    r = run_redis(["GET", "k"], data_path=db)
    assert_stdout(r, '"42"')


def test_large_value(db):
    big = "x" * 100_000
    run_redis(["SET", "big", big], data_path=db)
    r = run_redis(["GET", "big"], data_path=db)
    assert_success(r)
    # Value should be returned quoted
    assert r.stdout.strip() == f'"{big}"'


def test_key_with_colon(db):
    run_redis(["SET", "user:1:name", "Alice"], data_path=db)
    r = run_redis(["GET", "user:1:name"], data_path=db)
    assert_stdout(r, '"Alice"')


def test_del_multiple_some_missing(db):
    run_redis(["SET", "exists", "v"], data_path=db)
    r = run_redis(["DEL", "exists", "missing1", "missing2"], data_path=db)
    assert_stdout(r, "(integer) 1")


def test_lrange_out_of_bounds_returns_available(db):
    run_redis(["RPUSH", "mylist", "a", "b"], data_path=db)
    r = run_redis(["LRANGE", "mylist", "0", "100"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ['1) "a"', '2) "b"']


def test_lrange_empty_range(db):
    run_redis(["RPUSH", "mylist", "a", "b", "c"], data_path=db)
    r = run_redis(["LRANGE", "mylist", "5", "10"], data_path=db)
    assert_stdout(r, "(empty list)")


def test_incr_persists_across_restart(db):
    run_redis(["INCR", "ctr"], data_path=db)
    run_redis(["INCR", "ctr"], data_path=db)
    run_redis(["INCR", "ctr"], data_path=db)
    r = run_redis(["GET", "ctr"], data_path=db)
    assert_stdout(r, '"3"')


def test_hgetall_single_field(db):
    run_redis(["HSET", "h", "onlyfield", "onlyvalue"], data_path=db)
    r = run_redis(["HGETALL", "h"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ["onlyfield", "onlyvalue"]
```

- [ ] **Step 4: Create test_encoding.py**

```python
"""Adversarial: unicode keys and values, special characters."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, assert_stdout, run_redis


def test_unicode_value(db):
    run_redis(["SET", "greeting", "こんにちは"], data_path=db)
    r = run_redis(["GET", "greeting"], data_path=db)
    assert_success(r)
    assert '"こんにちは"' in r.stdout


def test_emoji_value(db):
    run_redis(["SET", "k", "🎉"], data_path=db)
    r = run_redis(["GET", "k"], data_path=db)
    assert_success(r)
    assert '"🎉"' in r.stdout


def test_unicode_key(db):
    run_redis(["SET", "キー", "value"], data_path=db)
    r = run_redis(["GET", "キー"], data_path=db)
    assert_stdout(r, '"value"')


def test_backslash_in_value(db):
    run_redis(["SET", "k", "back\\slash"], data_path=db)
    r = run_redis(["GET", "k"], data_path=db)
    assert_success(r)
    # Output must have escaped backslash: "back\\slash" (the :g spec rule escapes \ as \\)
    assert r.stdout.strip() == '"back\\\\slash"'


def test_double_quote_in_value(db):
    run_redis(["SET", "k", 'say "hello"'], data_path=db)
    r = run_redis(["GET", "k"], data_path=db)
    assert_success(r)
    assert r.returncode == 0
    # Output must be quoted and escaped
    out = r.stdout.strip()
    assert out.startswith('"') and out.endswith('"')


def test_hash_with_unicode_fields(db):
    run_redis(["HSET", "h", "名前", "Alice", "年齢", "30"], data_path=db)
    r = run_redis(["HKEYS", "h"], data_path=db)
    assert_success(r)
    assert "名前" in r.stdout
    assert "年齢" in r.stdout


def test_set_member_unicode(db):
    run_redis(["SADD", "tags", "python", "Ω大", "αβγ"], data_path=db)
    r = run_redis(["SMEMBERS", "tags"], data_path=db)
    assert_success(r)
    assert "python" in r.stdout
```

- [ ] **Step 5: Create test_boundary.py**

```python
"""Adversarial: boundary conditions."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, assert_stdout, run_redis


def test_incr_to_large_number(db):
    run_redis(["SET", "k", "9999999999"], data_path=db)
    r = run_redis(["INCR", "k"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(integer) 10000000000")


def test_decr_below_zero(db):
    run_redis(["SET", "k", "0"], data_path=db)
    r = run_redis(["DECR", "k"], data_path=db)
    assert_stdout(r, "(integer) -1")


def test_lrange_single_element_list(db):
    run_redis(["RPUSH", "mylist", "only"], data_path=db)
    r = run_redis(["LRANGE", "mylist", "0", "0"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ['1) "only"']


def test_sadd_many_members(db):
    members = [str(i) for i in range(50)]
    run_redis(["SADD", "s"] + members, data_path=db)
    r = run_redis(["SMEMBERS", "s"], data_path=db)
    assert_success(r)
    lines = r.stdout.strip().splitlines()
    assert len(lines) == 50


def test_hset_many_fields(db):
    args = []
    for i in range(50):
        args += [f"field{i:03d}", f"value{i}"]
    run_redis(["HSET", "h"] + args, data_path=db)
    r = run_redis(["HKEYS", "h"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert len(lines) == 50


def test_mget_many_keys(db):
    keys = [f"k{i}" for i in range(20)]
    for k in keys:
        run_redis(["SET", k, k + "_val"], data_path=db)
    r = run_redis(["MGET"] + keys, data_path=db)
    lines = r.stdout.strip().splitlines()
    assert len(lines) == 20


def test_del_all_keys_leaves_empty_store(db):
    run_redis(["SET", "a", "1"], data_path=db)
    run_redis(["SET", "b", "2"], data_path=db)
    run_redis(["DEL", "a", "b"], data_path=db)
    r = run_redis(["EXISTS", "a"], data_path=db)
    assert_stdout(r, "(integer) 0")
    r2 = run_redis(["EXISTS", "b"], data_path=db)
    assert_stdout(r2, "(integer) 0")


def test_lpop_until_empty(db):
    run_redis(["RPUSH", "mylist", "a", "b"], data_path=db)
    run_redis(["LPOP", "mylist"], data_path=db)
    run_redis(["LPOP", "mylist"], data_path=db)
    r = run_redis(["LRANGE", "mylist", "0", "-1"], data_path=db)
    assert_stdout(r, "(empty list)")


def test_persist_on_key_without_ttl_returns_0(db):
    run_redis(["SET", "k", "v"], data_path=db)
    r = run_redis(["PERSIST", "k"], data_path=db)
    assert_stdout(r, "(integer) 0")
```

- [ ] **Step 6: Commit tier3 + adversarial tests**

```bash
git add harnesses/mini-redis/tests/tier3/ harnesses/mini-redis/tests/adversarial/
git commit -m "feat: add mini-redis tier3 and adversarial tests

TTL, sets, counters (tier3) and ~80 adversarial tests covering
type errors, error handling, edge cases, encoding, boundaries."
```

---

## Chunk 5: Extension + Reliability + Performance

### Task 13: Extension tests — sorted sets

**Files:**
- Create: `harnesses/mini-redis/tests/extension/prompt.md`
- Create: `harnesses/mini-redis/tests/extension/test_sorted_sets.py`

- [ ] **Step 1: Create extension/prompt.md**

```markdown
# mini-redis Extension: Sorted Sets

The mini-redis implementation now needs to support Sorted Sets.

Add the following commands:

- `ZADD key score member [score member ...]` — add members with scores; print `(integer) N` (new members added; updating an existing member's score counts as 0)
- `ZRANGE key start stop` — list members by rank (ascending score), 0-indexed, negatives supported; print numbered list
- `ZRANK key member` — print `(integer) N` (0-based rank ascending) or `(nil)` if not found
- `ZSCORE key member` — print quoted score (e.g. `"1"` or `"1.5"`) or `(nil)` if not found
- `ZREM key member [member ...]` — remove members; print `(integer) N` removed

Rules:
- Scores are 64-bit floats
- Ties in score are broken lexicographically by member name
- ZRANGE does not support WITHSCORES (out of scope)
- Wrong type: exit 1, WRONGTYPE error

Write tests for the new functionality.
```

- [ ] **Step 2: Create test_sorted_sets.py**

```python
"""Extension: ZADD, ZRANGE, ZRANK, ZSCORE, ZREM — 16 tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_failure, assert_success, assert_stdout, run_redis


def test_zadd_new_member_returns_1(db):
    r = run_redis(["ZADD", "z", "1.0", "a"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(integer) 1")


def test_zadd_multiple_members(db):
    r = run_redis(["ZADD", "z", "1", "a", "2", "b", "3", "c"], data_path=db)
    assert_stdout(r, "(integer) 3")


def test_zadd_update_existing_returns_0(db):
    run_redis(["ZADD", "z", "1", "a"], data_path=db)
    r = run_redis(["ZADD", "z", "5", "a"], data_path=db)
    assert_stdout(r, "(integer) 0")


def test_zrange_ascending_by_score(db):
    run_redis(["ZADD", "z", "3", "c", "1", "a", "2", "b"], data_path=db)
    r = run_redis(["ZRANGE", "z", "0", "-1"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ['1) "a"', '2) "b"', '3) "c"']


def test_zrange_partial(db):
    run_redis(["ZADD", "z", "1", "a", "2", "b", "3", "c", "4", "d"], data_path=db)
    r = run_redis(["ZRANGE", "z", "1", "2"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ['1) "b"', '2) "c"']


def test_zrange_empty(db):
    r = run_redis(["ZRANGE", "nosuchkey", "0", "-1"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(empty list)")


def test_zrange_tie_broken_lexicographically(db):
    run_redis(["ZADD", "z", "1", "banana", "1", "apple", "1", "cherry"], data_path=db)
    r = run_redis(["ZRANGE", "z", "0", "-1"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ['1) "apple"', '2) "banana"', '3) "cherry"']


def test_zrank_found(db):
    run_redis(["ZADD", "z", "1", "a", "2", "b", "3", "c"], data_path=db)
    r = run_redis(["ZRANK", "z", "b"], data_path=db)
    assert_stdout(r, "(integer) 1")


def test_zrank_not_found(db):
    run_redis(["ZADD", "z", "1", "a"], data_path=db)
    r = run_redis(["ZRANK", "z", "nosuchmember"], data_path=db)
    assert_stdout(r, "(nil)")


def test_zscore_found_integer(db):
    run_redis(["ZADD", "z", "5", "a"], data_path=db)
    r = run_redis(["ZSCORE", "z", "a"], data_path=db)
    assert_success(r)
    out = r.stdout.strip()
    assert out == '"5"', f"Got {out!r}  (spec requires f\"{{score:g}}\" format, so 5.0 → '5')"


def test_zscore_found_float(db):
    run_redis(["ZADD", "z", "1.5", "a"], data_path=db)
    r = run_redis(["ZSCORE", "z", "a"], data_path=db)
    assert_stdout(r, '"1.5"')


def test_zscore_not_found(db):
    run_redis(["ZADD", "z", "1", "a"], data_path=db)
    r = run_redis(["ZSCORE", "z", "nosuchmember"], data_path=db)
    assert_stdout(r, "(nil)")


def test_zrem_removes_member(db):
    run_redis(["ZADD", "z", "1", "a", "2", "b"], data_path=db)
    r = run_redis(["ZREM", "z", "a"], data_path=db)
    assert_stdout(r, "(integer) 1")
    r2 = run_redis(["ZRANGE", "z", "0", "-1"], data_path=db)
    lines = r2.stdout.strip().splitlines()
    assert lines == ['1) "b"']


def test_zrem_missing_member_returns_0(db):
    run_redis(["ZADD", "z", "1", "a"], data_path=db)
    r = run_redis(["ZREM", "z", "nosuchmember"], data_path=db)
    assert_stdout(r, "(integer) 0")


def test_zrange_negative_indices(db):
    run_redis(["ZADD", "z", "1", "a", "2", "b", "3", "c"], data_path=db)
    r = run_redis(["ZRANGE", "z", "-2", "-1"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ['1) "b"', '2) "c"']


def test_zadd_wrong_type_exits_1(db):
    run_redis(["SET", "k", "string"], data_path=db)
    r = run_redis(["ZADD", "k", "1", "member"], data_path=db)
    assert_failure(r)
    assert "WRONGTYPE" in r.stderr
```

---

### Task 14: Reliability tests

**Files:**
- Create: `harnesses/mini-redis/tests/reliability/test_durability.py`
- Create: `harnesses/mini-redis/tests/reliability/test_corruption.py`

- [ ] **Step 1: Create test_durability.py**

```python
"""Reliability: durability, persistence, and data integrity."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, assert_stdout, run_redis, _CMD


def test_data_file_written_before_exit(db):
    """File must exist after SET — confirming fsync happened."""
    run_redis(["SET", "k", "v"], data_path=db)
    assert db.exists(), "Data file not written after SET"
    assert db.stat().st_size > 0, "Data file is empty"


def test_read_after_write_correct(db):
    """GET after SET returns correct value — basic sanity."""
    run_redis(["SET", "mykey", "myvalue"], data_path=db)
    r = run_redis(["GET", "mykey"], data_path=db)
    assert_stdout(r, '"myvalue"')


def test_many_writes_survive_restart(db):
    """Multiple writes — all survive a process restart."""
    for i in range(20):
        run_redis(["SET", f"key{i}", f"val{i}"], data_path=db)
    for i in range(20):
        r = run_redis(["GET", f"key{i}"], data_path=db)
        assert_stdout(r, f'"val{i}"')


def test_expire_deadline_survives_restart(db):
    """TTL deadline stored as epoch timestamp — still valid after restart."""
    run_redis(["SET", "k", "v"], data_path=db)
    run_redis(["EXPIRE", "k", "3600"], data_path=db)
    r = run_redis(["TTL", "k"], data_path=db)
    assert_success(r)
    out = r.stdout.strip()
    assert out.startswith("(integer) ")
    remaining = int(out.split()[-1])
    assert remaining > 3590, f"TTL should be ~3600, got {remaining}"


def test_missing_data_file_treated_as_empty(tmp_path):
    """No data file → empty store → GET returns (nil)."""
    db = tmp_path / "nonexistent.json"
    assert not db.exists()
    r = run_redis(["GET", "k"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(nil)")


def test_sigkill_does_not_corrupt_data_file(tmp_path):
    """SIGKILL during a write must not leave a partially-written (corrupt) file.

    Strategy: write a known-good key first so the file exists, then start a
    long-running write (SET with a large value in a tight loop) and SIGKILL it
    mid-flight. After the kill, the data file must either:
      (a) still be the last-known-good JSON, OR
      (b) not exist (implementation chose atomic write-then-rename)
    It must never be a partial/corrupt file.
    """
    if _CMD is None:
        import pytest
        pytest.skip("MINI_REDIS_CMD not set")

    env = {**os.environ, "MINI_REDIS_DATA": str(tmp_path / "mini_redis.json")}
    db = tmp_path / "mini_redis.json"

    # Establish a clean baseline
    subprocess.run(_CMD + ["SET", "baseline", "ok"], env=env, capture_output=True)
    assert db.exists(), "Baseline write failed"
    baseline_content = db.read_text()

    # Launch a process and kill it immediately with SIGKILL
    proc = subprocess.Popen(
        _CMD + ["SET", "large", "x" * 100_000],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    time.sleep(0.01)  # let it start
    try:
        os.kill(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass  # already exited — that is fine
    proc.wait()

    # Data file must not be corrupt JSON
    if db.exists():
        try:
            json.loads(db.read_text())
        except json.JSONDecodeError:
            raise AssertionError("Data file is corrupt after SIGKILL")
```

- [ ] **Step 2: Create test_corruption.py**

```python
"""Reliability: corrupt JSON file and large value handling."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, assert_stdout, run_redis


def test_corrupt_json_exits_nonzero(tmp_path):
    """Corrupt JSON file must not crash with traceback — must exit non-zero."""
    db = tmp_path / "mini_redis.json"
    db.write_text("{ this is not valid json !!!")
    r = run_redis(["GET", "k"], data_path=db)
    assert r.returncode != 0, "Corrupt file should cause non-zero exit"
    assert r.stderr.strip() != "", "Must print error to stderr"
    assert "Traceback" not in r.stderr, "Must not print Python traceback"


def test_large_value_stored_and_retrieved(db):
    """1MB value must be stored and retrieved correctly."""
    big = "A" * 1_000_000
    r_set = run_redis(["SET", "bigkey", big], data_path=db)
    assert_success(r_set)
    r_get = run_redis(["GET", "bigkey"], data_path=db)
    assert_success(r_get)
    assert r_get.stdout.strip() == f'"{big}"'
```

---

### Task 15: Performance benchmarks

**Files:**
- Create: `harnesses/mini-redis/tests/performance/conftest.py`
- Create: `harnesses/mini-redis/tests/performance/bench_get_10k.py`
- Create: `harnesses/mini-redis/tests/performance/bench_lrange_10k.py`
- Create: `harnesses/mini-redis/tests/performance/bench_hgetall_1k.py`
- Create: `harnesses/mini-redis/tests/performance/thresholds.json`

- [ ] **Step 1: Create thresholds.json**

```json
{
  "_comment": "Performance thresholds for mini-redis. Single CLI invocation on pre-populated store.",
  "_scoring": "Score = 100 if p95 <= target_p95. Score = 0 if p95 >= fail_p95. Linear interpolation between.",
  "benchmarks": {
    "get_10k_keys": {
      "file": "bench_get_10k.py",
      "description": "GET a key from a store containing 10,000 keys",
      "target_p95_seconds": 1.0,
      "fail_p95_seconds": 5.0,
      "weight": 0.40
    },
    "lrange_10k_list": {
      "file": "bench_lrange_10k.py",
      "description": "LRANGE 0 -1 on a list with 10,000 elements",
      "target_p95_seconds": 2.0,
      "fail_p95_seconds": 10.0,
      "weight": 0.35
    },
    "hgetall_1k_fields": {
      "file": "bench_hgetall_1k.py",
      "description": "HGETALL on a hash with 1,000 fields",
      "target_p95_seconds": 1.0,
      "fail_p95_seconds": 5.0,
      "weight": 0.25
    }
  }
}
```

- [ ] **Step 2: Create performance/conftest.py**

```python
"""Performance test helpers: build pre-populated data files directly."""

import json
import time
import statistics
import os
import subprocess
import shlex
from pathlib import Path
from typing import List
import pytest


def build_string_store(path: Path, n: int) -> None:
    """Write a JSON data file with n string keys directly (fast, no subprocess)."""
    # Agent's JSON schema is unknown, so we call SET via subprocess for one key
    # then read the schema to understand the format, then write directly.
    # Simpler: write n keys via batched MSET subprocess calls.
    import shlex, os
    cmd_str = os.environ.get("MINI_REDIS_CMD", "")
    if not cmd_str:
        pytest.skip("MINI_REDIS_CMD not set")
    cmd = shlex.split(cmd_str)
    env = os.environ.copy()
    env["MINI_REDIS_DATA"] = str(path)
    # MSET all keys at once
    args = []
    for i in range(n):
        args += [f"key{i}", f"value{i}"]
    subprocess.run(cmd + ["MSET"] + args, env=env, capture_output=True)


def time_command(cmd_args: list, data_path: Path, n: int = 7) -> dict:
    """Run a redis command n times and return p50/p95/p99 stats."""
    import shlex, os
    cmd_str = os.environ.get("MINI_REDIS_CMD", "")
    if not cmd_str:
        pytest.skip("MINI_REDIS_CMD not set")
    cmd = shlex.split(cmd_str)
    env = os.environ.copy()
    env["MINI_REDIS_DATA"] = str(data_path)

    samples = []
    for _ in range(n):
        start = time.perf_counter()
        subprocess.run(cmd + cmd_args, env=env, capture_output=True)
        samples.append(time.perf_counter() - start)

    samples.sort()
    def percentile(data, p):
        idx = int(len(data) * p / 100)
        return data[min(idx, len(data) - 1)]

    return {
        "p50": percentile(samples, 50),
        "p95": percentile(samples, 95),
        "p99": percentile(samples, 99),
    }
```

- [ ] **Step 3: Create bench_get_10k.py**

```python
"""Performance: GET from a store with 10,000 keys."""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from conftest import build_string_store, time_command


@pytest.fixture(scope="module")
def store_10k(tmp_path_factory):
    db = tmp_path_factory.mktemp("perf") / "mini_redis.json"
    build_string_store(db, 10_000)
    return db


def test_get_10k_p95_within_target(store_10k):
    stats = time_command(["GET", "key5000"], data_path=store_10k, n=7)
    print(f"\nget 10k keys — p50={stats['p50']:.3f}s p95={stats['p95']:.3f}s p99={stats['p99']:.3f}s")
    assert stats["p95"] < 5.0, f"p95 {stats['p95']:.2f}s exceeds fail threshold 5.0s"
    if stats["p95"] > 1.0:
        pytest.xfail(f"p95 {stats['p95']:.2f}s exceeds target 1.0s but under fail threshold")
```

- [ ] **Step 4: Create bench_lrange_10k.py**

```python
"""Performance: LRANGE 0 -1 on a 10,000-element list."""

import os, shlex, subprocess, sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from conftest import time_command


@pytest.fixture(scope="module")
def list_10k(tmp_path_factory):
    db = tmp_path_factory.mktemp("perf") / "mini_redis.json"
    cmd_str = os.environ.get("MINI_REDIS_CMD", "")
    if not cmd_str:
        pytest.skip("MINI_REDIS_CMD not set")
    cmd = shlex.split(cmd_str)
    env = os.environ.copy()
    env["MINI_REDIS_DATA"] = str(db)
    # RPUSH 10k items in one call
    items = [str(i) for i in range(10_000)]
    subprocess.run(cmd + ["RPUSH", "biglist"] + items, env=env, capture_output=True)
    return db


def test_lrange_10k_p95_within_target(list_10k):
    stats = time_command(["LRANGE", "biglist", "0", "-1"], data_path=list_10k, n=5)
    print(f"\nlrange 10k list — p50={stats['p50']:.3f}s p95={stats['p95']:.3f}s p99={stats['p99']:.3f}s")
    assert stats["p95"] < 10.0
    if stats["p95"] > 2.0:
        pytest.xfail(f"p95 {stats['p95']:.2f}s exceeds target 2.0s")
```

- [ ] **Step 5: Create bench_hgetall_1k.py**

```python
"""Performance: HGETALL on a hash with 1,000 fields."""

import os, shlex, subprocess, sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from conftest import time_command


@pytest.fixture(scope="module")
def hash_1k(tmp_path_factory):
    db = tmp_path_factory.mktemp("perf") / "mini_redis.json"
    cmd_str = os.environ.get("MINI_REDIS_CMD", "")
    if not cmd_str:
        pytest.skip("MINI_REDIS_CMD not set")
    cmd = shlex.split(cmd_str)
    env = os.environ.copy()
    env["MINI_REDIS_DATA"] = str(db)
    args = []
    for i in range(1_000):
        args += [f"field{i:04d}", f"value{i}"]
    subprocess.run(cmd + ["HSET", "bighash"] + args, env=env, capture_output=True)
    return db


def test_hgetall_1k_p95_within_target(hash_1k):
    stats = time_command(["HGETALL", "bighash"], data_path=hash_1k, n=5)
    print(f"\nhgetall 1k fields — p50={stats['p50']:.3f}s p95={stats['p95']:.3f}s p99={stats['p99']:.3f}s")
    assert stats["p95"] < 5.0
    if stats["p95"] > 1.0:
        pytest.xfail(f"p95 {stats['p95']:.2f}s exceeds target 1.0s")
```

---

### Task 16: Update .gitignore and finalize

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add held-out directory to .gitignore**

Add to `.gitignore`:
```
harnesses/mini-redis/tests/held-out/test_*.py
```

- [ ] **Step 2: Verify test collection works end-to-end**

Run: `python -m pytest harnesses/mini-redis/tests/tier1/ harnesses/mini-redis/tests/tier2/ harnesses/mini-redis/tests/tier3/ --collect-only -q 2>&1 | tail -5`
Expected: Shows collected test count, no errors.

- [ ] **Step 3: Verify scorer unit tests still pass**

Run: `python -m pytest tests/ -v`
Expected: 6 tests pass.

- [ ] **Step 4: Final commit**

```bash
git add harnesses/mini-redis/ .gitignore
git commit -m "feat: complete mini-redis harness

Extension tests (16 sorted-set tests), reliability tests (7 scenarios),
performance benchmarks (3 benchmarks with thresholds.json),
and .gitignore entry for held-out tests."
```
