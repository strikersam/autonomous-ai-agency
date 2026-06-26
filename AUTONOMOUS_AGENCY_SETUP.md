# Autonomous Agency Setup
This guide provides an overview of the autonomous agency setup, including what runs, when, and how to configure it.
## Introduction
The autonomous agency setup is designed to automate various tasks, including test suite health checks, security scans, and dependabot PR management.
## Workflows
The following workflows are included in the setup:
* `agency-cycle.yml`: Runs every 6 hours to perform CEO assessments, dev/security/scout agent tasks, and auto-fixes.
* `continuous-improvement.yml`: Runs daily at 09:00 UTC to test and scan for FIXME/TODO issues.
* `weekly-trend-digest.yml`: Runs every Monday at 08:00 UTC to fetch trends from arXiv, HuggingFace, Ollama, and GitHub.
* `ci-failure-autofix.yml`: Runs on every CI failure to generate a Claude Sonnet 4.6 patch and verify it.
* `perplexity-maintenance.yml`: Runs every Tuesday at 07:00 UTC to perform test suite health checks, security scans, and dependabot PR management.
## Configuration
To configure the setup, follow these steps:
1. Create a new GitHub secret for the `ANTHROPIC_API_KEY` and `GH_PAT` variables.
2. Update the `agency-cycle.yml` and `continuous-improvement.yml` workflows to use the new secrets.
3. Configure the `weekly-trend-digest.yml` workflow to fetch trends from the desired sources.
## Troubleshooting
For troubleshooting, refer to the workflow logs and the GitHub issues created by the setup.