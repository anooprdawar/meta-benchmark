"""
Representative excerpts from a low-quality mini-git implementation.
These are illustrative; a real calibration sample would be actual agent output.
"""

# Everything in one file — no separation of concerns

import hashlib
import json
import os
import sys


def init():
    os.makedirs(".git/objects", exist_ok=True)
    os.makedirs(".git/refs/heads", exist_ok=True)
    with open(".git/HEAD", "w") as f:
        f.write("ref: refs/heads/main")
    print("Initialized empty repository")


def add(filepath):
    with open(filepath) as f:
        content = f.read()
    # BUG: no git object header format, no zlib compression
    sha = hashlib.sha1(content.encode()).hexdigest()
    os.makedirs(f".git/objects/{sha[:2]}", exist_ok=True)
    with open(f".git/objects/{sha[:2]}/{sha[2:]}", "w") as f:
        f.write(content)
    # Store in a JSON index (not binary format)
    index = {}
    if os.path.exists(".git/index.json"):
        with open(".git/index.json") as f:
            index = json.load(f)
    index[filepath] = sha
    with open(".git/index.json", "w") as f:
        json.dump(index, f)


def commit(message):
    if not os.path.exists(".git/index.json"):
        print("nothing to commit")
        return
    with open(".git/index.json") as f:
        index = json.load(f)
    # BUG: tree is just the index JSON, not a proper tree object
    tree_sha = hashlib.sha1(json.dumps(index).encode()).hexdigest()
    commit_data = {
        "tree": tree_sha,
        "message": message,
        "parent": None
    }
    # Try to get parent
    if os.path.exists(".git/refs/heads/main"):
        with open(".git/refs/heads/main") as f:
            commit_data["parent"] = f.read().strip()
    # BUG: different SHA formula than add() — inconsistent
    commit_sha = hashlib.sha1(json.dumps(commit_data).encode()).hexdigest()
    with open(f".git/objects/{commit_sha[:2]}/{commit_sha[2:]}", "w") as f:
        json.dump(commit_data, f)
    with open(".git/refs/heads/main", "w") as f:
        f.write(commit_sha)
    print(f"Committed {commit_sha[:7]}: {message}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "init":
        init()
    elif cmd == "add":
        add(sys.argv[2])
    elif cmd == "commit":
        commit(sys.argv[sys.argv.index("-m") + 1])
