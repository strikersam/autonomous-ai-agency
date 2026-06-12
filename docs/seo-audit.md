# SEO / GEO / AIO Audit Engine

> World-class, Screaming Frog-compatible site auditor with repo-aware auto-fixing.
> Implements issue [#533](https://github.com/strikersam/autonomous-ai-agency/issues/533).

## What It Does

The audit engine crawls a website (robots.txt-aware, sitemap-seeded, SSRF-safe),
runs **95+ deterministic checks** against every page plus site-level signals, and
produces a prioritized, fully exportable report — the same `Issue Name / Issue
Type / Issue Priority / URLs / % of Total / Description / How To Fix / Help URL`
taxonomy Screaming Frog SEO Spider exports, so existing SEO workflows work as-is.

Beyond Screaming Frog parity, checks are organized into six **pillars**:

| Pillar | Coverage |
|--------|----------|
| `technical` | Titles, meta descriptions, headings, canonicals, directives, hreflang, URL structure, response codes, validation, pagination, performance |
| `content` | Word count, Flesch readability, placeholder copy |
| `security` | HTTPS, mixed content, HSTS/CSP/XCTO/XFO/Referrer-Policy headers, unsafe cross-origin links, protocol-relative resources, insecure forms |
| `social` | Open Graph and Twitter card readiness |
| `geo` | **Generative Engine Optimization** — llms.txt, robots.txt access for AI crawlers (GPTBot, ClaudeBot, PerplexityBot, Google-Extended, …), sitemaps, RSS feeds, semantic HTML landmarks, citable heading anchors |
| `aio` | **AI Overviews + Answer Engine Optimization (AEO)** — JSON-LD structured data validity, Organization/Breadcrumb/FAQ/QAPage schema, article dates and author markup (E-E-A-T), chunkable self-contained passages that answer engines can quote |

Together `geo` + `aio` cover the full beyond-classic-SEO spectrum (SEO / AEO /
GEO / AIO): classic ranking, being *the answer* in answer engines, and being
*read and cited* by generative engines.

Each audit yields a weighted **0–100 health score** overall and per pillar.

## Revenue-at-Risk Portfolio Quantification

Pass `monthly_organic_revenue` in the audit request and every finding is
quantified as **estimated monthly revenue at risk**: each finding's severity
deduction (priority × type × share of pages affected) doubles as the share of
organic revenue considered at risk, with the aggregate capped at 35% of the
baseline. The report carries `estimated_monthly_revenue_loss` overall and per
finding row.

Delegation packages are additionally **WSJF-scored** (SAFe Weighted Shortest
Job First — the same model as `agents/portfolio.py`): business value comes from
recoverable revenue, time criticality from priority, risk reduction from
pillar, and job size from effort. Packages slot directly into the portfolio
manager as `Initiative`s, so SEO remediation competes for capacity against the
rest of the portfolio on equal terms.

```bash
curl -X POST "$HOST/api/company/$COMPANY/seo/audit" \
  -H "Content-Type: application/json" \
  -d '{"website_url": "https://example.com", "max_pages": 100,
       "monthly_organic_revenue": 250000}'
```

## Architecture

```
models/seo_audit.py      Typed Pydantic contracts (request, report, fix plan)
services/seo_checks.py   The check catalog (95+ checks with remediation guidance)
services/seo_audit.py    Async crawler + check engine + scoring + exports
services/seo_fixer.py    Repo-aware auto-fixer (dry-run diffs / apply mode)
backend/seo_api.py       REST API (mounted in backend/server.py)
```

The `seo` specialist family is bound to the `seo-audit` runtime skill
(`services/skill_bindings.py`), so specialists can run audits through the
workflow engine; results are persisted into the Company Graph as
KnowledgeItems.

## API

```http
GET  /api/seo/checks                                          # full catalog (public)
POST /api/company/{company_id}/seo/audit                      # run an audit
GET  /api/company/{company_id}/seo/audits                     # list past audits
GET  /api/company/{company_id}/seo/audits/{audit_id}          # full report
GET  /api/company/{company_id}/seo/audits/{audit_id}/export   # ?fmt=csv|urls|issues|markdown|json
POST /api/company/{company_id}/seo/audits/{audit_id}/delegate # create agent tasks
POST /api/company/{company_id}/seo/fix                        # repo-aware auto-fix
```

### Running an audit

```bash
curl -X POST "$HOST/api/company/$COMPANY/seo/audit" \
  -H "Content-Type: application/json" \
  -d '{"website_url": "https://example.com", "max_pages": 100}'
```

Request options: `max_pages` (1–500, default 50), `max_depth`, `include_sitemap`,
`respect_robots`, `check_image_sizes`, `timeout_seconds`.

### Exports — the full heavy report

- `fmt=csv` — aggregated findings, drop-in compatible with Screaming Frog's
  issues overview CSV
- `fmt=urls` — **per-URL inventory** (one row per crawled page: status, title +
  length, meta description + length, H1s, word count, readability, canonical,
  links, images, structured data, issue list)
- `fmt=issues` — **every individual occurrence** (one row per check × URL)
- `fmt=markdown` — executive report: pillar scores, findings table,
  **delegation plan**, and per-page details (worst pages first)
- `fmt=json` — the complete typed report object

### Delegation plan → agent tasks

Every report contains a `delegation_plan`: findings grouped into work packages
(one per category) with priority, S/M/L effort, suggested specialist family
(`security`, `frontend`, `content`, `seo`, `marketing`, `engineering`,
`platform`) and concrete instructions.

`POST …/delegate` turns those packages into real tasks on the task board
(`source=seo_audit`), ready for the orchestrator or a human to assign:

```bash
curl -X POST "$HOST/api/company/$COMPANY/seo/audits/$AUDIT/delegate" \
  -H "Content-Type: application/json" \
  -d '{"min_priority": "medium"}'
```

### Repo-aware auto-fixing

When a code repo is available (checked out under the workspace root,
`SEO_FIX_WORKSPACE_ROOT`, default `./workspace`), the fixer remediates the
auto-fixable findings directly:

| Fix | Check |
|-----|-------|
| `<meta charset>`, viewport, `lang` attribute | validation_* |
| Meta description derived from page copy | meta_desc_missing |
| Canonical link (needs `base_url`) | canonical_missing |
| Open Graph + Twitter card tags | social_* |
| `rel="noopener"` on `target="_blank"` | security_unsafe_cross_origin_links |
| Protocol-relative URLs → https | security_protocol_relative_resources |
| Image `alt` (humanized from filename) | image_missing_alt_attribute |
| Image `width`/`height` (measured with Pillow) | image_missing_size_attributes |
| `loading="lazy"` on below-the-fold images | image_not_lazy_loaded |
| robots.txt / sitemap.xml / llms.txt generation | geo_* |
| Security-header config (netlify.toml / vercel.json / `_headers`) | security_missing_* (suggested) |

Default is a **dry run** returning unified diffs; pass `"apply": true` to write.
Edits are targeted text edits (not DOM re-serialization) so diffs stay minimal.

```bash
curl -X POST "$HOST/api/company/$COMPANY/seo/fix" \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "workspace/my-site", "base_url": "https://example.com", "apply": false}'
```

## Safety

- The crawler refuses private/loopback/link-local hosts (SSRF guard shared
  with `services/scanner.py`) and honors robots.txt by default.
- Extra-request budgets are bounded (image HEADs, sitemap fetches).
- The fixer only operates inside the workspace root; the API rejects paths
  outside it.

## Provenance

Built for issue #533 informed by Screaming Frog SEO Spider's issue taxonomy
and these references: [screaming-frog-mcp](https://github.com/bzsasson/screaming-frog-mcp),
[open-seo-crawler](https://github.com/puneetindersingh/open-seo-crawler)
(per-URL exports, slow-response checks, severity views),
[crawlforge](https://github.com/mario-hernandez/crawlforge) (rules-as-code,
per-URL data model), and the
[lazy-loading extraction gist](https://gist.github.com/jonathanmooredigital/667955e13965c1daa487796f76e11072)
(lazy-loading gap analysis).

## Tests

```bash
pytest tests/test_seo_audit.py tests/test_seo_fixer.py tests/test_seo_api.py
```
