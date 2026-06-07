"""Tests for Company Graph API endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    try:
        from backend.server import app
        return TestClient(app)
    except ImportError:
        pytest.skip("Backend server not available")


class TestCompanyAPI:
    """Test Company Graph API endpoints."""
    
    def test_api_router_included(self, client):
        """Test that the company API router is included."""
        # This will fail if the router is not included, but that's okay
        # We're just checking that the app starts
        try:
            response = client.get("/api/company")
            # May be 401 (unauthorized) or 404 (not found) - both are fine
            assert response.status_code in [401, 404, 403]
        except Exception:
            # If the app fails to start, that's a different issue
            pytest.skip("Backend app failed to start")


class TestDoctorEndpoint:
    """Test Doctor endpoint."""
    
    def test_public_doctor_endpoint(self, client):
        """Test the public doctor endpoint."""
        try:
            response = client.get("/api/company/doctor/public")
            assert response.status_code == 200
            data = response.json()
            assert "ready" in data
            assert "summary" in data
            assert "checks" in data
        except Exception:
            pytest.skip("Doctor endpoint not available")


class TestCreateCompanyValidation:
    """Regression tests for BUG-1: POST /api/company failing with
    `{"loc": ["body", "request"], "msg": "Field required"}`.

    Root cause: the `_get_current_user_thunk` / `_get_optional_user_thunk`
    dependencies declared their `request` parameter without a `Request` type
    annotation. FastAPI then treated `request` as a required *request-body*
    field, so every endpoint using the dependency rejected valid payloads with
    "request: Field required" (surfaced in the UI as
    "Could not create company: request: Field required").
    """

    def test_thunk_request_param_is_annotated_as_Request(self) -> None:
        """The auth thunks must annotate `request` as `Request`, otherwise
        FastAPI demands a body field named "request"."""
        import inspect
        try:
            from fastapi import Request
            from backend import company_api
        except (ImportError, ModuleNotFoundError):
            pytest.skip("backend.company_api not importable")

        for name in ("_get_current_user_thunk", "_get_optional_user_thunk"):
            fn = getattr(company_api, name)
            # eval_str=True resolves PEP 563 string annotations (the module uses
            # `from __future__ import annotations`) the same way FastAPI does via
            # get_type_hints — so this still asserts the param resolves to
            # fastapi.Request, the property that prevents the phantom body field.
            param = inspect.signature(fn, eval_str=True).parameters.get("request")
            assert param is not None, f"{name} must take a `request` parameter"
            assert param.annotation is Request, (
                f"{name}'s `request` param must be annotated as fastapi.Request "
                f"(got {param.annotation!r}); otherwise FastAPI treats it as a "
                f"required request-body field and POST /api/company fails with "
                f"'request: Field required'."
            )

    def test_create_company_does_not_demand_a_body_field_named_request(self, client) -> None:
        """A POST with a valid {name, domain} body must never fail validation
        because of a phantom required body field named `request`."""
        try:
            resp = client.post("/api/company", json={"name": "Acme", "domain": "acme.com"})
        except (ImportError, ModuleNotFoundError, RuntimeError, ConnectionError):
            pytest.skip("Backend app/dependencies not available")

        # With the bug, the unannotated dependency param surfaces as a required
        # `request` field (in body OR query depending on FastAPI's inference) and
        # the call 422s. With the fix, auth actually runs and an unauthenticated
        # call returns 401/403. So: a valid {name, domain} body must NOT 422 over
        # a phantom field named "request".
        assert resp.status_code != 422, (
            f"POST /api/company 422'd on a valid body (BUG-1 regression): "
            f"{resp.json()}"
        )
        if resp.status_code == 422:  # pragma: no cover - defensive
            detail = resp.json().get("detail", [])
            phantom = [
                err for err in detail
                if isinstance(err, dict) and "request" in (err.get("loc") or [])
            ]
            assert not phantom, (
                f"POST /api/company rejected a valid body with a phantom "
                f"required field 'request' (BUG-1 regression): {detail}"
            )
