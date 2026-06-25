"""Security regression tests for key_store: hashing, constant-time compare, rate limiting."""
from __future__ import annotations

import hashlib

import pytest

import key_store
from key_store import KeyStore, RateLimitError, issue_new_api_key


@pytest.fixture(autouse=True)
def _reset_rate_state():
    key_store._failed_attempts.clear()
    yield
    key_store._failed_attempts.clear()


def _make_store(tmp_path):
    return KeyStore(tmp_path / "keys.json")


def test_keys_stored_as_hash_not_plaintext(tmp_path):
    store = _make_store(tmp_path)
    plain, rec = issue_new_api_key(store, "a@b.com", "eng")
    raw = (tmp_path / "keys.json").read_text(encoding="utf-8")
    # The plaintext key must never be written to disk; only its hash.
    assert plain not in raw
    assert hashlib.sha256(plain.encode()).hexdigest() in raw


def test_lookup_success_and_miss(tmp_path):
    store = _make_store(tmp_path)
    plain, rec = issue_new_api_key(store, "a@b.com", "eng")
    assert store.lookup_plain_key(plain) is not None
    assert store.lookup_plain_key("llms-nope") is None


def test_rate_limit_blocks_after_max_failed(tmp_path):
    store = _make_store(tmp_path)
    issue_new_api_key(store, "a@b.com", "eng")
    ip = "10.0.0.5"
    # _RATE_MAX failed lookups are allowed, the next one raises.
    for _ in range(key_store._RATE_MAX):
        assert store.lookup_plain_key("bad-key", client_ip=ip) is None
    with pytest.raises(RateLimitError, match="Too many failed"):
        store.lookup_plain_key("bad-key", client_ip=ip)


def test_rate_limit_is_per_ip(tmp_path):
    store = _make_store(tmp_path)
    for _ in range(key_store._RATE_MAX):
        store.lookup_plain_key("bad-key", client_ip="1.1.1.1")
    # A different IP is unaffected.
    assert store.lookup_plain_key("bad-key", client_ip="2.2.2.2") is None


def test_successful_lookup_not_rate_limited(tmp_path):
    store = _make_store(tmp_path)
    plain, _ = issue_new_api_key(store, "a@b.com", "eng")
    ip = "3.3.3.3"
    for _ in range(key_store._RATE_MAX * 2):
        assert store.lookup_plain_key(plain, client_ip=ip) is not None
