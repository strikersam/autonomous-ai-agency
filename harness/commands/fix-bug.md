# /fix-bug — Bug Fix Agent

Systematically reproduce, isolate, fix, test, and document a bug.

## Usage

`/fix-bug <description or issue number>`

## Process

1. **Understand the bug**
   - Read the issue description or error carefully
   - Identify the affected module using graphify:
   ```bash
   graphify query "<error message or symptom>"
   ```
   - Read the affected file(s)

2. **Reproduce**
   - Write a minimal reproduction case
   - Confirm the bug exists by running the reproduction:
   ```bash
   pytest -x tests/test_<module>.py::test_<case> -v
   ```
   - If no existing test covers it, write a NEW failing test first

3. **Write a failing test BEFORE fixing**
   ```python
   def test_<bug_description_snake_case>() -> None:
       """Regression test for <issue description>."""
       # Arrange: set up the scenario that causes the bug
       # Act: trigger the buggy behavior
       # Assert: verify the expected (correct) behavior
       assert result == expected  # This should FAIL before the fix
   ```
   Confirm it fails: `pytest -x tests/test_<module>.py::test_<bug>` → RED

4. **Implement the fix**
   - Make the minimal change needed to fix the bug
   - Do NOT refactor, clean up, or change adjacent code
   - Do NOT fix other bugs while fixing this one

5. **Verify the fix**
   ```bash
   # The new test should now pass
   pytest -x tests/test_<module>.py::test_<bug>
   # Full suite should still pass
   pytest -x
   ```

6. **Update changelog**
   Add to `docs/changelog.md` under `## [Unreleased] → ### Fixed`:
   ```markdown
   - **`<file.py>` — <short description of bug>.** <Brief explanation of root cause and fix>.
   ```

7. **Commit**
   ```bash
   git add <affected files> docs/changelog.md
   git commit -m "fix(<module>): <short description>"
   ```

## Rules

- NEVER fix by deleting the failing test
- NEVER widen error catching to suppress the symptom
- NEVER increase timeouts as a fix
- ALWAYS reproduce first (failing test), then fix
- If the fix affects a RISKY MODULE, invoke `risky-module-review` before merging

## Escalation

Stop and ask the user if:
- The root cause is in a RISKY MODULE
- The fix requires changing more than 3 files
- The fix changes any API contract (request/response shape)
- The fix could break existing users' integrations
