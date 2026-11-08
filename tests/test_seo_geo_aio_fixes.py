"""SEO fixer: site files land in the served web root; AIO JSON-LD is added."""
from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

from models.seo_audit import SeoFixRequest
from services.company_agency import COMPANY_SCHEDULES, schedule_instruction
from services.seo_fixer import run_fixes

BASE = "https://example.workers.dev"
PAGE = "<html><head><title>{t}</title></head><body><p>{t} body copy that is long enough.</p></body></html>"


def _vite_repo(tmp_path: Path) -> Path:
    public = tmp_path / "frontend" / "public"
    public.mkdir(parents=True)
    (public / "robots.txt").write_text("User-agent: *\nAllow: /\n")
    (public / "home.html").write_text(PAGE.format(t="Home"))
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "notes.html").write_text(PAGE.format(t="Notes"))
    return tmp_path


def test_site_files_go_to_the_served_web_root(tmp_path):
    """A Vite app serves frontend/public; a repo-root llms.txt is never served."""
    repo = _vite_repo(tmp_path)
    run_fixes(SeoFixRequest(repo_path=str(repo), base_url=BASE, apply=True,
                            include_checks=["geo_missing_llms_txt", "geo_missing_sitemap"]))
    public = repo / "frontend" / "public"
    assert (public / "llms.txt").is_file() and not (repo / "llms.txt").exists()
    sitemap = (public / "sitemap.xml").read_text()
    assert f"<loc>{BASE}/home.html</loc>" in sitemap
    assert "frontend/public" not in sitemap and "docs/notes" not in sitemap


def test_repo_root_stays_the_web_root_for_plain_sites(tmp_path):
    (tmp_path / "index.html").write_text(PAGE.format(t="Home"))
    run_fixes(SeoFixRequest(repo_path=str(tmp_path), base_url=BASE, apply=True,
                            include_checks=["geo_missing_llms_txt"]))
    assert (tmp_path / "llms.txt").is_file()


def _json_ld(html: str) -> dict:
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert m, "no JSON-LD block"
    return json.loads(m.group(1).replace("<\\/", "</"))


def test_homepage_gets_organization_and_website_schema(tmp_path):
    (tmp_path / "index.html").write_text(PAGE.format(t="Acme"))
    (tmp_path / "about.html").write_text(PAGE.format(t="About"))
    run_fixes(SeoFixRequest(repo_path=str(tmp_path), base_url=BASE, apply=True, site_name="Acme",
                            include_checks=["aio_no_structured_data", "aio_missing_organization_schema"]))
    home = {n["@type"] for n in _json_ld((tmp_path / "index.html").read_text())["@graph"]}
    about = {n["@type"] for n in _json_ld((tmp_path / "about.html").read_text())["@graph"]}
    assert home == {"WebPage", "Organization", "WebSite"}
    assert about == {"WebPage"}


def test_existing_structured_data_is_left_alone(tmp_path):
    html = ('<html><head><title>X</title><script type="application/ld+json">'
            '{"@type": "Organization"}</script></head><body></body></html>')
    (tmp_path / "index.html").write_text(html)
    run_fixes(SeoFixRequest(repo_path=str(tmp_path), base_url=BASE, apply=True,
                            include_checks=["aio_no_structured_data", "aio_missing_organization_schema"]))
    assert (tmp_path / "index.html").read_text() == html


def test_json_ld_cannot_close_its_script_tag(tmp_path):
    (tmp_path / "index.html").write_text(PAGE.format(t="a</script><b>"))
    run_fixes(SeoFixRequest(repo_path=str(tmp_path), base_url=BASE, apply=True,
                            include_checks=["aio_no_structured_data"]))
    html = (tmp_path / "index.html").read_text()
    block = html.split('application/ld+json">', 1)[1].split("</script>", 1)[0]
    assert "</" not in block


# ── schedules: priorities reach every run; SEO schedule needs an SEO specialist ──

def test_schedule_instruction_carries_ranked_priorities():
    company = SimpleNamespace(id="c1", name="Acme", domain="acme.com",
                              priorities=["Rank for AI answers", "Cut churn"])
    text = schedule_instruction(company, {"instruction": "Do the thing."})
    assert "1. Rank for AI answers" in text and "2. Cut churn" in text
    assert text.index("1. Rank") < text.index("2. Cut") < text.index("Task: Do the thing.")


def test_schedule_instruction_without_priorities_is_unchanged():
    company = SimpleNamespace(id="c1", name="Acme", domain="acme.com", priorities=[])
    assert schedule_instruction(company, {"instruction": "X"}) == (
        "Company: Acme (ID: c1)\nDomain: acme.com\nTask: X")


def test_seo_schedule_covers_all_four_pillars_and_needs_an_seo_specialist():
    seo = next(s for s in COMPANY_SCHEDULES if s["name_suffix"] == "seo-geo-aeo-aio-audit")
    assert seo["requires_family"] == "seo" and seo["specialist_family"] == "seo"
    for pillar in ("SEO", "GEO", "AEO", "AIO", "llms.txt", "JSON-LD"):
        assert pillar in seo["instruction"]


async def test_activation_adds_seo_schedule_and_refreshes_priorities(tmp_path, monkeypatch):
    """An SEO-staffed company gets the audit schedule; changed priorities
    replace the running jobs instead of leaving the old instruction."""
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AGENCY_SQLITE_DB_PATH", str(tmp_path / "agency.db"))
    from models.company_graph import Company
    from packages.scheduler.scheduler import AgentScheduler
    from services.company_agency import CompanyAgencyService

    sched = AgentScheduler()
    svc = CompanyAgencyService()
    svc._scheduler = sched
    state = {"company": Company(id="co_seo", name="SEO Co", domain="seo.test", owner_id="t",
                                onboarding_status="complete", priorities=["Win AI answers"])}
    seo = SimpleNamespace(id="sp1", family="seo", is_provisioned=True, status="active",
                          name="SEO", model_copy=lambda update: seo)

    class _Store:
        async def get_company(self, cid):
            return state["company"]

        async def list_specialists(self, cid):
            return [seo]

        async def update_specialist(self, s):
            return s

    import services.company_graph_store as cgs
    monkeypatch.setattr(cgs, "get_company_graph_store", lambda: _Store())
    try:
        await svc.activate_company("co_seo", start_runtimes=False, create_schedules=True)
        jobs = [j for j in sched.list() if "company:co_seo" in (j.tags or [])]
        assert any("seo-geo-aeo-aio-audit" in j.tags for j in jobs)
        assert all("1. Win AI answers" in j.instruction for j in jobs)

        state["company"] = state["company"].model_copy(update={"priorities": ["Cut churn"]})
        await svc.activate_company("co_seo", start_runtimes=False, create_schedules=True)
        after = [j for j in sched.list() if "company:co_seo" in (j.tags or [])]
        assert len(after) == len(jobs)
        assert all("1. Cut churn" in j.instruction and "Win AI" not in j.instruction for j in after)
    finally:
        sched.shutdown()
