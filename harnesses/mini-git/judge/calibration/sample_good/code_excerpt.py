"""
Representative excerpts from a high-quality mini-git implementation.
These are illustrative; a real calibration sample would be actual agent output.
"""

# === objects.py (plumbing layer) ===

import hashlib
import zlib
from pathlib import Path


def hash_object(data: bytes, obj_type: str, repo_path: Path, write: bool = True) -> str:
    """Compute SHA1 of a git object, optionally writing to object store."""
    header = f"{obj_type} {len(data)}\x00".encode()
    full = header + data
    sha = hashlib.sha1(full).hexdigest()
    if write:
        obj_path = repo_path / ".git" / "objects" / sha[:2] / sha[2:]
        obj_path.parent.mkdir(parents=True, exist_ok=True)
        if not obj_path.exists():
            obj_path.write_bytes(zlib.compress(full))
    return sha


def read_object(sha: str, repo_path: Path) -> tuple[str, bytes]:
    """Read and decompress a git object. Returns (type, content)."""
    obj_path = repo_path / ".git" / "objects" / sha[:2] / sha[2:]
    raw = zlib.decompress(obj_path.read_bytes())
    header, _, content = raw.partition(b"\x00")
    obj_type, _ = header.decode().split(" ", 1)
    return obj_type, content


# === commands/cmd_commit.py (porcelain layer) ===

def cmd_commit(repo_path: Path, message: str) -> None:
    """Create a commit from the current index."""
    from objects import hash_object, read_object
    from index import read_index
    from refs import read_head, write_ref

    entries = read_index(repo_path)
    if not entries:
        raise RuntimeError("nothing to commit")

    # Build tree object
    tree_data = _build_tree(entries, repo_path)
    tree_sha = hash_object(tree_data, "tree", repo_path)

    # Build commit object
    parent = read_head(repo_path)
    commit_data = _build_commit(tree_sha, parent, message)
    commit_sha = hash_object(commit_data, "commit", repo_path)

    # Update HEAD
    head_ref = _get_head_ref(repo_path)
    write_ref(head_ref, commit_sha, repo_path)

    print(f"[{_short_sha(commit_sha)}] {message}")
