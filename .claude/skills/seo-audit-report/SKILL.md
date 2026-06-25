---
name: seo-audit-report
description: >
  Full-site SEO / GEO / AEO / AIO audit for any website. Crawls up to N pages
  using Chrome TLS impersonation (bypasses Akamai/Cloudflare), runs a
  Screaming Frog-class check catalog across Technical, Content, Security,
  Social, GEO, and AIO pillars, and produces an executive-level PDF report plus
  CSV/JSON/Markdown data files. Suitable for client deliverables and CTO reviews.
triggers:
  - "run seo audit"
  - "audit website"
  - "seo report for"
  - "seo/geo/aio audit"
  - "crawl and audit"
  - "site health report"
  - "full seo report"
parameters:
  website_url:
    description: "Full URL of the site to audit (e.g. https://www.example.com)"
    required: true
  max_pages:
    description: "Maximum pages to crawl (default: 100)"
    required: false
    default: 100
  max_depth:
    description: "Maximum crawl depth (default: 3)"
    required: false
    default: 3
  output_dir:
    description: "Directory to write output files (default: ./seo-audit-output)"
    required: false
    default: "./seo-audit-output"
  monthly_organic_revenue:
    description: "Monthly organic revenue baseline for revenue-at-risk modelling (default: 0 — leave at 0 if unknown)"
    required: false
    default: 0
references:
  - scripts/run_seo_audit.py
  - services/seo_audit.py
  - services/seo_fetch.py
  - models/seo_audit.py
  - docs/seo-audit.md
---

# Skill: seo-audit-report

## Purpose

Run a full SEO / GEO / AEO / AIO audit against any public website and produce
an executive-level PDF report suitable for CTO or client delivery.

The crawl uses **curl_cffi with Chrome 120 TLS impersonation** to bypass
bot-protection layers (Akamai, Cloudflare) that block plain httpx crawlers.
Playwright browser mode is supported when system dependencies are available;
curl_cffi is the reliable fallback.

## Quick Start

```bash
python scripts/run_seo_audit.py \
  --website-url https://www.example.com \
  --output-dir ./seo-output
```

All other parameters have sensible defaults. See `--help` for full options.

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--website-url` | required | Site to audit |
| `--max-pages` | 100 | Crawl budget (pages) |
| `--max-depth` | 3 | Link-follow depth |
| `--output-dir` | `./seo-audit-output` | Where to write files |
| `--monthly-organic-revenue` | 0 | Revenue baseline for at-risk modelling |
| `--check-image-sizes` | true | HEAD-request image sizes (slower) |
| `--no-check-image-sizes` | — | Skip image size checks for speed |

## Output Files

| File | Contents |
|------|----------|
| `{domain}_seo_audit.pdf` | Executive PDF report (cover, executive summary, pillar deep-dives, full findings, delegation plan, methodology) |
| `{domain}_report.json` | Full machine-readable report (all pages, all issues, pillar scores) |
| `{domain}_report.md` | Markdown version of the report |
| `{domain}_findings.csv` | Summary CSV: one row per finding type with priority, URLs affected, how-to-fix |
| `{domain}_pages.csv` | Per-page CSV: URL, status, title, H1, word count, issues found |
| `{domain}_issues.csv` | Per-issue-instance CSV: URL × check_code × details |

## Verify Bypass Quality

Before trusting results, spot-check the JSON:

```python
import json
with open("seo-output/example.com_report.json") as f:
    r = json.load(f)
pages = r["pages"]
# All should show status_code=200 and via="curl_cffi"
print({p["url"]: (p["status_code"], p.get("fetch_via","?")) for p in pages[:5]})
```

Repeated 403s with small HTML bodies indicate the site is still blocking; report
that plainly rather than fabricating findings.

## How This Skill Works (Agent Instructions)

1. **Install dependencies** (first run only):
   ```bash
   cd autonomous-ai-agency
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   # playwright install chromium  # optional — curl_cffi is used as fallback
   ```

2. **Run the audit**:
   ```bash
   source .venv/bin/activate
   python scripts/run_seo_audit.py \
     --website-url "{{ website_url }}" \
     --max-pages {{ max_pages | default(100) }} \
     --max-depth {{ max_depth | default(3) }} \
     --output-dir "{{ output_dir | default('./seo-audit-output') }}" \
     --monthly-organic-revenue {{ monthly_organic_revenue | default(0) }}
   ```
   Expect 3–20 minutes depending on site size and network. For large sites
   (500 pages) expect up to 90 minutes with browser mode.

3. **Verify bypass success**: check the JSON as shown above.

4. **Present the PDF** to the user and provide a 3–5 sentence summary:
   - Overall health score and worst pillar
   - Top 3 issues by strategic pressure
   - Pages crawled vs pages genuinely bypassed vs still blocked

## Revenue-at-Risk Disclaimer (load-bearing — always include in reports)

> Revenue-at-risk figures use a saturating exponential model
> `share = 0.35 × (1 − e^(−pressure/50))` applied to aggregate issue severity.
> They are **model estimates of proportional organic revenue exposure**, not
> measured losses. Leave `monthly_organic_revenue=0` when the baseline is
> unknown; all figures will display as £0/month.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| All pages return 403 | Bot wall not bypassed | curl_cffi should handle most; try increasing `timeout_seconds` |
| `libXdamage.so.1` error | Missing Playwright system libs | curl_cffi fallback activates automatically |
| Audit times out | Site too large / slow | Reduce `--max-pages` or `--max-depth` |
| Report has 0 pages | Crawl seeding failed | Check URL is correct and publicly reachable |
