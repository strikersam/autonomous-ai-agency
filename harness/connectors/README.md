# Connectors

How agents reach the outside world: MCP servers for platforms, and client configs for
pointing your editor or CLI at an OpenAI-compatible endpoint.

## MCP servers

Claude Code reads MCP servers from `.mcp.json` at the repo root. Start from
[`mcp.example.json`](mcp.example.json): copy it to `.mcp.json` and keep secrets in your
shell environment. The file references `${VAR}`; never paste a key into it.

| Server | What it gives the agent | Needs |
|---|---|---|
| Render | Deploys, logs, metrics and env vars for Render services | `RENDER_API_KEY`, Docker |
| GitHub | PRs, issues, CI status | The Claude GitHub app, or a GitHub MCP server with a token |
| Browser (`agent-browser`, `dev-browser`, `browserbase-*` skills) | Real-browser UI testing | Local Chrome, or a Browserbase key for the remote skills |

Pin the Render image by digest in production (the agency's own `.mcp.json` does). The
example uses the tag for readability.

Hosted connectors (Gmail, Drive, Slack, Linear, …) are added in your Claude account's
connector settings, not in this file.

## Client configs

[`clients/`](clients/) has ready-made configs for tools that speak the OpenAI API:

| File | Tool |
|---|---|
| `aider_config.sh`, `aider_config.ps1` | Aider |
| `codex_config.md` | OpenAI Codex CLI |
| `continue_config.yaml`, `continue_config.json` | Continue |
| `cursor_settings.json` | Cursor |
| `zed_settings.json` | Zed |
| `vscode_settings.json` | VS Code |
| `python_client_example.py`, `crispy_client.py` | Python (OpenAI SDK) |
| `quick-note-to-claude.shortcut` | Apple Shortcut for sending a quick note to the agency |

Each one expects a base URL and an API key. With the agency running locally that is
`http://localhost:8000/v1`; with any other OpenAI-compatible server, use its URL.
