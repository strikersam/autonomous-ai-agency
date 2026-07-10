"""Reproduce the committed self-audit against a locally served site copy.

The standalone auditor (``scripts/run_seo_audit.py``) correctly refuses
loopback/private hosts (SSRF fail-closed in ``SeoAuditEngine.run``). Auditing a
*locally served copy* of your own site is the one legitimate loopback case, so
this helper uses the engine's documented fetcher-injection seam
(``SeoAuditEngine(fetcher=...)``) — the same path used to generate
``proof/audits/self-audit/``.

Usage:
    python -m http.server 8899 -d docs &
    PYTHONPATH=. python scripts/self_audit_local.py http://127.0.0.1:8899/ ./self-audit
"""
from __future__ import annotations

import argparse
import asyncio
import re
from pathlib import Path
from urllib.parse import urlparse


async def run_local_audit(url: str, out_dir: Path, max_pages: int) -> int:
    """Run the audit engine against ``url`` with an injected HTTP fetcher."""
    from models.seo_audit import SeoAuditRequest
    from services.seo_audit import (
        SeoAuditEngine,
        USER_AGENT,
        report_to_csv,
        report_to_issues_csv,
        report_to_markdown,
        report_to_pages_csv,
    )
    from services.seo_fetch import make_fetcher

    request = SeoAuditRequest(
        website_url=url,
        max_pages=max_pages,
        max_depth=3,
        fetch_mode="http",
        timeout_seconds=30,
        include_sitemap=True,
        respect_robots=True,
        check_image_sizes=False,
    )
    fetcher = make_fetcher(
        fetch_mode="http", timeout=30.0, user_agent=USER_AGENT, concurrency=5
    )
    report = await SeoAuditEngine(fetcher=fetcher).run(request)

    out_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^\w\-]", "_", urlparse(url).netloc or "site")
    (out_dir / f"{slug}_report.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    (out_dir / f"{slug}_report.md").write_text(report_to_markdown(report), encoding="utf-8")
    (out_dir / f"{slug}_findings.csv").write_text(report_to_csv(report), encoding="utf-8")
    (out_dir / f"{slug}_pages.csv").write_text(report_to_pages_csv(report), encoding="utf-8")
    (out_dir / f"{slug}_issues.csv").write_text(report_to_issues_csv(report), encoding="utf-8")

    print(f"status={report.status} pages={report.pages_crawled}")
    print(f"health={report.health_score} pillars={report.pillar_scores}")
    print(f"output: {out_dir.resolve()}")
    return 0 if report.status == "success" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url", help="Locally served URL, e.g. http://127.0.0.1:8899/")
    parser.add_argument("output_dir", type=Path, help="Directory for report files")
    parser.add_argument("--max-pages", type=int, default=20)
    args = parser.parse_args()
    return asyncio.run(run_local_audit(args.url, args.output_dir, args.max_pages))


if __name__ == "__main__":
    raise SystemExit(main())
