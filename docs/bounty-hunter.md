# Bounty hunter

Agents look for funded open-source issues, write a fix, and claim the bounty
once you approve. It runs in GitHub Actions
(`.github/workflows/bounty-hunter.yml`), and the code lives in
`packages/bounty/`.

## What happens on each run (every 3 hours)

1. **Sweep.** Every submitted PR is checked. A merged PR moves to `merged`, a
   payout comment from the platform's bot naming your login moves it to
   `paid`, and a PR closed without merging moves it to `lost`.
2. **Budget.** New attempts per run = `min(BOUNTY_MAX_ATTEMPTS_PER_RUN,
   BOUNTY_MAX_OPEN_REVIEWS − reviews already waiting)`. A full review queue
   means no new work.
3. **Discover.** The hunter searches GitHub for each platform in
   `BOUNTY_PLATFORMS`:
   - **Algora:** issues with the `💎 Bounty` label.
   - **Opire:** issues whose comments mention Opire.
   - **generic:** issues with a `bounty` label. Off by default, because the
     payout route varies.
4. **Triage.** Deterministic; no LLM decides where to spend effort. A bounty
   is rejected if any of these hold:
   - the repo is archived, or has had no pushes for `BOUNTY_MAX_REPO_IDLE_DAYS`
   - the amount is below `BOUNTY_MIN_USD`
   - the bounty was already awarded (a bot comment says so; Algora leaves the
     label on after paying)
   - the repo's contribution policy refuses AI-generated PRs
   - the issue is older than `BOUNTY_MAX_ISSUE_AGE_DAYS`
   - more than `BOUNTY_MAX_COMPETITORS` other people have posted `/attempt` or
     `/claim`
   - no agent covers the repo's language

   Survivors are scored as `amount × 1/(1+competitors) × freshness`.
5. **Allocate.** Each agent (`hunter-python`, `hunter-web`, `hunter-systems`)
   has a profit-and-loss account. Revenue is paid bounties. Cost is LLM spend
   plus `BOUNTY_REVIEW_COST_USD` for every attempt that took up your review
   time. Agents still on probation share slots equally, earners get slots in
   proportion to their return, and an agent that reaches
   `BOUNTY_RETIRE_AFTER_ATTEMPTS` attempts without earning is retired.
6. **Solve.** The repo is cloned without credentials. The agent can list,
   read, search and write files inside the clone, and run the project's tests.
   - Tests run in Docker with no network and none of the runner's environment.
     Dependencies are installed by a separate container, which also gets no
     secrets.
   - The agent has no shell and no network, so an issue written to
     prompt-inject it can at worst produce a bad patch.
   - LLM calls go through `packages/ai/router.py`, using free providers only.
7. **Guard.** The patch is rejected if any of these hold:
   - it is empty, or longer than `BOUNTY_MAX_DIFF_LINES`
   - it deletes a file, touches `.github/` or another CI config, or changes a
     binary
   - it contains anything shaped like a credential
   - the project's tests fail after the change
8. **Park for review.** The fix is pushed to a branch on your fork, and an
   issue labelled `bounty-hunt` + `bounty:awaiting-review` is opened here. It
   holds the diff, the test log, and a compare link.

## Your part

- Add **`bounty:approved`** to a review issue. The workflow re-checks that the
  bounty is still open and unpaid, then opens the upstream PR from your fork.
  The PR body carries `Fixes #N`, `/claim #N`, and a line saying the change
  was AI-assisted.
- Add **`bounty:declined`** to drop it.
- Only labels added by the repository owner trigger anything.
- There is **no automatic submission**: every upstream PR goes out under your
  name, so each one needs your label.
- When the maintainer asks for changes on the upstream PR, you answer. The
  hunter does not reply to reviews.

The **Bounty hunter ledger** issue (label `bounty:ledger`) is rewritten after
every run with each agent's P&L.

## Setup

1. Create an Algora account (and Opire, if enabled) with the GitHub login that
   will submit, and finish its payout onboarding (Stripe Connect).
2. Make sure the `GH_PAT` secret belongs to that login and can fork public
   repositories, push to your forks and open pull requests on public
   repositories. A classic token with `public_repo` covers this.
3. Set the repository variable `BOUNTY_HUNTER_ENABLED=true`. Optionally set
   `BOUNTY_GITHUB_LOGIN`, which defaults to the repository owner.
4. At least one free, tool-calling LLM key must be set (`NVIDIA_API_KEY`,
   `GROQ_API_KEY` or `CEREBRAS_API_KEY`).

## Expectations

Public bounty boards are crowded with other agents. A fresh Algora bounty can
draw many competing PRs within hours, and most listed bounties turn out to be
paid or abandoned already. The triage filters exist because of this. Expect
few accepted candidates per run, and expect most attempts not to win. The
ledger shows the real numbers.

## Switches

All of these are GitHub repository variables (Settings → Secrets and variables
→ Actions → Variables), because the hunter runs in Actions, where dashboard
overrides do not reach. `AGENCY_KILL_SWITCH=true` also stops it. Defaults and
meanings are in `docs/configuration-reference.md` under "Bounty hunter".
