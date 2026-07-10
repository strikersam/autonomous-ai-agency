# Proof

Most "autonomous agent" projects show you a demo video. This directory holds **artifacts** — real output from the systems in this repository, committed as produced, with the exact commands to reproduce each one yourself.

| Artifact | What it proves |
|---|---|
| [`agent-built.md`](agent-built.md) | This repository is maintained by its own agents: **184 of the 642 merged pull requests** were opened by AI agent sessions (verifiable from the PR head branches). |
| [`audits/self-audit/`](audits/self-audit/) | The SEO/GEO/AIO audit engine, run for real against this project's own public docs page — including the findings against ourselves. |

## The self-audit (yes, we publish our own imperfect score)

The audit engine (`services/seo_audit.py`, [full docs](../docs/seo-audit.md)) runs 102 deterministic checks across six pillars and produces Screaming Frog-compatible exports plus an agent-ready delegation plan. We ran it against this project's own docs page and committed the output unedited:

- **Health score: 43.1/100** — 21 distinct findings, 11 of them auto-fixable by the repo-aware SEO fixer
- Report: [`report.md`](audits/self-audit/127_0_0_1_8899_report.md) · [PDF](audits/self-audit/127_0_0_1_8899_seo_audit.pdf) · [findings CSV](audits/self-audit/127_0_0_1_8899_findings.csv) · [raw JSON](audits/self-audit/127_0_0_1_8899_report.json)

If we hid this score, you'd be right not to trust the reports the agents produce about *your* site. The delegation plan at the bottom of the report is the interesting part: every finding is already packaged as a WSJF-prioritized work item assigned to a specialist agent — that's the handoff from "audit" to "agency."

### Honesty notes (read before quoting the numbers)

- This run was executed against a **locally served copy** of the docs page (`python -m http.server -d docs`) because the CI sandbox that generated it has no general internet egress. Findings marked *Security: HTTP URLs* and the missing HTTPS-related headers are partly artifacts of local serving — the production deployments sit behind Cloudflare/Render TLS.
- Single-page site → single-page crawl. Larger targets produce per-page CSVs with hundreds of rows in the same format.
- Revenue-at-risk figures (when a baseline is supplied) are **model estimates of exposure, not measured losses** — the model is documented in [`docs/seo-audit.md`](../docs/seo-audit.md).

## Reproduce any audit yourself

```bash
git clone https://github.com/strikersam/autonomous-ai-agency && cd autonomous-ai-agency
pip install -r requirements.txt

# Audit any public site (yours, ideally):
PYTHONPATH=. python scripts/run_seo_audit.py \
  --website-url https://yourcompany.com \
  --max-pages 50 \
  --output-dir ./my-audit

# Reproduce the self-audit exactly (loopback needs the dedicated helper — see note):
python -m http.server 8899 -d docs &
PYTHONPATH=. python scripts/self_audit_local.py http://127.0.0.1:8899/ ./self-audit
```

(The standalone `run_seo_audit.py` script correctly refuses loopback/private URLs — an SSRF fail-closed guard in `SeoAuditEngine.run`. Auditing a locally served copy of your own site is the one legitimate loopback case, so `scripts/self_audit_local.py` wraps the engine's documented fetcher-injection seam, `SeoAuditEngine(fetcher=...)` — the exact path used to generate the committed report.)

## What's coming next in this directory

- Audits of well-known public sites (constructive framing, no revenue claims about third parties), run from an unrestricted network.
- Case studies from pilot deployments — [request one](../README.md#need-assistance).
