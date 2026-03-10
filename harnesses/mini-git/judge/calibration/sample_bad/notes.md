# Sample: Low-Quality Mini-Git Implementation

## What Makes This Poor

This is a reference example of a low-quality mini-git implementation,
for calibrating the LLM judge. Scores are in `../scores.json`.

### Plumbing vs Porcelain Separation (Score: 10/100)

Everything is in a single 800-line `mini_git.py` file. SHA computation,
file I/O, and command logic are interleaved throughout. Example:

```python
def commit(message):
    # Stage check
    if not os.path.exists(".git/index.json"):
        print("nothing to commit")
        return
    with open(".git/index.json") as f:
        staged = json.load(f)
    # Write blobs inline
    for path, content in staged.items():
        sha = hashlib.sha1((content).encode()).hexdigest()  # BUG: ignores binary
        os.makedirs(f".git/objects/{sha[:2]}", exist_ok=True)
        with open(f".git/objects/{sha[:2]}/{sha[2:]}", "w") as f:
            f.write(content)  # BUG: no header, no compression
    ...
```

No separation whatsoever. All git knowledge lives in command handlers.

### Object Model Abstraction (Score: 5/100)

No object model. SHA is computed ad-hoc in multiple places with different
formulas (some include the header, some don't). No Blob/Tree/Commit classes.
The "tree" is just the staged dict written directly to a JSON file.

```python
# from cmd_log:
sha = hashlib.sha1(json.dumps(commit_data).encode()).hexdigest()  # wrong format

# from cmd_add:
sha = hashlib.sha1(content.encode()).hexdigest()  # different formula, no header
```

### Naming Consistency (Score: 30/100)

Mixed conventions:
- Some functions: `do_commit()`, some: `run_add()`, some: `git_status()`
- Variables: sometimes `sha`, sometimes `hash`, sometimes `commit_id`
- File reads: sometimes `open(...).read()`, sometimes `Path(...).read_text()`

### Test Quality (Score: 20/100)

Tests exist but only check exit codes:
```python
def test_commit():
    result = subprocess.run(["python", "mini_git.py", "commit", "-m", "msg"])
    assert result.returncode == 0  # That's all
```

No verification of object files, no SHA consistency checks, no tree structure
verification. Happy-path only. No edge case coverage.

### Scope Discipline (Score: 60/100)

Implements all requested commands, but also added unrequested features:
- `mini-git gc` (garbage collection)
- `mini-git config` (not asked for)
- `--porcelain` flag on status (not asked for)

Moderate over-building.
