# /devops-check — DevOps Agent

Audit CI/CD pipelines, deployment configuration, and operational readiness.

## When to use

- Before any release
- When CI workflows fail unexpectedly
- When deploying a new environment
- Monthly production health review

## Steps

1. **CI status check**
   ```bash
   # Check recent workflow results (via GitHub MCP if available)
   # Or review .github/workflows/ for known issues
   ls .github/workflows/
   ```

2. **Workflow configuration audit**
   - Verify `ci.yml` runs tests on every push
   - Verify `security-scan.yml` runs CodeQL and bandit
   - Verify `deploy-backend.yml` only deploys from `master`
   - Check for hardcoded secrets in workflow files:
   ```bash
   grep -rn --include="*.yml" "password\|secret\|token\|key" .github/workflows/ | \
     grep -v "\${{" | grep -v "#" | grep -v "example"
   ```

3. **Docker image audit**
   ```bash
   # Check Dockerfiles for security issues
   grep -n "USER root\|--privileged\|sudo" Dockerfile* 2>/dev/null
   # Check .dockerignore
   cat .dockerignore 2>/dev/null || echo "WARNING: No .dockerignore found"
   ```

4. **Environment variable completeness**
   ```bash
   # Check that .env.example has all required vars
   cat .env.example 2>/dev/null | grep -v "^#" | grep -v "^$" | sort
   # Compare against vars used in proxy.py
   grep -n "os.environ.get" proxy.py | head -30
   ```

5. **Production readiness gate**
   - Read `audit/production-readiness.md`
   - Check which Must-Fix items are still open
   - Run doctor endpoint if server is available

6. **Dependency freshness check**
   ```bash
   pip list --outdated 2>/dev/null | head -20
   ```

7. **Report**
   - Green: all CI checks pass, no critical issues found
   - Yellow: non-blocking issues found (document in PR description)
   - Red: blocking issues found (must fix before release)

## Deployment Checklist

Before any production deployment:
- [ ] `pytest -x` passes locally
- [ ] No hardcoded secrets in workflow files
- [ ] Docker images build successfully
- [ ] Environment variables documented in `.env.example`
- [ ] `docs/changelog.md` has unreleased changes documented
- [ ] Health endpoint responds correctly
- [ ] No open P0/P1 security issues
