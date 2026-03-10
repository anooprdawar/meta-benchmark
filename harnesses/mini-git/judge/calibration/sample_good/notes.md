# Sample: High-Quality Mini-Git Implementation

## What Makes This Good

This is a reference example of what a high-quality mini-git implementation
looks like, for calibrating the LLM judge. Scores are in `../scores.json`.

### Plumbing vs Porcelain Separation (Score: 85/100)

The implementation cleanly separates:
- `objects.py` — read_object, write_object, hash_object (pure storage layer)
- `index.py` — read_index, write_index, add_to_index (staging layer)
- `refs.py` — read_ref, write_ref, update_head (refs layer)
- `commands/` — one file per command (cmd_commit.py, cmd_log.py, etc.)

The commands call into the plumbing layer but never directly touch .git/objects/.
This mirrors how real git separates `git hash-object` from `git commit`.

Minor deduction: the `cmd_log.py` file contains one instance of direct SHA
string construction that should live in `objects.py`.

### Object Model Abstraction (Score: 80/100)

```python
@dataclass
class Blob:
    content: bytes

    def serialize(self) -> bytes:
        header = f"blob {len(self.content)}\x00".encode()
        return header + self.content

    @classmethod
    def deserialize(cls, data: bytes) -> "Blob":
        _, _, content = data.partition(b"\x00")
        return cls(content=content)

@dataclass
class Commit:
    tree: str
    parent: str | None
    author: str
    message: str
    ...
```

Clean, explicit classes with serialize/deserialize. SHA computation is
centralized in a `hash_object()` function that takes any serializable object.

Minor: Tree entry sorting (by name) is done inline in `cmd_commit` rather than
in `Tree.serialize()`.

### Naming Consistency (Score: 90/100)

- All commands follow `cmd_<verb>` naming
- All plumbing functions follow `<verb>_<noun>` naming (read_object, write_object)
- SHA variables consistently named `sha` (not sometimes `hash` or `oid`)
- Repository state consistently accessed through `repo_path / ".git"`

Very consistent throughout.

### Test Quality (Score: 75/100)

Tests cover all Tier 1-2 commands with good edge case coverage. Notably:
- Tests verify object files are created on disk, not just exit codes
- Tests check SHA consistency (same content → same SHA)
- Tests verify HEAD updates correctly after commit

Gaps:
- Tier 3 commands have only happy-path tests
- No tests for binary file handling
- Stash tests missing

### Scope Discipline (Score: 95/100)

Implements exactly what was asked. No extra commands. No --verbose flags
or config file parsing that wasn't requested. One small addition: a `--help`
flag on each command (reasonable, not penalized).
