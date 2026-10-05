"""Outbound prompt sanitiser: modes, content shapes, no mutation of the input."""

from __future__ import annotations

import copy

import pytest

from packages.gateway.sanitizer import sanitize_payload
from tests.gateway_support import (  # noqa: F401
    chat_body,
    clear_dependency_overrides,
    gateway_env,
    make_client,
)

SSN = "123-45-6789"
CARD = "4111 1111 1111 1111"  # Luhn-valid test number
TOKEN = "ghp_" + "a" * 24


def _payload(content):
    return {"model": "m", "messages": [{"role": "user", "content": content}]}


def test_off_returns_the_same_object_untouched(gateway_env):
    payload = _payload(f"ssn {SSN} token {TOKEN}")
    assert sanitize_payload(payload) is payload


def test_unknown_mode_falls_back_to_off(gateway_env):
    gateway_env.setenv("GATEWAY_SANITIZER_MODE", "aggressive")
    payload = _payload(SSN)
    assert sanitize_payload(payload) is payload


def test_pii_mode_redacts_pii_but_leaves_secrets(gateway_env):
    gateway_env.setenv("GATEWAY_SANITIZER_MODE", "pii")
    out = sanitize_payload(_payload(f"ssn {SSN}, card {CARD}, token {TOKEN}"))
    text = out["messages"][0]["content"]
    assert SSN not in text and CARD not in text
    assert TOKEN in text


def test_secrets_and_pii_mode_redacts_both(gateway_env):
    gateway_env.setenv("GATEWAY_SANITIZER_MODE", "secrets_and_pii")
    out = sanitize_payload(_payload(f"ssn {SSN} key {TOKEN} db postgres://user:hunter2@host/db"))
    text = out["messages"][0]["content"]
    assert SSN not in text and TOKEN not in text and "hunter2" not in text
    assert "***" in text


def test_luhn_invalid_number_is_not_mistaken_for_a_card(gateway_env):
    gateway_env.setenv("GATEWAY_SANITIZER_MODE", "pii")
    out = sanitize_payload(_payload("order 4111 1111 1111 1112"))
    assert out["messages"][0]["content"] == "order 4111 1111 1111 1112"


def test_multimodal_text_parts_are_sanitised_and_other_parts_kept(gateway_env):
    gateway_env.setenv("GATEWAY_SANITIZER_MODE", "pii")
    image = {"type": "image_url", "image_url": {"url": f"data:x;{SSN}"}}
    payload = _payload([{"type": "text", "text": f"my ssn is {SSN}"}, image])
    original = copy.deepcopy(payload)

    out = sanitize_payload(payload)

    parts = out["messages"][0]["content"]
    assert SSN not in parts[0]["text"]
    assert parts[1] == image
    assert payload == original, "the caller's payload must not be mutated"


def test_every_role_and_non_text_payload_shapes_are_handled(gateway_env):
    gateway_env.setenv("GATEWAY_SANITIZER_MODE", "pii")
    payload = {
        "model": "m",
        "messages": [
            {"role": "system", "content": f"admin ssn {SSN}"},
            {"role": "assistant", "content": None, "tool_calls": []},
            {"role": "tool", "content": SSN},
            "not-a-dict",
        ],
    }
    out = sanitize_payload(payload)
    assert SSN not in out["messages"][0]["content"] and SSN not in out["messages"][2]["content"]
    assert out["messages"][1]["content"] is None
    assert out["messages"][3] == "not-a-dict"
    assert sanitize_payload({"model": "m"}) == {"model": "m"}


@pytest.mark.parametrize("mode", ["pii", "secrets_and_pii"])
def test_upstream_never_sees_the_redacted_values(gateway_env, mode):
    gateway_env.setenv("GATEWAY_SANITIZER_MODE", mode)
    client, upstream, observations = make_client(gateway_env)

    resp = client.post("/v1/chat/completions", json=chat_body(f"my ssn is {SSN}"))

    assert resp.status_code == 200
    assert SSN not in upstream.requests[0].content.decode()
    assert SSN not in str(observations[0]["messages"])


def test_default_mode_leaves_the_upstream_body_unchanged(gateway_env):
    client, upstream, _obs = make_client(gateway_env)
    client.post("/v1/chat/completions", json=chat_body(f"my ssn is {SSN}"))
    assert SSN in upstream.requests[0].content.decode()
