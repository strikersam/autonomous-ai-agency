# Conflicts and Stale Facts

Every figure below was re-derived in this repo at audit time. The command that
produced it is shown, so you can re-run any of them.

---

## C1 — The bill of materials is wrong in both directions

`CLAUDE.md` §4 and `AGENTS.md` "Codebase Map" both publish sizes, and they
disagree with each other *and* with the repo.

| Claim | `CLAUDE.md` | `AGENTS.md` | Actual | Command |
|-------|------------|------------|--------|---------|
| `backend/server.py` | 9,667 lines | 6,487 lines | **10,666** | `wc -l < backend/server.py` |
| `proxy.py` | "3400+ lines" | 1,719 lines | **4,116** | `wc -l < proxy.py` |
| Python files | 628 | — | **901** | `find . -name '*.py' -not -path './.git/*' -not -path './node_modules/*'` |
| Python test files | 297 | — | **431** | `find tests -name 'test_*.py'` |
| Loop registry entries | 34 | — | **37** | `python3 -c "import yaml; print(len(yaml.safe_load(open('loops/registry.yaml'))['loops']))"` |

Why it matters beyond tidiness: `AGENTS.md` §8 sets a hard 800-line file limit and
then lists `backend/server.py` at 6,487 lines as if that were the current state. It
is 10,666. An agent trusting the map would size a change against a file 4,179 lines
smaller than the one it is about to edit.

---

## C2 — Three different answers to "where do I read env vars?"

The rule "never read environment variables outside config modules" is stated three
times, naming three different sets of modules:

| Source | Names |
|--------|-------|
| `CLAUDE.md` §3, forbidden-patterns row 2 | `packages/ai/brain.py`, `packages/ai/brain_config.py` |
| `CLAUDE.md` §3, forbidden-patterns last row | `packages/ai/brain.py`, `app_settings.py` |
| `.openhands/microagents/repo.md` | `brain_policy.py`, `packages/config/` |

`brain_policy.py` **does not exist** (`ls brain_policy.py` → No such file). The
other four paths all exist. Kept rule 5 resolves this by naming the union of the
files that are actually present: `packages/ai/brain.py`,
`packages/ai/brain_config.py`, `app_settings.py`, `packages/config/`. Confirm that
union is what you want before it goes into force.

---

## C3 — Two different file-size limits

| Source | Limit |
|--------|-------|
| `AGENTS.md` §8 Coding Standards | 800 lines, with two written exceptions |
| `ENGINEERING_STANDARDS.md` §1 File rules | 500 lines |

Kept rule 28 takes 800, because that is the number the two recorded exceptions in
`AGENTS.md` are written against — `packages/config/control_catalogue.py` and
`services/ceo_dispatcher.py` are both justified relative to an 800-line limit, and
adopting 500 would silently put many more files in violation. Say if you want 500.

---

## C4 — The frontend does not deploy to Vercel

`AGENTS.md` "Production" table lists *Frontend SPA → Vercel*, and "Deploy Frontend"
says "Push to `master` → `deploy-frontend.yml` → Vercel redeploys automatically."

`grep -rliE 'vercel' .github/workflows/` returns **nothing**. The actual
`deploy-frontend.yml` is titled *Deploy Frontend to GitHub Pages* and calls
`actions/deploy-pages@v5`. `CLAUDE.md` §1 gets this right (Cloudflare Worker +
GitHub Pages).

Related: the two files disagree on the production URL and the repo identity —
`CLAUDE.md` says `autonomous-ai-agency.strikersam.workers.dev` and repo
`strikersam/autonomous-ai-agency`; `AGENTS.md` says
`local-llm-server.strikersam.workers.dev`, calls the repo `local-llm-server`, and
lists a placeholder backend URL `https://relay.example.com`. The git remote is
`https://github.com/strikersam/autonomous-ai-agency`, so `AGENTS.md` is describing
the repository under its former name.

---

## C5 — The documented P0 escape hatch does not exist

`AGENTS.md` "Bug Triage Process" item 7: *"For P0/P1: bypass changelog requirement,
fix directly, document after."*

`.claude/hooks/commit-msg` has no severity concept. It blocks any commit touching
`.py/.sh/.ps1/.bat/.yaml/.yml/.json/.toml` without a staged `docs/changelog.md`,
unless the subject starts with `chore:`, `docs:`, `style:`, `ci:`, `test:`,
`revert:`, `build:`, `wip:`, or `Merge`. An agent following item 7 during a P0
outage gets blocked, and the only documented way through is `--no-verify`, which
`AGENTS.md` Autonomous Maintenance item 9 forbids ("Never bypass CI. Do not use
`--no-verify`").

Resolution options: add a `hotfix:` exempt prefix to the hook, or delete item 7.
Kept rule 34 currently states the hook's real behaviour and omits item 7.

---

## C6 — `CLAUDE.md` §14.11 conflicts with §14.9

§14.11 mandates an 8-item verification gate "on every answer before sending", with
"If any item fails: fix it, then run the gate again from item 1. Never send
anyway." §14.9 mandates "Match depth to the question: a one-line question gets a
short prose answer." The gate has no scale-down path, so the two directives
disagree about what a trivial question costs. Both are cut, so this resolves
itself, but it is worth knowing the section had an internal contradiction.

---

## C7 — Two `§10` headings in `CLAUDE.md`

`CLAUDE.md` numbers both "Testing Constitution" and "CI/CD Standards" as section
10, so §11–§14 are each one off from where a cross-reference would put them.
`AGENTS.md` cross-references "`CLAUDE.md` §14" by name rather than by number, so
nothing currently breaks.

---

## C8 — Duplicated rule sets that have already drifted

The same rules exist in `CLAUDE.md`, `AGENTS.md`, `ENGINEERING_STANDARDS.md`,
`.openhands/microagents/`, and — for changelog and testing — in skill files as
well. C1 through C4 are all drift between copies. The `CLAUDE.md` architectural
principle "**Never duplicate logic — one source of truth per concern**" applies to
this repository's own rule files, and is currently violated by them.
