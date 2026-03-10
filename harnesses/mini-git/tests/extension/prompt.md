# Extension Prompt: Remote Operations

Your mini-git implementation is working well. Now add support for remote operations.

## What to add

Implement the following commands:

### `mini-git remote add <name> <url>`
Register a named remote. A remote is simply a name and a URL.

```
$ mini-git remote add origin https://example.com/repo.git
```

### `mini-git remote -v` (or `mini-git remote list`)
List configured remotes with their URLs.

```
$ mini-git remote -v
origin  https://example.com/repo.git
```

### `mini-git remote remove <name>`
Remove a named remote.

### `mini-git fetch <remote>`
Download objects and refs from a remote. For this exercise, a "remote" can be a
local path (e.g., `/tmp/bare-repo`) rather than a real HTTP URL. Implement fetch
to work with local paths as a minimum.

Fetch should:
- Read objects from the remote's `.git/objects/`
- Read refs from the remote's `.git/refs/`
- Create or update `refs/remotes/<remote>/<branch>` locally

### `mini-git pull <remote> <branch>`
Fetch from remote, then merge the fetched branch into the current branch.

### `mini-git push <remote> <branch>`
Send local objects and refs to the remote. Implement for local path remotes.

Push should:
- Copy missing objects to the remote
- Update the remote's ref for the branch

## Notes

- You don't need to implement HTTP. Local path remotes (another directory
  containing a `.git/` folder) are sufficient.
- Persist remote configuration in `.git/config` (INI-style) or a simpler file.
- Error clearly when a remote doesn't exist.

## Tests

Update your test suite to cover the new commands.
