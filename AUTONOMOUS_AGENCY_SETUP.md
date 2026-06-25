# Autonomous Agency Setup Guide

This guide walks through enabling and configuring the autonomous agency workflows
that keep `local-llm-server` self-maintaining.

## Overview

The autonomous agency consists of scheduled GitHub Actions workflows that run
on a regular cadence:

| Workflow | Schedule | Purpose |
|----------|----------|--------|
| `agency-cycle.yml` | Every 6 hours | CEO assessment: runs tests, classifies failures via SelfHealingAgent, dispatches Dev Agent to auto-fix, escalates if unable |
| `continuous-improvement.yml` | Daily at 09:00 UTC | ImprovementLoop scanner: detects tech debt, stale tests, and code quality issues |
| `weekly-trend-digest.yml` | Monday at 08:00 UTC | TrendWatcher: analyzes repository trends and publishes a digest |
| `ci-failure-autofix.yml` | On CI failure | Attempts to auto-fix CI failures when they occur |
| `perplexity-maintenance.yml` | Monday at 02:00 UTC | Test health checks, security scans, dependency audits, auto-merges safe Dependabot PRs |

## Prerequisites

### Required Secrets

| Secret | Purpose |
|--------|--------|
| `GITHUB_TOKEN` | Auto-provided by GitHub Actions; used for checkout |
| `GH_PAT` | Personal Access Token with repo scope; used for git push and PR operations |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude Code agent dispatch (optional; agent falls back to free NVIDIA models) |
| `NVIDIA_API_KEY` | NVIDIA API key for free-tier model access in the Dev Agent |

### Required Repository Settings

1. **Actions permissions**: Settings → Actions → General → "Allow all actions and reusable workflows"
2. **Workflow permissions**: "Read and write permissions"
3. **Branch protection**: The `master` branch requires the following status checks:
   - Test (Python 3.13)
   - Frontend test + build
   - Lint check
   - Secret / Credential Scan
   - Dependency CVE Audit
   - Bandit SAST
   - Analyze (python)
   - Analyze (javascript-typescript)
   - Security Gate — No New Alerts

## Enabling Workflows

All workflows listed above are enabled by default. To disable a specific workflow:

1. Go to the workflow file in `.github/workflows/`
2. Comment out or remove the `schedule` trigger
3. Commit and push

## The Agency Cycle in Detail

Every 6 hours, `agency-cycle.yml` runs the CEO Assessment:

1. **Baseline test run** — runs `pytest --tb=short` and captures the output
2. **Failure classification** — SelfHealingAgent classifies each failure (syntax_error, import_error, timeout, etc.)
3. **Secrets redaction** — `.github/scripts/redact_secrets.sh` strips credentials before posting
4. **CEO Assessment** — summarizes the state and issues directives
5. **Dev Agent dispatch** — if there are failures, a Claude Code agent attempts to fix them
6. **Post-fix verification** — reruns tests to verify the fix
7. **Escalation** — if tests still fail, creates a detailed GitHub issue with tracebacks and classification

### Manual Trigger

All workflows support `workflow_dispatch` — you can run them manually from the
GitHub Actions tab.

## What Happens When Tests Fail

1. The Dev Agent attempts to auto-fix the failure
2. If the fix succeeds, it commits and pushes to `master`
3. If the fix fails, an escalation issue is created with:
   - Per-test full tracebacks
   - SelfHealingAgent failure classification
   - Suggested fix per failure category
   - Structured action-required checklist

## Monitoring Health

- **GitHub Issues**: Watch for issues with the `agency-escalation` label
- **Actions tab**: Check the agency-cycle workflow run history
- **Dashboard**: The Doctor screen at `/doctor` shows real-time health checks

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Agency cycle not running | Workflow disabled or schedule removed | Check `.github/workflows/agency-cycle.yml` triggers |
| Dev Agent can't push | Missing `GH_PAT` secret | Add a PAT with repo scope to GitHub Secrets |
| Escalation issues have no details | Old workflow version | Update to latest workflow (post PR #445) |
| Cloudflare Workers Build failing | Non-prod builds enabled in Cloudflare dashboard | Disable "Builds for non-production branches" in Cloudflare Workers settings |

## Cloudflare Workers Deployment

The Cloudflare Workers deploy is now controlled by `.github/workflows/deploy-cloudflare.yml`,
which triggers only on version tags (`v*`) and `workflow_dispatch`. Make sure to disable
the automatic Cloudflare dashboard integration to avoid duplicate deploys.
