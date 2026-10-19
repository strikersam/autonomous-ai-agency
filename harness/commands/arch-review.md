# /arch-review — Architecture Agent

Review architectural decisions, identify technical debt, and propose improvements.

## When to use

- Before planning a multi-file feature (use with `/plan`)
- Monthly architecture review
- When a file exceeds 800 lines
- When adding a new module or package

## Steps

1. **Read current architecture**
   - Read `audit/architecture.md` for the baseline
   - Read `audit/technical-debt.md` for open debt items
   - Run `graphify query "architecture overview"` for current state

2. **Identify the change scope**
   ```bash
   git diff --name-only main..HEAD
   ```
   Map changed files to the architecture layers in `AGENTS.md`.

3. **Module boundary check**
   - Does the change respect existing module boundaries?
   - Are new abstractions introduced? Are they necessary?
   - Does any file now exceed 800 lines?

4. **Dependency direction check**
   - Does the change introduce circular imports?
   - Does the change add a dependency from a lower layer to a higher layer?
   ```bash
   python -c "
   import ast, sys
   from pathlib import Path
   # Quick circular import detector
   for f in Path('.').glob('*.py'):
       try:
           src = f.read_text()
           tree = ast.parse(src)
           imports = [n.names[0].name if isinstance(n, ast.Import) else n.module
                     for n in ast.walk(tree) 
                     if isinstance(n, (ast.Import, ast.ImportFrom)) and n.module]
           # Flag proxy importing from backend
           if 'backend' in str(f) and 'proxy' in str(imports):
               print(f'WARNING: {f} imports from proxy (reverse dependency)')
       except: pass
   "
   ```

5. **Technical debt impact**
   - Will this change increase or decrease technical debt?
   - If it increases debt (e.g., adds to a god file), create a follow-up issue

6. **ADR requirement check**
   - Does this change a fundamental architectural decision?
   - If yes, draft an ADR in `docs/adrs/`

7. **Report**
   Format: "Architecture review for [scope]: [PASS|CONCERN|BLOCK]"
   - PASS: change is architecturally sound
   - CONCERN: change is acceptable but creates debt (document in PR description)
   - BLOCK: change violates architectural principles (must be redesigned)

## Key Architectural Principles

1. **Proxy is the gateway.** `proxy.py` handles auth, rate limiting, and routing only. Business logic lives in services.
2. **Router is stateless.** `router/model_router.py` makes routing decisions based only on the request and config. No state.
3. **Agent is sandboxed.** Agent file writes go through `WorkspaceTools._resolve_path()`. No exceptions.
4. **Storage is abstracted.** Code uses the store abstraction, not MongoDB/SQLite directly.
5. **Backends are pluggable.** Provider/model selection is configurable via env vars, not hardcoded.
