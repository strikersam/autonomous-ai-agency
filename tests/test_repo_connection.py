"""Tests for RepoConnection + DeliveryPolicy (Autonomy Charter G5).

Covers URL parsing (GitHub-only / coming-soon), policy detection with a mocked
GitHub probe (protected / unprotected / uncertain), the first-unattended-merge
gate, URL-only pause, consent recording, and best-effort onboarding attach.
No live network — the GitHub probe is mocked.
"""
from __future__ import annotations

import pytest

from models.company_graph import Company, DeliveryPolicy, RepoConnection
from services.repo_connection import (
    UnsupportedProviderError,
    attach_repo_connection,
    build_repo_connection,
    decide_merge,
    detect_delivery_policy,
    parse_repo_url,
    provider_of,
    record_first_merge_consent,
)


# ── URL parsing / provider ───────────────────────────────────────────────────


def test_parse_github_url_variants():
    assert parse_repo_url("https://github.com/octo/Hello-World") == ("octo", "Hello-World")
    assert parse_repo_url("https://github.com/octo/hello.git") == ("octo", "hello")
    assert parse_repo_url("git@github.com:octo/hello.git") == ("octo", "hello")


def test_parse_non_github_is_coming_soon():
    assert provider_of("https://gitlab.com/o/r") == "gitlab"
    with pytest.raises(UnsupportedProviderError) as ei:
        parse_repo_url("https://gitlab.com/o/r")
    assert ei.value.provider == "gitlab"
    with pytest.raises(UnsupportedProviderError):
        parse_repo_url("https://bitbucket.org/o/r")


def test_parse_unknown_url_returns_none():
    assert parse_repo_url("https://example.com/not/a/repo") is None
    assert parse_repo_url("") is None


# ── policy detection (mocked probe) ──────────────────────────────────────────


class _Probe:
    def __init__(self, *, default_branch="main", protection=None, raise_repo=False,
                 raise_protection=False):
        self._default_branch = default_branch
        self._protection = protection
        self._raise_repo = raise_repo
        self._raise_protection = raise_protection

    async def get_repo(self, owner, repo):
        if self._raise_repo:
            raise RuntimeError("boom")
        return {"default_branch": self._default_branch}

    async def get_branch_protection(self, owner, repo, branch):
        if self._raise_protection:
            raise RuntimeError("boom")
        return self._protection


async def test_detect_protected_branch_is_pr_required():
    probe = _Probe(protection={
        "required_pull_request_reviews": {"required_approving_review_count": 2},
        "required_status_checks": {"strict": True},
    })
    policy = await detect_delivery_policy("o", "r", probe=probe)
    assert policy.mode == "pr_required"
    assert policy.protected is True
    assert policy.required_reviews == 2
    assert policy.required_status_checks is True


async def test_detect_unprotected_without_allow_is_pr_required():
    probe = _Probe(protection=None)
    policy = await detect_delivery_policy("o", "r", probe=probe, allow_direct_push=False)
    assert policy.mode == "pr_required"
    assert policy.protected is False


async def test_detect_unprotected_with_allow_is_direct_push():
    probe = _Probe(protection=None, default_branch="trunk")
    policy = await detect_delivery_policy("o", "r", probe=probe, allow_direct_push=True)
    assert policy.mode == "direct_push"
    assert policy.default_branch == "trunk"


async def test_detect_uncertain_defaults_to_pr_required():
    # repo metadata error
    p1 = await detect_delivery_policy("o", "r", probe=_Probe(raise_repo=True))
    assert p1.mode == "pr_required" and "uncertain" in p1.detection_note
    # protection probe error
    p2 = await detect_delivery_policy("o", "r", probe=_Probe(raise_protection=True))
    assert p2.mode == "pr_required" and "uncertain" in p2.detection_note


# ── merge decision / gating ──────────────────────────────────────────────────


def test_url_only_company_pauses():
    d = decide_merge(None)
    assert d.action == "awaiting_repo_connection"
    assert d.requires_approval is False


def test_first_merge_is_gated_then_follows_policy():
    policy = DeliveryPolicy(mode="pr_required", protected=True)
    conn = build_repo_connection("https://github.com/o/r", policy=policy)
    # first merge → Telegram gate regardless of mode
    first = decide_merge(conn)
    assert first.action == "telegram_gate" and first.requires_approval is True
    # after consent → follow policy (pr_required → open_pr)
    conn2 = record_first_merge_consent(conn)
    after = decide_merge(conn2)
    assert after.action == "open_pr" and after.requires_approval is False


def test_direct_push_policy_after_consent():
    policy = DeliveryPolicy(mode="direct_push", protected=False)
    conn = record_first_merge_consent(
        build_repo_connection("https://github.com/o/r", policy=policy)
    )
    d = decide_merge(conn)
    assert d.action == "direct_push" and d.requires_approval is False


def test_build_repo_connection_rejects_non_github():
    with pytest.raises(UnsupportedProviderError):
        build_repo_connection("https://gitlab.com/o/r")


# ── onboarding attach (fake store) ───────────────────────────────────────────


class _FakeStore:
    def __init__(self, company):
        self._company = company
        self.saved = None

    async def get_company(self, company_id):
        return self._company

    async def update_company(self, company):
        self.saved = company
        return company


async def test_attach_persists_connection_to_company():
    company = Company(name="Acme", domain="acme.com", id="c1")
    store = _FakeStore(company)
    conn = await attach_repo_connection(
        "c1", "https://github.com/acme/site", store=store,
        probe=_Probe(protection={"required_pull_request_reviews": {}}),
    )
    assert conn is not None and conn.full_name == "acme/site"
    assert store.saved is not None
    assert store.saved.repo_connection.full_name == "acme/site"
    assert store.saved.repo_connection.policy.mode == "pr_required"


async def test_attach_skips_non_github_without_raising():
    store = _FakeStore(Company(name="Acme", domain="acme.com", id="c1"))
    conn = await attach_repo_connection("c1", "https://gitlab.com/acme/site", store=store)
    assert conn is None
    assert store.saved is None


def test_company_defaults_to_no_repo_connection():
    # URL-only companies (and all existing persisted companies) migrate to None.
    assert Company(name="Acme", domain="acme.com").repo_connection is None
    assert isinstance(
        RepoConnection(owner="o", repo="r"), RepoConnection
    )
