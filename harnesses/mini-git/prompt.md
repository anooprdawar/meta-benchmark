# Mini-Git: Agent Seed Prompt

---

Build me a minimal but real implementation of git from scratch. I want to use it as a learning tool, so it should work like the real git — not a fake simulator. Here's what I need:

---

## What to build

A command-line tool called `mini-git` (or `mgit`, your choice) that I can run against a real directory and use like git. It should store all its data in a `.git/` folder inside the repository, just like real git does.

The tool should implement these commands:

### Core commands (must work perfectly)

**`mini-git init [directory]`**
Initialize a new repository. Creates the `.git/` directory structure. Running it in an existing repo should not destroy data.

**`mini-git add <path>`**
Stage a file or directory for commit. `mini-git add .` should stage everything. This must actually write the file content into content-addressable storage — not just record the path.

**`mini-git status`**
Show what's staged, what's modified but not staged, and what's untracked. The output format should look roughly like real git's output — three sections.

**`mini-git commit -m "message"`**
Commit the staged changes. This must create an actual commit object that points to a tree snapshot of the staged files. Each commit stores: a pointer to its tree, a pointer to its parent commit (if any), the author name/email, timestamp, and the commit message.

**`mini-git log`**
Show the commit history from HEAD backwards. Support `--oneline` for the short format. Show the full SHA1, author, date, and message by default.

### Branching commands

**`mini-git branch [name]`**
Without a name: list branches (mark current with `*`). With a name: create a new branch at HEAD.

**`mini-git branch -d <name>`**
Delete a branch.

**`mini-git checkout <branch-or-sha1>`**
Switch to a branch or commit. `mini-git checkout -b <name>` creates and switches. Should refuse to switch if you'd lose uncommitted changes.

**`mini-git merge <branch>`**
Merge a branch into the current branch. Fast-forward when possible. For non-fast-forward merges, do a three-way merge and write conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) into conflicted files.

**`mini-git diff [--staged] [commit1 [commit2]]`**
Show differences in unified diff format. Without arguments: working tree vs staged. With `--staged`: staged vs last commit. With two commits: between those commits.

### Advanced commands

**`mini-git reset [--soft|--mixed|--hard] [commit]`**
Move HEAD (and the branch) to a different commit. `--soft` moves HEAD only. `--mixed` (default) also resets the index. `--hard` also resets the working tree.

**`mini-git stash`** / **`mini-git stash pop`** / **`mini-git stash list`** / **`mini-git stash drop`**
Save and restore work-in-progress. `stash` saves current changes and reverts to HEAD. `stash pop` restores the most recent stash. `stash list` shows all saved stashes. `stash drop` discards one.

---

## How storage must work

This is the important part. The storage layer must use content-addressable storage with SHA1 hashing, exactly like real git:

- Every file version stored is called a **blob**. Its key is `SHA1("blob {length}\0{content}")`.
- Every directory snapshot is a **tree**. A tree lists its entries (files and subdirectories) as `{mode} {name}\0{binary-sha1}`. The tree's key is the SHA1 of that serialized form (with a `tree {length}\0` header).
- Every commit is a **commit object** with a text body (tree SHA1, parent SHA1, author, committer, blank line, message). Its key is the SHA1 of that serialized form.
- All objects are stored compressed with zlib at the path `.git/objects/{first2}/{remaining38}`.
- When you read an object back, verify its SHA1 matches the filename. If it doesn't match, report corruption and stop.

This means if two files have identical content, they produce identical blobs and are stored once. If you commit the same tree twice, it produces the same commit SHA1 (minus the timestamp). That's the property I want.

---

## Example session I want to work

```bash
$ mkdir myproject && cd myproject
$ mini-git init
Initialized empty Git repository in /path/to/myproject/.git/

$ echo "hello world" > hello.txt
$ mini-git status
On branch main

Untracked files:
        hello.txt

$ mini-git add hello.txt
$ mini-git status
On branch main

Changes to be committed:
        new file:   hello.txt

$ mini-git commit -m "initial commit"
[main abc1234] initial commit
 1 file changed

$ mini-git log
commit abc1234...
Author: ...
Date:   ...

    initial commit

$ mini-git branch feature
$ mini-git checkout feature
Switched to branch 'feature'

$ echo "new feature" > feature.txt
$ mini-git add .
$ mini-git commit -m "add feature"
[feature def5678] add feature

$ mini-git checkout main
$ mini-git merge feature
Fast-forward
 1 file changed

$ mini-git log --oneline
def5678 add feature
abc1234 initial commit
```

---

## Language and architecture

Use Python (3.10+) or any language you prefer. I'm not specifying the architecture — design it however makes sense to you. But I do want the code to be readable and maintainable.

A few things I care about:
- The object storage layer should be cleanly separated from the CLI commands
- Error messages should be helpful — tell me what went wrong and why
- The tool should exit with code 0 on success, non-zero on error

---

## Tests

Write a test suite for this. The tests should cover:
- Object serialization/deserialization (can you write a blob and read it back correctly?)
- Each major command (at least one test per command, more for tricky ones)
- Edge cases you can think of (empty repo, empty file, binary files, filenames with spaces, etc.)

Tests should be runnable with a single command like `pytest` or `go test ./...`. They must not shell out to the real `git` binary.

---

## Deliverables

1. The implementation (one or more source files)
2. A test suite
3. A short README explaining how to run it and the test suite
4. Any dependencies listed in a requirements file

That's it. Make it work.
