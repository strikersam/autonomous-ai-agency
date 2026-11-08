"""One platform company: consolidation, repair, and the bugs that split it."""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from models.company_graph import Company, RepoConnection
from services import self_company as sc
from services.framework_families import system_type_for_framework

REPO_URL = "https://github.com/strikersam/autonomous-ai-agency"
WEBSITE = "https://local-llm-server.onrender.com"
ADMIN = "admin@example.com"


# ── framework detection ──────────────────────────────────────────────────────

@pytest.mark.parametrize("name,kind", [
    ("FastAPI", "backend"), ("Django", "backend"), ("Express", "backend"),
    ("React", "frontend"), ("Vue.js", "frontend"), ("Next.js", "frontend"),
    ("Nuxt.js", "frontend"), ("Vite", "frontend"), ("Spring Boot", "backend"),
    ("Tailwind CSS", None), ("OpenAI-compatible API", None), ("", None),
])
def test_scanner_framework_names_map_to_the_right_system_type(name, kind):
    assert system_type_for_framework(name) == kind


# ── identity ─────────────────────────────────────────────────────────────────

def _company(cid, *, name="Something", domain="example.com", owner=ADMIN, status="complete",
             repo=None, age_days=0):
    return Company(
        id=cid, name=name, domain=domain, owner_id=owner, onboarding_status=status,
        repo_connection=repo, created_at=datetime(2026, 1, 1) + timedelta(days=age_days),
    )


def _repo(owner="strikersam", name="autonomous-ai-agency", branch="master"):
    return RepoConnection(owner=owner, repo=name, default_branch=branch)


def test_platform_copies_match_by_domain_repo_or_name_but_strangers_do_not():
    domains = sc.self_domains(WEBSITE)
    assert sc.looks_like_self(_company("a", domain="local-llm-server.strikersam.workers.dev"), domains)
    assert sc.looks_like_self(_company("b", domain="local-llm-server.onrender.com"), domains)
    assert sc.looks_like_self(_company("c", repo=_repo()), domains)
    assert sc.looks_like_self(_company("d", name="Autonomous AI Agency (self)"), domains)
    assert not sc.looks_like_self(_company("e", name="Acme", domain="acme.com",
                                           repo=_repo("acme", "shop")), domains)


def test_canonical_prefers_repo_then_onboarded_then_specialists_then_oldest():
    connected = _company("conn", repo=_repo(), age_days=5)
    big = _company("big", age_days=1)
    old = _company("old", age_days=0)
    assert sc.pick_canonical([big, old, connected], {"big": 9, "old": 1}).id == "conn"
    assert sc.pick_canonical([big, old], {"big": 9, "old": 1}).id == "big"
    assert sc.pick_canonical([big, old], {"big": 2, "old": 2}).id == "old"
    pending = _company("pending", status="in_progress")
    assert sc.pick_canonical([pending, old], {"pending": 9}).id == "old"


# ── end-to-end consolidation ─────────────────────────────────────────────────

class _Store:
    def __init__(self, companies, specialists):
        self.companies = {c.id: c for c in companies}
        self.specialists = specialists  # company_id -> list[SimpleNamespace]

    async def list_companies(self, limit=500):
        return list(self.companies.values())

    async def get_company(self, cid):
        return self.companies.get(cid)

    async def update_company(self, company):
        self.companies[company.id] = company
        return company

    async def list_repos(self, cid):
        return list(getattr(self, "repos", {}).get(cid, []))

    async def list_detected_systems(self, company_id, system_type=None):
        return list(getattr(self, "systems", {}).get(company_id, []))

    async def delete_company(self, cid):
        return self.companies.pop(cid, None) is not None

    async def list_specialists(self, cid):
        return list(self.specialists.get(cid, []))


@pytest.fixture
def world(monkeypatch):
    """Three platform copies (as seen live), one user's look-alike, one unrelated company."""
    monkeypatch.setenv("SELF_COMPANY_CONSOLIDATE_ENABLED", "true")
    monkeypatch.setenv("ADMIN_EMAIL", ADMIN)
    backend = _company("6a3cea2b", name="local-llm-server", domain="local-llm-server.onrender.com",
                       age_days=0)
    agency5 = _company("6a9e9456", name="Autonomous AI Agency", domain="autonomous-ai-agency.onrender.com",
                       age_days=3)
    frontend = _company("6a3ce9f9", name="Autonomous AI Agency",
                        domain="local-llm-server.strikersam.workers.dev", age_days=1)
    lookalike = _company("user1", name="Autonomous AI Agency", domain="myagency.io", owner="bob@users.io")
    other = _company("acme", name="Acme", domain="acme.com", owner=ADMIN)
    spec = lambda fam, i: SimpleNamespace(id=f"{i}-{fam}", family=fam)  # noqa: E731
    store = _Store([backend, agency5, frontend, lookalike, other], {
        "6a3cea2b": [spec(f, "b") for f in ("frontend", "analytics", "data", "seo", "backend")],
        "6a9e9456": [spec(f, "a") for f in ("analytics", "data", "seo", "backend", "frontend")],
        "6a3ce9f9": [spec(f, "f") for f in ("frontend", "engineering")],
    })
    log = {"deleted": [], "provisioned": [], "deprovisioned": [], "activated": [], "attached": [],
           "scanned": [], "agents_removed": []}

    import services.company_graph_store as cgs
    monkeypatch.setattr(cgs, "get_company_graph_store", lambda: store)

    class _Graph:
        async def delete_company(self, cid):
            log["deleted"].append(cid)
            store.companies.pop(cid, None)
            return True

    import services.company_graph as cg
    monkeypatch.setattr(cg, "get_company_graph_service", lambda: _Graph())

    class _Specialists:
        async def provision_specialist(self, req):
            log["provisioned"].append(req.specialist_family)
            store.specialists.setdefault(req.company_id, []).append(
                SimpleNamespace(id=f"new-{req.specialist_family}", family=req.specialist_family))
            return SimpleNamespace(status="success")

        async def deprovision_specialist(self, sid):
            log["deprovisioned"].append(sid)
            for cid, specs in store.specialists.items():
                store.specialists[cid] = [s for s in specs if s.id != sid]
            return True

    import services.specialist as sp
    monkeypatch.setattr(sp, "get_specialist_service", lambda: _Specialists())

    class _Agency:
        async def activate_company(self, cid, **kw):
            log["activated"].append(cid)
            return {"status": "active"}

    import services.company_agency as ca
    monkeypatch.setattr(ca, "get_company_agency_service", lambda: _Agency())

    async def fake_attach(company_id, url, *, store, fallback_branch="main", **kw):
        log["attached"].append((company_id, fallback_branch))
        company = await store.get_company(company_id)
        await store.update_company(company.model_copy(update={"repo_connection": _repo(branch=fallback_branch)}))

    import services.repo_connection as rc
    monkeypatch.setattr(rc, "attach_repo_connection", fake_attach)

    class _Onboarding:
        async def _scan_repo(self, cid, url):  # a successful scan records the repo
            log["scanned"].append((cid, url))
            store.repos = {**getattr(store, "repos", {}), cid: [SimpleNamespace(url=url)]}
            store.systems = {**getattr(store, "systems", {}), cid: [SimpleNamespace(name="FastAPI")]}

    import services.onboarding as ob
    monkeypatch.setattr(ob, "get_onboarding_service", lambda: _Onboarding())

    async def remove_agent(sid):
        log["agents_removed"].append(sid)

    monkeypatch.setattr(sc, "_remove_agent", remove_agent)
    return store, log


async def test_consolidation_keeps_one_platform_company_and_staffs_it(world):
    store, log = world
    result = await sc.consolidate_self_companies(website_url=WEBSITE, repo_url=REPO_URL)

    assert result["status"] == "consolidated"
    keep = result["company_id"]
    # Tie on onboarding and specialists (5 each) → the oldest wins; the 2-specialist copy goes too.
    assert keep == "6a3cea2b"
    assert sorted(log["deleted"]) == ["6a3ce9f9", "6a9e9456"]
    # The user's look-alike and the unrelated company are untouched.
    assert {"user1", "acme"} <= set(store.companies)

    company = store.companies[keep]
    assert company.name == sc.COMPANY_NAME
    assert company.domain == "autonomous-ai-agency.strikersam.workers.dev"  # the public site, not the API host
    assert company.repo_connection.default_branch == "master"
    assert log["attached"] == [(keep, "master")] and log["scanned"] == [(keep, REPO_URL)]

    families = {s.family for s in store.specialists[keep]}
    assert families == {"backend", "frontend", "devops", "security", "qa", "data", "seo"}
    assert sorted(log["agents_removed"]) == ["b-analytics"]  # seo stays: the public site needs it
    assert log["activated"] == [keep]


async def test_consolidation_is_idempotent(world):
    store, log = world
    await sc.consolidate_self_companies(website_url=WEBSITE, repo_url=REPO_URL)
    for key in log:
        log[key].clear()
    again = await sc.consolidate_self_companies(website_url=WEBSITE, repo_url=REPO_URL)
    assert again["status"] == "consolidated" and again["removed"] == []
    assert again["activation"] == "unchanged"
    assert not log["deleted"] and not log["provisioned"] and not log["attached"]


async def test_consolidation_can_be_switched_off(world, monkeypatch):
    store, log = world
    monkeypatch.setenv("SELF_COMPANY_CONSOLIDATE_ENABLED", "false")
    assert await sc.consolidate_self_companies(website_url=WEBSITE, repo_url=REPO_URL) == {"status": "disabled"}
    assert not log["deleted"]


async def test_a_company_whose_owner_cannot_be_resolved_is_left_alone(world, monkeypatch):
    store, log = world

    async def lookup_fails(_owner):
        raise RuntimeError("db down")

    import services.agent_memory.service as ams
    monkeypatch.setattr(ams, "_user_identities", lookup_fails)
    store.companies["mystery"] = _company("mystery", name="local-llm-server", owner="some-user-id")
    await sc.consolidate_self_companies(website_url=WEBSITE, repo_url=REPO_URL)
    assert "mystery" in store.companies and "mystery" not in log["deleted"]


async def test_workers_dev_frontend_is_no_longer_archived_as_stale(monkeypatch):
    import services.self_bootstrap as sb

    frontend = _company("fe", name="Autonomous AI Agency", domain="local-llm-server.strikersam.workers.dev")

    async def listing():
        return [frontend]

    monkeypatch.setattr(sb, "_list_companies_safe", listing)
    assert await sb._find_stale_self_companies() == []


# ── repo branch fallback ─────────────────────────────────────────────────────

async def test_branch_fallback_is_used_when_github_cannot_be_asked():
    from services.repo_connection import detect_delivery_policy

    class _Down:
        async def get_repo(self, owner, repo):
            raise RuntimeError("rate limited")

    policy = await detect_delivery_policy("strikersam", "autonomous-ai-agency", probe=_Down(),
                                          fallback_branch="master")
    assert policy.default_branch == "master" and policy.mode == "pr_required"
    default = await detect_delivery_policy("o", "r", probe=_Down())
    assert default.default_branch == "main"  # unchanged for callers that don't know


# ── schedules no longer shared between same-named companies ──────────────────

async def test_same_named_companies_get_their_own_schedules(monkeypatch, tmp_path):
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AGENCY_SQLITE_DB_PATH", str(tmp_path / "agency.db"))
    from packages.scheduler.scheduler import AgentScheduler
    from services.company_agency import CompanyAgencyService
    import services.company_graph_store as cgs

    companies = {cid: _company(cid, name="Twin Co", domain=f"{cid.replace('_', '-')}.test") for cid in ("co_one", "co_two")}

    class _Stub:
        async def get_company(self, cid):
            return companies[cid]

        async def list_specialists(self, cid):
            return []

    monkeypatch.setattr(cgs, "get_company_graph_store", lambda: _Stub())
    svc = CompanyAgencyService()
    svc._scheduler = sched = AgentScheduler()
    for cid in companies:
        await svc.activate_company(cid, start_runtimes=False, create_schedules=True)

    tags = [set(j.tags or []) for j in sched.list()]
    for cid in companies:
        owned = [t for t in tags if f"company:{cid}" in t]
        assert len(owned) == 6, (cid, len(owned))
    names = [j.name for j in sched.list()]
    assert len(names) == len(set(names)) == 12


def test_canonical_tie_breaks_on_id_so_every_process_agrees():
    a, b = _company("aaa", age_days=0), _company("bbb", age_days=0)
    assert sc.pick_canonical([a, b], {}).id == sc.pick_canonical([b, a], {}).id == "bbb"


async def test_survivor_is_reactivated_when_only_duplicates_were_removed(world):
    store, log = world
    # Survivor already connected and correctly staffed: only the duplicate removal changes things.
    keep = store.companies["6a3cea2b"]
    store.companies["6a3cea2b"] = keep.model_copy(update={"repo_connection": _repo()})
    store.specialists["6a3cea2b"] = [SimpleNamespace(id=f"k-{f}", family=f) for f in sc.TECH_FAMILIES]
    result = await sc.consolidate_self_companies(website_url=WEBSITE, repo_url=REPO_URL)
    assert result["removed"] and result["specialists"] == {"added": [], "removed": []}
    assert log["activated"] == ["6a3cea2b"]


async def test_reattaching_the_repo_keeps_token_ref_and_first_merge_consent(world, monkeypatch):
    from models.company_graph import DeliveryPolicy

    store, log = world
    seen = {}

    async def attach(company_id, url, *, store, token_ref=None, fallback_branch="main", **kw):
        seen["token_ref"] = token_ref
        company = await store.get_company(company_id)
        await store.update_company(company.model_copy(update={"repo_connection": RepoConnection(
            owner="strikersam", repo="autonomous-ai-agency", default_branch=fallback_branch,
            token_ref=token_ref, policy=DeliveryPolicy(default_branch=fallback_branch))}))

    import services.repo_connection as rc
    monkeypatch.setattr(rc, "attach_repo_connection", attach)
    stored_ref = "ref-to-stored-gh-pat"  # an opaque secrets-store reference, not a credential
    guessed = RepoConnection(owner="strikersam", repo="autonomous-ai-agency", default_branch="main",
                             token_ref=stored_ref, policy=DeliveryPolicy(
                                 default_branch="main", first_merge_consent=True,
                                 detection_note="uncertain (repo metadata unavailable) → pr_required"))
    store.companies["6a3cea2b"] = store.companies["6a3cea2b"].model_copy(update={"repo_connection": guessed})
    await sc.consolidate_self_companies(website_url=WEBSITE, repo_url=REPO_URL)
    conn = store.companies["6a3cea2b"].repo_connection
    assert seen["token_ref"] == stored_ref
    assert conn.default_branch == "master" and conn.policy.first_merge_consent is True


# ── production stall 2026-11-08: one hung teardown blocked the repair ────────

async def test_a_hung_teardown_does_not_block_consolidation(world, monkeypatch):
    """Production: delete_company of the second duplicate never returned, so
    the repair never ran and two companies stayed. The row is deleted on
    timeout (the orphan reaper finishes the teardown) and the repair runs."""
    import asyncio

    store, log = world

    class _HungGraph:
        async def delete_company(self, cid):
            await asyncio.sleep(3600)

    import services.company_graph as cg
    monkeypatch.setattr(cg, "get_company_graph_service", lambda: _HungGraph())
    monkeypatch.setattr(sc, "_DELETE_TIMEOUT_S", 0.05)

    result = await sc.consolidate_self_companies(website_url=WEBSITE, repo_url=REPO_URL)

    assert result["status"] == "consolidated"
    assert sorted(result["removed"]) == ["6a3ce9f9", "6a9e9456"]
    assert "6a9e9456" not in store.companies and "6a3ce9f9" not in store.companies
    assert log["activated"] == ["6a3cea2b"]


async def test_concurrent_consolidations_do_not_race(world, monkeypatch):
    """Startup, the agency cycle and the background loop each call the
    bootstrap; a second run while one is in flight is skipped."""
    import asyncio

    store, log = world

    class _SlowGraph:  # real teardown awaits I/O; the fakes otherwise never yield
        async def delete_company(self, cid):
            await asyncio.sleep(0.05)
            log["deleted"].append(cid)
            store.companies.pop(cid, None)
            return True

    import services.company_graph as cg
    monkeypatch.setattr(cg, "get_company_graph_service", lambda: _SlowGraph())
    first, second = await asyncio.gather(
        sc.consolidate_self_companies(website_url=WEBSITE, repo_url=REPO_URL),
        sc.consolidate_self_companies(website_url=WEBSITE, repo_url=REPO_URL),
    )
    assert {first["status"], second["status"]} == {"consolidated", "in_progress"}
    assert sorted(log["deleted"]) == ["6a3ce9f9", "6a9e9456"]


async def test_duplicate_specialists_of_one_family_are_retired(world):
    """Production 2026-11-08: two racing runs each added security and qa."""
    store, log = world
    store.specialists["6a3cea2b"] = [SimpleNamespace(id=f"k-{f}", family=f) for f in sc.TECH_FAMILIES] + [
        SimpleNamespace(id="dup-security", family="security"), SimpleNamespace(id="dup-qa", family="qa")]
    result = await sc.reconcile_specialists(store, "6a3cea2b")
    assert sorted(result["removed"]) == ["qa", "security"]
    assert sorted(log["deprovisioned"]) == ["dup-qa", "dup-security"]
    assert sorted(s.family for s in store.specialists["6a3cea2b"]) == sorted(sc.TECH_FAMILIES)


async def test_dedupe_keeps_the_healthy_specialist(world):
    store, log = world
    broken = SimpleNamespace(id="broken-qa", family="qa", is_provisioned=False, status="disabled")
    good = SimpleNamespace(id="good-qa", family="qa", is_provisioned=True, status="active")
    store.specialists["6a3cea2b"] = [SimpleNamespace(id=f"k-{f}", family=f) for f in sc.TECH_FAMILIES
                                     if f != "qa"] + [broken, good]
    await sc.reconcile_specialists(store, "6a3cea2b")
    assert log["deprovisioned"] == ["broken-qa"]


async def test_repair_rescans_when_the_graph_has_no_repo(world):
    """Production 2026-11-08: the repo was connected, but every scan had run
    unauthenticated and failed, so the Company page showed 0 repos/systems.
    An already-connected company with no scanned repo is rescanned."""
    store, log = world
    await sc.consolidate_self_companies(website_url=WEBSITE, repo_url=REPO_URL)
    store.repos = {}  # connected, but no scan ever succeeded
    log["scanned"].clear()
    log["activated"].clear()

    result = await sc.consolidate_self_companies(website_url=WEBSITE, repo_url=REPO_URL)
    assert log["scanned"] == [("6a3cea2b", REPO_URL)]
    assert result["repo_rescanned"] is True and log["activated"] == ["6a3cea2b"]

    log["scanned"].clear()
    await sc.consolidate_self_companies(website_url=WEBSITE, repo_url=REPO_URL)
    assert log["scanned"] == []  # scanned repo on record: nothing to do


def test_repo_scanner_uses_the_platform_github_token(monkeypatch):
    """Onboarding built RepoScanner(company_id) with no token: GitHub's
    unauthenticated limit (60/h per IP) answered 403 to every scan."""
    from packages.config.settings import settings
    from services.scanner import RepoScanner

    import uuid

    configured, explicit = uuid.uuid4().hex, uuid.uuid4().hex  # opaque, not secrets
    monkeypatch.setattr(settings, "gh_pat", configured)
    assert RepoScanner("c1").github_token == configured
    assert RepoScanner("c1", github_token=explicit).github_token == explicit
    monkeypatch.setattr(settings, "gh_pat", "")
    assert RepoScanner("c1").github_token is None


async def test_duplicates_priorities_survive_consolidation(world):
    """Production 2026-11-08: the operator's priorities were on a duplicate the
    consolidation deleted. They are moved onto the kept company first."""
    store, log = world
    dup = store.companies["6a3ce9f9"]
    store.companies["6a3ce9f9"] = dup.model_copy(update={"priorities": ["Rank in AI answers", "Ship weekly"]})
    keep = store.companies["6a3cea2b"]
    store.companies["6a3cea2b"] = keep.model_copy(update={"priorities": ["Ship weekly"]})

    await sc.consolidate_self_companies(website_url=WEBSITE, repo_url=REPO_URL)

    assert "6a3ce9f9" not in store.companies
    assert store.companies["6a3cea2b"].priorities == ["Ship weekly", "Rank in AI answers"]


async def test_repair_rescans_while_no_systems_are_recorded(world):
    """A scanned repo with no detected systems (the old topic-only detection)
    is rescanned, so the new file-based detection fills the systems list."""
    store, log = world
    await sc.consolidate_self_companies(website_url=WEBSITE, repo_url=REPO_URL)
    store.systems = {}
    log["scanned"].clear()

    await sc.consolidate_self_companies(website_url=WEBSITE, repo_url=REPO_URL)
    assert log["scanned"] == [("6a3cea2b", REPO_URL)]
