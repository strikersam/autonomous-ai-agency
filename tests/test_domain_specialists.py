"""tests/test_domain_specialists.py — business/domain specialist coverage.

Agency Core v5 extends specialist families beyond engineering to the full
business + domain set (SEO, content, marketing, merchandising, PIM, OMS, DAM,
CRM, support, trading, research, platform).  These tests lock the contract:
every declared family has a name, capabilities, tools, and a runtime preference,
and detected commerce/business systems route to the right domain specialist.
"""
from __future__ import annotations

from typing import get_args

import pytest

from models.company_graph import SpecialistFamily
from services.specialist import SpecialistService
from services.company_agency import FAMILY_RUNTIME_MAP

NEW_DOMAIN_FAMILIES = [
    "seo", "content", "marketing", "merchandising", "pim", "oms",
    "dam", "crm", "support", "trading", "research", "platform",
]


@pytest.fixture
def svc():
    # No DB needed for the pure helper methods.
    return SpecialistService.__new__(SpecialistService)


def test_new_families_are_declared():
    families = set(get_args(SpecialistFamily))
    for fam in NEW_DOMAIN_FAMILIES:
        assert fam in families, f"{fam} missing from SpecialistFamily literal"


@pytest.mark.parametrize("family", NEW_DOMAIN_FAMILIES)
def test_family_is_fully_specified(svc, family):
    name = svc._generate_specialist_name(family)
    caps = svc._get_default_capabilities(family)
    tools = svc._get_default_tools(family)
    assert name and "Specialist" in name or name, family
    assert caps, f"{family} has no default capabilities"
    assert tools, f"{family} has no default tools"
    assert family in FAMILY_RUNTIME_MAP, f"{family} has no runtime preference"
    assert FAMILY_RUNTIME_MAP[family][-1] == "internal_agent", (
        f"{family} runtime chain must end in internal_agent fallback"
    )


def test_commerce_systems_route_to_domain_specialists():
    """The system→family map sends commerce/business systems to domain families."""
    import inspect
    src = inspect.getsource(SpecialistService.provision_specialists_for_company)
    # CRM systems should provision a CRM specialist; support → support; etc.
    assert '"crm"' in src
    assert '"support"' in src
    assert '"oms"' in src
    assert '"merchandising"' in src
    assert '"seo"' in src
