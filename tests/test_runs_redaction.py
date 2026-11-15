"""Phase 2 J: run redaction covers credential keys and shapes; the memory matcher never raises."""
from __future__ import annotations

import pytest

from packages.runs.backend import MemoryTable, _memory_matches
from packages.runs.redaction import redact_value

# Built at run time so no secret shaped literal sits in the test file.
_JWT = "eyJ" + "a" * 12 + ".eyJ" + "b" * 12 + "." + "c" * 20
_SLACK = "xox" + "b-" + "1" * 12 + "-abcdefghij"
_PEM = ("-----BEGIN RSA " + "PRIVATE KEY-----\nMIIBOgIBAAJBAKj34GkxFhD90vcNLYLInFEX\n"
        "-----END RSA " + "PRIVATE KEY-----")


@pytest.mark.parametrize("key", ["password", "Secret", "API_KEY", "apiKey", "Authorization",
                                 "db_credential", "access_token", "x-api-key"])
def test_values_under_sensitive_keys_are_replaced(key):
    out = redact_value({key: "plainvalue", "nested": [{key: {"deep": "x"}}], "note": "ok"})
    assert out[key] == "***" and out["nested"][0][key] == "***" and out["note"] == "ok"


def test_numeric_fencing_tokens_are_kept():
    out = redact_value({"token": 3, "lease_token": 7, "max_tokens": 512, "password": None})
    assert out == {"token": 3, "lease_token": 7, "max_tokens": 512, "password": None}


@pytest.mark.parametrize("secret", [_JWT, _SLACK])
def test_jwt_and_slack_tokens_in_free_text(secret):
    out = redact_value({"msg": f"call failed with {secret} attached"})
    assert secret not in out["msg"] and "call failed" in out["msg"]


def test_json_quoted_api_key_and_pem_block():
    text = 'body={"api_key": "plainvalue99", "user": "a"} key=' + _PEM
    out = redact_value(text)
    assert "plainvalue99" not in out and '"api_key"' in out and '"user": "a"' in out
    assert "MIIBOgIBAAJB" not in out and "PRIVATE KEY" not in out


def test_lt_against_a_non_numeric_stored_value_is_no_match():
    assert _memory_matches({"expires_at": "garbage"}, {"expires_at": ("lt", 10.0)}) is False
    assert _memory_matches({"expires_at": 5.0}, {"expires_at": ("lt", 10.0)}) is True
    assert _memory_matches({}, {"expires_at": ("lt", 10.0)}) is False


@pytest.mark.anyio
async def test_memory_table_compare_and_set_survives_a_bad_value():
    table = MemoryTable()
    await table.insert_if_absent("r1", {"_id": "r1", "expires_at": "garbage"})
    assert await table.compare_and_set("r1", {"expires_at": ("lt", 10.0)}, {"x": 1}) is False
