"""Company create/update must reject a bad domain with a 422, not a 500.

``CompanyCreateRequest`` accepted any string, so a domain like "acme" (no TLD)
passed request validation and then failed inside ``Company(**data)`` in the
service — an unhandled ValidationError, i.e. a 500 on the onboarding form.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from models.company_graph import Company, CompanyCreateRequest, CompanyUpdateRequest


@pytest.mark.parametrize("domain", ["acme", "qa-domain", "   "])
def test_create_request_rejects_invalid_domain(domain: str) -> None:
    with pytest.raises(ValidationError):
        CompanyCreateRequest(name="Acme", domain=domain)


def test_create_request_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        CompanyCreateRequest(name="  ", domain="acme.com")


def test_create_request_normalises_like_the_stored_model() -> None:
    req = CompanyCreateRequest(name=" Acme ", domain="https://Acme.COM/about")
    assert (req.name, req.domain) == ("Acme", "acme.com")
    assert Company(name="Acme", domain="https://Acme.COM/about").domain == "acme.com"


def test_update_request_checks_domain_only_when_given() -> None:
    assert CompanyUpdateRequest(name="Acme").domain is None
    with pytest.raises(ValidationError):
        CompanyUpdateRequest(domain="acme")


def test_create_endpoint_answers_422(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    import backend.server as server

    async def _user(request):
        return {"_id": "u1", "email": "qa@example.com", "role": "admin"}

    monkeypatch.setattr(server, "get_optional_user", _user)
    client = TestClient(server.app, raise_server_exceptions=False)
    resp = client.post("/api/company", json={"name": "Acme", "domain": "acme"})
    assert resp.status_code == 422, resp.text
    assert "valid domain" in resp.text
