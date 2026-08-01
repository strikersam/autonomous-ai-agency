"""Regression test: production leaked a live MongoDB password in plaintext.

services/company_graph_store.py logged the raw MONGO_URL on every boot —
``mongodb+srv://user:password@host/...`` — putting the database password in
every log aggregator (and, in this incident, directly in a support message).
CLAUDE.md's constitution requires secrets stay env-only and never touch a
log line; ``packages.security.redact.redact_connection_url()`` is the fix,
shared by both call sites that name a connection target
(``services/company_graph_store.py``, ``scripts/register_agent_runtimes.py``)
instead of each reimplementing its own regex.

All credentials below are synthetic — assembled from literal fragments so no
scanner mistakes this file for a second copy of the leaked secret.
"""
from __future__ import annotations

import logging

from packages.security.redact import redact_connection_url

_FAKE_USER = "svc" + "acct"
_FAKE_PASSWORD = "test" + "-pw-" + "1234"


class TestRedactConnectionUrl:
    def test_strips_credentials_from_srv_uri(self) -> None:
        raw = f"mongodb+srv://{_FAKE_USER}:{_FAKE_PASSWORD}@cluster0.example.net/?appName=Test"
        redacted = redact_connection_url(raw)
        assert _FAKE_PASSWORD not in redacted
        assert _FAKE_USER not in redacted
        assert "cluster0.example.net" in redacted, "host must stay visible for debugging"

    def test_strips_credentials_from_plain_uri(self) -> None:
        raw = f"mongodb://{_FAKE_USER}:{_FAKE_PASSWORD}@10.0.0.5:27017"
        redacted = redact_connection_url(raw)
        assert _FAKE_PASSWORD not in redacted
        assert "10.0.0.5:27017" in redacted

    def test_a_url_with_no_credentials_is_returned_unchanged(self) -> None:
        raw = "mongodb://localhost:27017"
        assert redact_connection_url(raw) == raw

    def test_percent_encoded_special_characters_in_the_password_are_redacted(self) -> None:
        # A literal "@" in a password must be percent-encoded (%40) to keep
        # the URI's userinfo delimiter unambiguous — this is what a real
        # generated password looks like on the wire.
        raw = f"mongodb+srv://{_FAKE_USER}:pw%40{_FAKE_PASSWORD}@cluster0.example.net/db"
        redacted = redact_connection_url(raw)
        assert f"pw%40{_FAKE_PASSWORD}" not in redacted
        assert "cluster0.example.net" in redacted

    def test_secret_query_parameter_is_redacted_even_with_no_userinfo(self) -> None:
        raw = f"mongodb://cluster0.example.net/db?tlsCertificateKeyFilePassword={_FAKE_PASSWORD}"
        redacted = redact_connection_url(raw)
        assert _FAKE_PASSWORD not in redacted
        assert "tlsCertificateKeyFilePassword=" in redacted, "the key name may stay, only the value is secret"

    def test_secret_query_parameter_is_redacted_alongside_userinfo(self) -> None:
        raw = (
            f"mongodb+srv://{_FAKE_USER}:{_FAKE_PASSWORD}@cluster0.example.net/db"
            f"?retryWrites=true&w=majority&tlsCertificateKeyFilePassword=anotherSecret"
        )
        redacted = redact_connection_url(raw)
        assert _FAKE_PASSWORD not in redacted
        assert "anotherSecret" not in redacted
        # Non-secret query parameters must survive untouched.
        assert "retryWrites=true" in redacted
        assert "w=majority" in redacted


class TestLoggingCallSitesRedactCredentials:
    """Integration coverage: the actual log lines this module emits must
    never carry the raw MONGO_URL, only its redacted form.

    Constructing ``MongoDBStore`` and calling ``_get_db()`` does not connect
    — Motor's ``AsyncIOMotorClient`` is lazy — so this exercises the real
    logging call sites without needing a reachable MongoDB.
    """

    def test_company_graph_store_init_does_not_log_credentials(self, monkeypatch, caplog) -> None:
        import services.company_graph_store as cgs

        fake_url = f"mongodb+srv://{_FAKE_USER}:{_FAKE_PASSWORD}@cluster0.example.net/?appName=Test"
        monkeypatch.setattr(cgs, "MONGO_URL", fake_url)

        with caplog.at_level(logging.INFO, logger="company_graph.store"):
            cgs.CompanyGraphStore(backend="mongodb")

        messages = [r.getMessage() for r in caplog.records]
        assert not any(_FAKE_PASSWORD in m for m in messages), messages
        assert any("cluster0.example.net" in m for m in messages), messages

    def test_mongodb_store_get_db_does_not_log_credentials(self, monkeypatch, caplog) -> None:
        import services.company_graph_store as cgs

        fake_url = f"mongodb://{_FAKE_USER}:{_FAKE_PASSWORD}@10.0.0.5:27017"
        monkeypatch.setattr(cgs, "MONGO_URL", fake_url)
        store = cgs.MongoDBStore()

        with caplog.at_level(logging.INFO, logger="company_graph.store"):
            store._get_db()

        messages = [r.getMessage() for r in caplog.records]
        assert not any(_FAKE_PASSWORD in m for m in messages), messages
        assert any("10.0.0.5:27017" in m for m in messages), messages
