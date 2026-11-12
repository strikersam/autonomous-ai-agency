# Audit: symlink and redirect handling in agent file access

Date: 2026-11-12. Scope: `agent/tools.py` (`WorkspaceTools`), read-only. Source: routine
backlog #1892, item 4 (Claude Code 2.1.309–2.1.314 closed a redirect bypass of an
`Edit(path)` deny rule and made `denyWrite` apply through symlinks).

**No file in a risky module was changed by this audit.** `agent/tools.py` is a rule-15
module; the two proposed patches below need `risky-module-review` and a human decision
(rule 40) before anyone applies them.

## Verdict

The workspace boundary (rule 13) holds against symlinks. Two gaps remain, both lower
severity than a symlink escape: writes through a **hard link**, and `read_file` reading
**secret files inside the workspace**.

## What was checked

`WorkspaceTools._resolve_path()` delegates to `_safe_path()` (`agent/tools.py:89`), which
calls `os.path.realpath()` on the joined path and requires the result to be the root or
start with `root + os.sep`. `self.root` is itself resolved at construction
(`agent/tools.py:56`). So symlinks are resolved **before** the boundary check.

Probed against a scratch workspace with `WorkspaceTools(...)` called directly:

| Case | Result |
|---|---|
| Read a symlink that points to a file outside the root | refused |
| Write a symlink that points to a file outside the root | refused |
| Write through a symlinked directory that points outside | refused |
| Write a dangling symlink whose target is outside | refused |
| `../` traversal | refused |
| Absolute path outside the root | refused |
| Root given as a symlink to the real workspace | allowed, and correct: the root is resolved first |
| Write a **hard link** whose other name is outside the root | **allowed; the outside file's content changed** |
| `read_file(".env")` inside the workspace | **allowed; content returned** |

Shell redirects: `WorkspaceTools` runs no shell. `run_command` is dispatched to the MCP
container (`agent/loop.py`, `_dispatch_tool`); with no container attached it returns
"run_command not available locally". So there is no host-side redirect path to bypass the
boundary. What a command does inside the container is outside this audit.

## Finding 1: hard links bypass the boundary (low)

`realpath()` cannot see hard links: a hard link inside the root is an ordinary file whose
inode may also be named outside the root. `write_file`, `apply_diff` and `edit_file` then
modify the shared inode.

Preconditions make this hard to reach: something with write access to the host workspace
must create the link, the outside file must be on the same filesystem, and the link's
creator must already be able to open the outside file. The agent's own tools cannot create
a hard link (no host shell, and `write_file` creates regular files). A cloned repository
cannot carry one either: git does not store hard links.

Proposed patch (not applied): in `write_file` and `edit_file`, refuse a target that exists
and has `os.stat(target).st_nlink > 1`, with a test that a hard-linked file is rejected and
an ordinary file is not. Cost: a repository checked out with `git worktree` or a
hard-link-based cache could trip it, so it should ship behind a Platform control,
default on.

## Finding 2: `read_file` returns secret files inside the workspace (medium)

`_searchable()` (`agent/tools.py:102`) keeps `.env`, `.env.*`, `*.env` and `keys.json` out
of `search_code` and the file index, including when a harmless-looking symlink points at
one. `read_file` and `head_file` apply no such filter, so the Executor can read a
workspace `.env` directly and its content enters the model context and any trace that
records tool output (rule 6: secrets are never logged).

Proposed patch (not applied): apply the same name check in `read_file` / `head_file`, on
both the requested name and the resolved name, and return a refusal string the model can
read. Test: `.env`, `.env.local`, `prod.env`, `keys.json` and a symlink named `notes.txt`
pointing at `.env` are all refused; `env.py` and `.envrc.example` are not. Note that the
MCP `read_file` path (`agent/loop.py:2102`) bypasses `WorkspaceTools` entirely, so the
container-side tool needs the same check to close this fully.

## Finding 3: check-then-use race (informational)

`_safe_path()` validates the path, then `Path.write_text()` opens it by name. A path
component swapped for a symlink between the two steps would be followed. Nothing in the
agent runtime can make that swap on the host, so this is recorded for completeness only.
The standard fix is to open with `O_NOFOLLOW` on the final component, or walk the path
with `openat`; not proposed now.

## Not checked

- The MCP container's own `read_file` / `write_file` / `run_command` implementations.
- macOS-specific behaviour (case-insensitive and firmlinked paths); probes ran on Linux.
- Any path through `packages/` that writes files without `WorkspaceTools`.
