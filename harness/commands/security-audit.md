# /security-audit — Security Agent

Perform a targeted security audit of the codebase or a specific module.

## When to use

- Before any PR that touches `admin_auth.py`, `key_store.py`, `agent/tools.py`, `rbac.py`, `social_auth.py`, or `proxy.py` auth middleware
- After adding a new API endpoint
- After adding a new dependency
- On a scheduled basis (monthly)

## Steps

1. **Read context**
   - Read `AGENTS.md` sections: Security Requirements, Risky Modules
   - Read `audit/security-analysis.md` for known open issues
   - Run `graphify query "security vulnerabilities"` to check known concerns

2. **Dependency audit**
   ```bash
   pip-audit --requirement requirements.txt --output json > /tmp/pip_audit.json
   cat /tmp/pip_audit.json
   ```

3. **Static analysis**
   ```bash
   # Run bandit on the codebase
   bandit -r . -x .venv,tests,node_modules --severity-level medium -f json
   ```

4. **Hardcoded secrets check**
   ```bash
   grep -rn --include="*.py" --exclude-dir=.venv --exclude-dir=tests \
     'SECRET_KEY\s*=\s*["\x27][^"]+["\x27]' .
   ```

5. **Auth path review**
   - Read `proxy.py` lines 195-292 (auth middleware)
   - Read `admin_auth.py`
   - Verify `hmac.compare_digest` or equivalent used for secret comparison
   - Verify rate limiter cannot be bypassed

6. **CORS check**
   ```bash
   grep -n "CORS_ORIGINS" proxy.py
   ```
   Verify it's not `*` in production.

7. **Agent filesystem boundary check**
   - Read `agent/tools.py _resolve_path()`
   - Verify `AGENT_WORKSPACE_ROOT` is set and does not equal repo root

8. **Report findings**
   - Severity: P0 (immediate), P1 (this sprint), P2 (next sprint)
   - Create GitHub issues for P0/P1 findings
   - Update `audit/security-analysis.md` with new findings

## Escalation

Stop and ask the user before fixing:
- Any P0 security vulnerability (immediate escalation required)
- Any change to risky modules that affects auth flows
- Any change that could break existing authenticated sessions
