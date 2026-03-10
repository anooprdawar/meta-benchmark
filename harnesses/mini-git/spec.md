# Mini-Git: Product Requirements Document

**Harness ID:** mini-git
**Version:** 1.0.0
**Status:** Approved
**Owner:** Meta-Benchmark Working Group

---

## 1. Overview

### 1.1 Purpose

Mini-git is a faithful, from-scratch implementation of the core Git content-addressable object store and command interface. It is not a wrapper around the real `git` binary. Every object (blob, tree, commit) is written to disk using the same SHA1-addressed, zlib-compressed format that real Git uses — meaning a correctly implemented mini-git repository can be opened and inspected with the real `git` tool.

The goal of this harness is to present a coding agent with a single, well-scoped systems programming problem that exercises: file I/O, serialization, data structures (DAGs, trees), hash addressing, CLI design, atomic writes, and test harness construction. It is hard enough to be meaningful and scoped enough to be completable.

### 1.2 Background

Git's object model is a clean, elegant design: three object types (blob, tree, commit) stored in a content-addressable store keyed by the SHA1 of their serialized content. The staging area (index) mediates between the working tree and the object store. Refs are plain-text pointers from named branches to commit SHAs. This is a finite, specifiable design — a good agent should be able to implement it from a description alone.

### 1.3 Success Criterion

A successful implementation can initialize a repository, stage files, commit snapshots, branch, merge (fast-forward), inspect history, and survive adversarial edge cases — all without delegating to the real `git` binary.

---

## 2. Scope

### 2.1 In Scope

- Content-addressable object storage (blob, tree, commit) with SHA1 addressing
- Zlib compression of stored objects (matching real Git's format)
- Index/staging area (`.git/index`)
- Ref management (`.git/refs/heads/`, `.git/HEAD`)
- Commands: `init`, `add`, `status`, `commit`, `log`, `branch`, `checkout`, `merge`, `diff`, `reset`, `stash`
- Atomic commit protocol
- Corruption detection via SHA1 verification on read
- Test suite (unit + integration)

### 2.2 Out of Scope

The following features are explicitly excluded. An agent that implements any of these in the initial prompt response is penalized under scope discipline:

- **Networking:** No `clone`, `push`, `pull`, `fetch`, `remote`
- **Submodules**
- **Git hooks** (pre-commit, post-commit, etc.)
- **Git LFS**
- **Annotated or lightweight tags** (except for `stash` internals, which use refs under `.git/refs/stash`)
- **Rebase**
- **Cherry-pick**
- **Worktrees**
- **Shallow clones**
- **Packfiles** (loose object storage only is acceptable for this scope)
- **Config file parsing** (`.git/config`, `.gitconfig`)
- **Gitignore** (`.gitignore` parsing is a bonus, not required)

---

## 3. Object Model

### 3.1 Object Types

All objects are stored in `.git/objects/` using the path `{first-2-chars-of-sha1}/{remaining-38-chars}`. Each file is zlib-compressed. The raw content before compression follows the format:

```
{type} {byte-length}\0{content}
```

**Blob:** Stores raw file content.
- Header: `blob {byte-length}\0`
- Content: verbatim bytes of the file

**Tree:** Stores a directory snapshot.
- Header: `tree {byte-length}\0`
- Content: sorted list of entries, each:
  ```
  {mode} {filename}\0{20-byte-raw-sha1}
  ```
  Mode is `100644` for regular files, `100755` for executable, `040000` for subdirectory.
  Entries MUST be sorted lexicographically by name, with directories sorted as if they had a trailing `/`.

**Commit:** Stores a snapshot reference plus metadata.
- Header: `commit {byte-length}\0`
- Content (text, UTF-8):
  ```
  tree {tree-sha1}
  parent {parent-sha1}        (omitted for root commit; multiple lines for merge commits)
  author {name} <{email}> {unix-timestamp} {tz-offset}
  committer {name} <{email}> {unix-timestamp} {tz-offset}

  {commit message}
  ```

### 3.2 SHA1 Computation

SHA1 is computed over the raw (pre-compression) content, including the type header. The hex digest is the object's key. Implementations MUST NOT compute SHA1 over compressed content.

### 3.3 Object Deduplication

Because the key is derived from content, identical content produces identical keys. Writes to an already-existing object path are a no-op (content-addressed deduplication is automatic).

---

## 4. Index / Staging Area

The index lives at `.git/index`. It tracks which file paths have been staged and what blob SHA1 they resolve to.

### 4.1 Minimum Required Index Fields (per entry)

| Field | Type | Description |
|-------|------|-------------|
| mode | uint32 | File mode (100644, 100755) |
| sha1 | 20 bytes | Binary SHA1 of staged blob |
| path | string | Relative path from repo root |
| mtime | float | Last modification time at staging time |

Implementations may use a binary format (matching real Git's index v2) or a simpler JSON/text format. The format need not be interoperable with real Git at the index level — object interoperability is sufficient.

### 4.2 Index Semantics

- `git add <path>` writes the blob to the object store and upserts the index entry.
- `git add .` stages all modified/new files under the working tree.
- Removing a file from disk does not automatically remove it from the index; `git rm` (out of scope) would handle that. For Tier 1, a file deleted from disk simply shows as "deleted" in `git status`.

---

## 5. Refs

### 5.1 Structure

```
.git/
  HEAD               — text file: "ref: refs/heads/main\n" or a detached SHA1
  refs/
    heads/
      main           — text file: "{commit-sha1}\n"
      feature-x      — text file: "{commit-sha1}\n"
    stash            — text file: "{stash-commit-sha1}\n" (only when stash is non-empty)
```

### 5.2 Semantics

- `HEAD` normally contains a symbolic ref (`ref: refs/heads/{branch}`). In detached HEAD state (after `git checkout {sha1}`), it contains a raw SHA1.
- Branch refs are updated atomically by writing to a temp file and renaming.
- A branch ref that does not exist yet is created on first commit or `git branch`.

---

## 6. Feature Tiers

### Tier 1 — Core (40% of functional score)

All Tier 1 features must be implemented for the implementation to be considered functional.

#### 6.1 `git init [directory]`

Creates a new repository. If `directory` is omitted, initializes in the current directory. Must create:

```
.git/
  HEAD          ("ref: refs/heads/main\n")
  objects/
  refs/
    heads/
```

Output: `Initialized empty Git repository in {absolute-path}/.git/`

Edge cases:
- Running `git init` in an existing repo must not destroy existing data. Output: `Reinitialized existing Git repository in {absolute-path}/.git/`
- Must work in directories with spaces in the path.

#### 6.2 `git add <pathspec>`

Stages file(s) for commit.

- `git add <file>` — stages a single file
- `git add <dir>` — stages all files under that directory recursively
- `git add .` — stages all modified/new files from the working tree root

Behavior:
1. Read file content
2. Compute blob SHA1
3. Write blob to `.git/objects/` (if not already present)
4. Update `.git/index`

Edge cases:
- File does not exist: exit with error `fatal: pathspec '{path}' did not match any files`
- Binary files: must be handled (blob stores raw bytes)
- Empty file: valid, produces a blob with empty content
- File path with spaces: must work

#### 6.3 `git status`

Compares three states: HEAD tree, index, and working tree.

Output format (mimicking real git):
```
On branch main

Changes to be committed:
  (use "git restore --staged <file>..." to unstage)
        new file:   foo.txt
        modified:   bar.txt

Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
        modified:   baz.txt
        deleted:    qux.txt

Untracked files:
  (use "git add <file>..." to include in what will be committed)
        new_untracked.txt
```

Edge cases:
- Empty repo (no commits yet): show `No commits yet` before listing staged files
- Untracked directories: show directory name, not every file within
- Binary files: must not fail

#### 6.4 `git commit -m <message>`

Creates a commit object.

Steps:
1. Build tree object from current index (recursively for subdirectories)
2. Write tree objects (subtrees first, then root)
3. Determine parent SHA1 from HEAD (none if first commit)
4. Write commit object
5. Update current branch ref to new commit SHA1
6. Clear the index (or leave it as-is — real git leaves the index intact after commit)

Output: `[{branch} {short-sha1}] {message}\n {n} files changed, ...` (file change stats are optional but appreciated)

Edge cases:
- Nothing staged: `nothing to commit, working tree clean`
- Empty commit message (via `-m ""`): must be rejected with an error
- Committer identity: use `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL` env vars if set; otherwise use hardcoded defaults (e.g., `Mini Git User <mini@git.local>`)

#### 6.5 `git log [--oneline] [--graph] [-n <number>]`

Traverses the commit DAG from HEAD, printing commit metadata.

Default output format:
```
commit {full-sha1}
Author: {name} <{email}>
Date:   {human-readable date}

    {commit message}
```

`--oneline` format: `{short-sha1} {first-line-of-message}`

Edge cases:
- Empty repo (no commits): `fatal: your current branch 'main' does not have any commits yet`
- Merge commits: show both parents

---

### Tier 2 — Branching & Diff (35% of functional score)

#### 6.6 `git branch [<name>] [-d <name>] [-v]`

- `git branch` — list all branches, prefixing current branch with `*`
- `git branch <name>` — create a new branch pointing to HEAD commit
- `git branch -d <name>` — delete a branch (must refuse to delete the current branch)
- `git branch -v` — list branches with last commit SHA1 and message

Edge cases:
- Branch already exists: `fatal: A branch named '{name}' already exists`
- Delete non-existent branch: `error: branch '{name}' not found`
- Delete branch with unmerged commits: warn (not required to enforce)

#### 6.7 `git checkout <branch|sha1> [-- <file>]`

- `git checkout <branch>` — switch to a branch (update HEAD, update working tree, update index)
- `git checkout -b <name>` — create and switch to a new branch
- `git checkout <sha1>` — detached HEAD mode
- `git checkout -- <file>` — restore a file from the index (discard working tree changes)

Safety requirement: Must refuse to switch branches if there are uncommitted changes that would be overwritten. Output: `error: Your local changes to the following files would be overwritten by checkout: {files}`

Edge cases:
- Switching to the current branch is a no-op with a message
- Detached HEAD must show a warning message

#### 6.8 `git merge <branch>`

Implements fast-forward merge only (three-way merge is Tier 3).

Fast-forward detection:
1. Find common ancestor of current HEAD and target branch HEAD
2. If common ancestor == current HEAD, fast-forward is possible: update current branch ref to target SHA1, update working tree and index
3. If not fast-forward, output: `Automatic merge failed; fix conflicts and then commit.` and set up conflict markers (Tier 3)

Output on success: `Fast-forward\n {n} files changed...`
Output when already up to date: `Already up to date.`

Edge cases:
- Merging a branch into itself: `Already up to date.`
- Merging when working tree is dirty: warn but proceed (or refuse — implementation choice, must be documented)

#### 6.9 `git diff [--staged] [<commit1> <commit2>] [-- <file>]`

Produces unified diff output.

- `git diff` — working tree vs. index
- `git diff --staged` (or `--cached`) — index vs. HEAD
- `git diff <commit1> <commit2>` — between two commits
- `git diff <commit>` — working tree vs. that commit

Output format: standard unified diff (`--- a/file`, `+++ b/file`, `@@ -l,s +l,s @@` hunks)

Edge cases:
- Binary files: output `Binary files a/{file} and b/{file} differ`
- New file: diff from `/dev/null`
- Deleted file: diff to `/dev/null`

---

### Tier 3 — Advanced (25% of functional score)

#### 6.10 Merge Conflicts

When fast-forward is not possible, perform a three-way merge.

1. Find merge base (lowest common ancestor in commit DAG)
2. For each file: three-way merge content
3. If conflict: write conflict markers into working tree file:
   ```
   <<<<<<< HEAD
   {ours}
   =======
   {theirs}
   >>>>>>> {branch-name}
   ```
4. Stage non-conflicted files; leave conflicted files unstaged
5. Write `.git/MERGE_HEAD` with the target branch SHA1
6. Output: list of conflicted files

After resolving, user runs `git add <resolved-files>` then `git commit` (which reads MERGE_HEAD to construct merge commit with two parents).

#### 6.11 `git reset [--soft|--mixed|--hard] [<commit>]`

- `--soft` — Move HEAD (and branch ref) to `<commit>`. Index and working tree unchanged.
- `--mixed` (default) — Move HEAD, reset index to match `<commit>` tree. Working tree unchanged.
- `--hard` — Move HEAD, reset index AND working tree to match `<commit>` tree.

`<commit>` defaults to HEAD (useful for unstaging with `git reset HEAD <file>` or `git reset`).

Edge cases:
- `git reset HEAD <file>` — unstage a single file (mixed, file-level)
- `git reset --hard` on a dirty working tree: overwrites without warning (matches real git behavior)
- `git reset` past the initial commit: error

#### 6.12 `git stash [save|pop|list|drop]`

- `git stash` or `git stash save` — save current working tree + index changes, revert to HEAD
- `git stash list` — list stash entries (most recent first): `stash@{0}: WIP on {branch}: {short-sha} {message}`
- `git stash pop` — apply most recent stash and remove it from the stash list
- `git stash drop [stash@{n}]` — discard a stash entry without applying

Implementation note: Stash entries are stored as commit objects (with a special second parent encoding the index state), referenced from `.git/refs/stash`. Each `stash save` prepends to the stash ref chain.

Edge cases:
- `git stash pop` with nothing stashed: `No stash entries found.`
- `git stash pop` when working tree is dirty: apply anyway (conflicts handled like merge conflicts)
- `git stash drop stash@{N}` where N > list length: error

---

## 7. Performance Targets

These are measured on the CI runner hardware (4-core x86, SSD, Linux). Implementations exceeding these targets score 0 on the performance dimension for that sub-test.

| Operation | Condition | p95 Latency Target |
|-----------|-----------|-------------------|
| `git log` | 10,000 commit chain | < 2.0 seconds |
| `git add .` | 100,000 small files (1 KB each) | < 30 seconds |
| `git add .` | 1,000 large files (1 MB each) | < 60 seconds |
| `git status` | 100,000 file working tree | < 10 seconds |
| `git diff` | Two commits, 10,000 file tree | < 5 seconds |
| `git commit` | 100,000 staged files | < 30 seconds |
| Object read | Single blob, cold cache | < 50 ms |

---

## 8. Reliability Requirements

### 8.1 Atomic Commits

Commit operations must be atomic with respect to power loss simulation. The implementation must:
1. Write all objects to `.git/objects/` before updating any ref
2. Update branch refs by writing to a temp file in `.git/` and atomically renaming (POSIX `rename(2)` is atomic on the same filesystem)
3. Never leave HEAD pointing to a non-existent object

### 8.2 SIGTERM Handling

If the process receives SIGTERM during a `git add` or `git commit`, it must not corrupt the repository. Partially written object files are acceptable (they will be ignored on next read due to SHA1 mismatch); partially updated refs are not acceptable.

Implementation: write objects before updating refs. Any incomplete object write is detected by SHA1 verification on read and can be safely ignored or removed.

### 8.3 Corruption Detection

On every object read, verify that `SHA1(raw_content) == filename`. If mismatch: output `error: object {sha1} is corrupt` and exit non-zero. Do not silently use corrupted data.

### 8.4 Concurrent Access

Out of scope. Implementations are not required to handle concurrent repository access.

---

## 9. Test Requirements

The implementation must include:

1. **Unit tests** for the object model (blob/tree/commit serialization and deserialization)
2. **Integration tests** for each CLI command (at minimum one happy-path test per command)
3. **Edge case tests** for at least 5 of the adversarial scenarios listed in the rubric
4. Tests must be runnable with a single command (e.g., `pytest`, `go test ./...`, `cargo test`)
5. Tests must not depend on the real `git` binary (except optionally in cross-validation tests, clearly labeled as such)

---

## 10. Interface Contract

### 10.1 CLI Entry Point

The tool must be invocable as:
```
python mini_git.py <command> [args...]
```
or equivalent for the agent's chosen language. A `Makefile` or `run.sh` wrapper is acceptable.

### 10.2 Exit Codes

| Condition | Exit Code |
|-----------|-----------|
| Success | 0 |
| User error (bad args, file not found) | 1 |
| Internal error (corruption, I/O failure) | 128 |

### 10.3 Output Streams

Informational messages go to stdout. Error messages go to stderr. This is testable via subprocess capture.

---

## 11. Reference Material

The following are provided for disambiguation only — agents are not expected to produce byte-for-byte identical output to real git, but where format is unspecified, mimicking real git is preferred.

- Real git's object format: documented in `git help cat-file`
- Real git's diff output: unified diff format (RFC 3284)
- Tree entry sort order: documented in git source `tree.c`

---

*Document version 1.0.0. Last updated: 2026-03-10.*
