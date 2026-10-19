# /qa-check — QA Agent

Run a comprehensive quality check on the current state of the codebase.

## When to use

- Before any PR merge
- After significant code changes
- On a nightly basis (automated)
- When CI fails and you need to diagnose why

## Steps

1. **Baseline test run**
   ```bash
   pytest -x --tb=short --timeout=120 \
     --ignore=tests/test_hardware.py \
     --ignore=tests/test_backend_runtime_bootstrap.py
   ```
   If baseline fails, STOP. Report the failure before proceeding.

2. **Coverage check**
   ```bash
   pytest --cov=. --cov-report=term-missing --cov-fail-under=70 \
     --ignore=tests/test_hardware.py -q
   ```
   If coverage drops below 70%, identify which modules lost coverage.

3. **Lint / type check**
   ```bash
   # Check for obvious syntax issues
   find . -name "*.py" -not -path "./.venv/*" -not -path "./.git/*" \
     -exec python -m py_compile {} +
   ```

4. **Placeholder test detection**
   ```bash
   # Find test functions with only 'pass'
   python -c "
   import ast, sys
   from pathlib import Path
   problems = []
   for f in Path('tests').rglob('test_*.py'):
       try:
           tree = ast.parse(f.read_text())
           for node in ast.walk(tree):
               if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                   body = node.body
                   if len(body) == 1 and isinstance(body[0], ast.Pass):
                       problems.append(f'{f}:{node.lineno}: {node.name}')
       except: pass
   if problems:
       print('PLACEHOLDER TESTS FOUND:')
       for p in problems: print(' ', p)
       sys.exit(1)
   else:
       print('No placeholder tests found.')
   "
   ```

5. **Date-stamped test file check**
   ```bash
   ls tests/test_daily_*.py 2>/dev/null && echo "WARNING: date-stamped test files found"
   ```

6. **Missing return type annotation check (spot check)**
   ```bash
   grep -rn --include="*.py" -E "^def [a-z]" agent/loop.py router/model_router.py | \
     grep -v "-> " | head -20
   ```

7. **Report**
   - If all checks pass: "QA check passed — tests green, coverage ≥70%, no placeholders"
   - If checks fail: list each failure with file:line references
   - For recurring test failures: create GitHub issue with `bug` + `test` labels

## What NOT to do

- Do not fix failing tests by deleting them
- Do not increase timeouts to make flaky tests pass
- Do not skip tests without adding a `@pytest.mark.skip(reason="...")` explanation
