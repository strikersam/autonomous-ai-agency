# Agent Rules

Drop-in discipline rules for any coding agent. Reference this file from your `CLAUDE.md`,
`AGENTS.md`, `GEMINI.md` or Cursor rules, or paste it in.

They matter most for agents that run without a coding-assistant system prompt behind them
(open-weights models called from your own loop), which otherwise tend to report checks
they never ran and invent file paths.

Numbering matches the Autonomous AI Agency `CLAUDE.md` §2, where these rules come from.

45. **Verify before asserting.** Re-derive counts, line numbers, and paths from the
    repo, not from memory and not from another document. Documents drift. If a number
    appears in your answer, you ran the command that produced it.
46. **Never report a check you did not run.** No "tests pass", "verified", or "confirmed
    working" without the output. If you could not run it, say which check and why.
47. **Mark known versus guessed, and never guess an identifier.** A file path, function
    name, env var, or config key is either one you have seen in the repo or one you say
    you could not find. Inventing a plausible-looking one is the most costly error
    available to you.
48. **Answer the whole request.** If you deliberately leave a part undone, say which
    part and why. Silent partial delivery reads as completion.
<!-- pstack-verification:start -->
49. **No "done" without an independent verifier (pstack).** Before any task is reported
    done, by a coding agent or by an agency agent, a verifier that did not write the
    change tries to break it. It exercises the real artifact (runs the feature, the
    tests, the built page; not "it compiles", not the author's own report) and returns
    `PASS`, `PASS+NOTES`, or `FAIL` with a report: what it checked, what it found broken,
    what was fixed, and the evidence (command output; screenshots for any UI change).
    `FAIL` sends the work back: fix every defect it found, then verify again, until it
    passes. Only `PASS` or `PASS+NOTES` permits a done claim, and the report quotes that
    verdict. Work in small units that each end in a check. Agency tasks enforce this in
    code (`tasks/verification.py`, live control `TASK_VERIFICATION_REQUIRED`). Source:
    pstack's `principle-prove-it-works` and its independent per-PR verdict
    (github.com/cursor/plugins/tree/main/pstack, github.com/michael-denyer/pstack-claude).
    This rule is mirrored byte-for-byte in every agent instruction file;
    `python scripts/check_verification_rule.py` fails if a copy drifts.
<!-- pstack-verification:end -->
