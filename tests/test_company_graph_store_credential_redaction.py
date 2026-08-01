"""Regression test: production leaked a live MongoDB password in plaintext.

services/company_graph_store.py logged the raw MONGO_URL on every boot —
``mongodb+srv://user:password@host/...`` — putting the database password in
every log aggregator (and, in this incident, directly in a support message).
CLAUDE.md's constitution requires secrets stay env-only and never touch a
log line; ``_redact_mongo_url()`` is the fix, applied at both call sites that
name the connection target.
"""
from __future__ import annotations

from services.company_graph_store import _redact_mongo_url


class TestRedactMongoUrl:
    def test_strips_credentials_from_srv_uri(self) -> None:
        raw = "mongodb+srv://dbadmin:WikiAdmin2026!@cluster0.ncgdysv.mongodb.net/?appName=Cluster0"
        redacted = _redact_mongo_url(raw)
        assert "WikiAdmin2026!" not in redacted
        assert "dbadmin" not in redacted
        assert "cluster0.ncgdysv.mongodb.net" in redacted, "host must stay visible for debugging"

    def test_strips_credentials_from_plain_uri(self) -> None:
        raw = "mongodb://admin:hunter2@10.0.0.5:27017"
        redacted = _redact_mongo_url(raw)
        assert "hunter2" not in redacted
        assert "10.0.0.5:27017" in redacted

    def test_a_url_with_no_credentials_is_returned_unchanged(self) -> None:
        raw = "mongodb://localhost:27017"
        assert _redact_mongo_url(raw) == raw

    def test_percent_encoded_special_characters_in_the_password_are_redacted(self) -> None:
        # A literal "@" in a password must be percent-encoded (%40) to keep
        # the URI's userinfo delimiter unambiguous — this is what a real
        # generated password looks like on the wire.
        raw = "mongodb+srv://user:p%40ss!@cluster0.example.mongodb.net/db"
        redacted = _redact_mongo_url(raw)
        assert "p%40ss!" not in redacted
        assert "cluster0.example.mongodb.net" in redacted
