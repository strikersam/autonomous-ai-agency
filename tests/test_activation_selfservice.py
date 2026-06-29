"""Tests for self-service activation: env-overridable owner key, the
ACTIVATION_REQUIRED escape hatch, and the scripts/activate.py CLI.

These cover the onboarding-unblock fix: an owner/self-hoster can mint and
install a valid activation token with their own keypair (or disable the gate
outright) instead of emailing for a signed code.
"""
from __future__ import annotations

import base64
import os
import subprocess
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient

import packages.config.activation as activation
from packages.config.activation_api import activation_router

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _make_keypair() -> tuple[str, str]:
    priv = Ed25519PrivateKey.generate()
    priv_b64 = base64.b64encode(
        priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    ).decode()
    pub_b64 = base64.b64encode(
        priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ).decode()
    return priv_b64, pub_b64


def test_env_public_key_round_trip(monkeypatch) -> None:
    priv_b64, pub_b64 = _make_keypair()
    monkeypatch.setenv("ACTIVATION_PUBLIC_KEY_B64", pub_b64)

    token = activation._generate_token_for_owner("iid-round-trip", "me@example.com", priv_b64)
    result = activation.verify_activation_token(token, "iid-round-trip")

    assert result.valid, result.error
    assert result.email == "me@example.com"


def test_token_bound_to_instance_id(monkeypatch) -> None:
    priv_b64, pub_b64 = _make_keypair()
    monkeypatch.setenv("ACTIVATION_PUBLIC_KEY_B64", pub_b64)

    token = activation._generate_token_for_owner("iid-A", "me@example.com", priv_b64)
    # A token minted for iid-A must not validate for a different instance.
    assert not activation.verify_activation_token(token, "iid-B").valid


def test_untrusted_key_rejected(monkeypatch) -> None:
    # No env override → embedded owner key is trusted. A token from a random
    # keypair must fail the signature check.
    monkeypatch.delenv("ACTIVATION_PUBLIC_KEY_B64", raising=False)
    priv_b64, _ = _make_keypair()
    token = activation._generate_token_for_owner("iid-x", "x@example.com", priv_b64)
    result = activation.verify_activation_token(token, "iid-x")
    assert not result.valid
    assert result.error == "Invalid signature"


def test_activation_required_default(monkeypatch) -> None:
    monkeypatch.delenv("ACTIVATION_REQUIRED", raising=False)
    assert activation.activation_required() is True


def test_activation_required_bypass(monkeypatch) -> None:
    monkeypatch.setenv("ACTIVATION_REQUIRED", "false")
    activation._bypass_warned = False
    assert activation.activation_required() is False
    assert activation.is_activated() is True


def test_status_activated_when_gate_disabled(monkeypatch) -> None:
    monkeypatch.setenv("ACTIVATION_REQUIRED", "false")
    activation._bypass_warned = False
    app = FastAPI()
    app.include_router(activation_router)
    client = TestClient(app, raise_server_exceptions=False)

    r = client.get("/api/activation/status")
    assert r.status_code == 200
    body = r.json()
    assert body["activated"] is True
    assert body["instance_id"]


def test_activate_cli_mints_verifiable_token() -> None:
    priv_b64, _ = _make_keypair()
    env = {**os.environ, "ACTIVATION_PRIVATE_KEY_B64": priv_b64}
    env.pop("ACTIVATION_PUBLIC_KEY_B64", None)

    result = subprocess.run(
        [sys.executable, "scripts/activate.py", "--instance-id", "cli-iid-1",
         "--email", "cli@example.com", "--print-only"],
        capture_output=True, text=True, env=env, cwd=str(_REPO_ROOT),
    )
    assert result.returncode == 0, result.stderr
    assert "cli-iid-1" in result.stdout
    assert "ACTIVATION_PUBLIC_KEY_B64" in result.stdout  # tells the user how to trust it
