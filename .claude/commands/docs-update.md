# /docs-update — Documentation Agent

Keep documentation in sync with the codebase after code changes.

## When to use

- After any PR that changes module behavior, API endpoints, or env vars
- When CLAUDE.md references feel stale
- When new features are added without documentation
- Monthly documentation health check

## Steps

1. **Identify what changed**
   ```bash
   git diff main..HEAD --name-only
   ```

2. **Map files to documentation**
   | Changed File | Docs to Update |
   |-------------|----------------|
   | `proxy.py` (new endpoint) | `docs/api-surfaces.md` |
   | `proxy.py` (new env var) | `docs/configuration-reference.md`, `.env.example` |
   | `router/` | `docs/model-routing.md`, `router/CLAUDE.md` |
   | `agent/loop.py` | `docs/architecture/agent-orchestration.md`, `agent/CLAUDE.md` |
   | `agent/tools.py` | `agent/CLAUDE.md` |
   | New service | `docs/architecture/overview.md` |
   | Auth change | `admin_auth.py` inline docs, `docs/admin-dashboard.md` |
   | New workflow | `docs/architecture/` |
   | `requirements.txt` | `audit/dependency-analysis.md` |

3. **Check changelog**
   - Is the change documented under `## [Unreleased]` in `docs/changelog.md`?
   - If not, add an entry now

4. **Check API surfaces document**
   ```bash
   # Find new endpoints in proxy.py
   grep -n "@app\.\(get\|post\|put\|delete\|patch\)" proxy.py | \
     grep -v "# already documented"
   ```

5. **Check configuration reference**
   ```bash
   # Find new env vars
   grep -n "os.environ.get" proxy.py backend/server.py | \
     grep -v "already documented" | head -30
   ```

6. **Update CLAUDE.md files**
   - Root `CLAUDE.md`: if codebase map changes
   - Module `CLAUDE.md`: if module contracts or invariants change
   - `AGENTS.md`: if agent roles, commands, or security requirements change

7. **Validate doc links**
   ```bash
   # Check for broken internal links
   grep -rn "\[.*\](docs/" *.md docs/*.md 2>/dev/null | while read line; do
     path=$(echo $line | grep -o '(docs/[^)]*)')
     path=${path:1:${#path}-2}
     if [ ! -f "$path" ]; then
       echo "BROKEN LINK: $line → $path"
     fi
   done
   ```

8. **Report**
   - List files updated
   - List any docs that should be updated but require human knowledge (flag for owner)

## Documentation Standards

- Write for a developer who just joined the team (no assumed knowledge)
- Use concrete examples, not abstract descriptions
- Code examples must be tested/runnable
- Never duplicate information — link to the canonical source instead
- Keep docs close to the code they describe (prefer module CLAUDE.md over central docs for module-specific detail)
