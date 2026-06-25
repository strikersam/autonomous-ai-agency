# claude-mem Plugin — Persistent Memory for All Sessions

This repo auto-enables [`claude-mem`](https://github.com/thedotmack/claude-mem)
(a persistent memory / cross-session context-compression plugin for Claude Code)
for **every** session that opens it — CLI, web, and mobile.

## How it's wired

The plugin is declared in the committed `.claude/settings.json` so no interactive
`/plugin` command is needed. Any session that opens (and trusts) this repo gets it:

```json
{
  "extraKnownMarketplaces": {
    "thedotmack": {
      "source": {
        "source": "github",
        "repo": "thedotmack/claude-mem",
        "ref": "v13.6.2",
        "sha": "dddb2d3e7d3886e1201503c209bf71d35e4bef7b"
      }
    }
  },
  "enabledPlugins": {
    "claude-mem@thedotmack": true
  }
}
```

- `extraKnownMarketplaces.thedotmack` registers the GitHub marketplace.
- `enabledPlugins["claude-mem@thedotmack"]` enables the plugin by default.
- Marketplace name (`thedotmack`) and plugin name (`claude-mem`) are verified
  against the upstream `.claude-plugin/marketplace.json` (plugin v13.6.2).

### Why the source is pinned (`ref` + `sha`)

Plugins can execute arbitrary code, and GitHub sources track the repo's
**default branch** unless pinned — so without a pin, every new trusted session
would run whatever upstream publishes *later*, not the version reviewed here.
We pin to the reviewed tag **`v13.6.2`** and its immutable commit
**`dddb2d3e7d3886e1201503c209bf71d35e4bef7b`** so the code is frozen to a known
state. (`sha` is the immutable guarantee; `ref` is the human-readable label.)

**To upgrade:** review the upstream diff for the new release, then bump both
`ref` and `sha` together (resolve the SHA with
`git ls-remote --tags https://github.com/thedotmack/claude-mem vX.Y.Z`) and
update the version mentions in this doc.

## Scope and limits

| Reach | Covered? |
|-------|----------|
| Future sessions in **this repo** (CLI / web / mobile) | ✅ Yes |
| Sessions **already running** when this landed | ❌ Restart required |
| Your **other repos** | ⚠️ Copy the same block into each repo's `.claude/settings.json` |
| Machine-global (`~/.claude`) across everything | ❌ No user-level web/mobile sync exists; per-repo config is the only path that reaches mobile |

## Enabling it elsewhere

**Per repo (recommended for web/mobile):** paste the JSON block above into that
repo's `.claude/settings.json` and commit it.

**On your local machine (CLI only):** run inside Claude Code —
```
/plugin marketplace add thedotmack/claude-mem
/plugin install claude-mem
```

## Notes

- `claude-mem` is a **third-party** plugin that captures session content into a
  local memory store. The first web/mobile session may show a one-time prompt to
  trust the `thedotmack` marketplace.
- The plugin itself is cached under `~/.claude/plugins/cache/` at session start;
  it is not vendored into this repo.
