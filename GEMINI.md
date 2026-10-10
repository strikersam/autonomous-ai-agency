# GEMINI.md — Gemini CLI

The binding ruleset for every agent in this repository is [`CLAUDE.md`](/CLAUDE.md) §1 and §2.
Read it before changing code. The verification rule is repeated here because it gates every
"done" claim.

## Verification rule (mirrored from CLAUDE.md §2, binding on every agent)

<!-- pstack-verification:start -->
49. **No "done" without an independent verifier (pstack).** Before any task is reported
    done, by a coding agent or by an agency agent, a verifier that did not write the
    change exercises the real artifact (runs the feature, the tests, the built page; not
    "it compiles", not the author's own report) and returns `PASS`, `PASS+NOTES`, or
    `FAIL` with the evidence it observed. `FAIL` sends the work back. Only `PASS` or
    `PASS+NOTES` permits a done claim, and the report quotes that verdict. Work in small
    units that each end in a check, and verify each before starting the next. Source:
    pstack's `principle-prove-it-works` and its independent per-PR verdict
    (github.com/cursor/plugins/tree/main/pstack, github.com/michael-denyer/pstack-claude).
    This rule is mirrored byte-for-byte in every agent instruction file;
    `python scripts/check_verification_rule.py` fails if a copy drifts.
<!-- pstack-verification:end -->
