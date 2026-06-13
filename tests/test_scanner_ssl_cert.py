"""Offline regression tests for the SSL/TLS certificate analysis fix.

Background: `_analyze_ssl_cert` previously disabled certificate verification
(`CERT_NONE`) before calling `getpeercert()`. CPython only populates the parsed
issuer / SAN dict when the cert is *verified*, so the whole analysis silently
returned zero systems. The fix verifies first and falls back to decoding the
raw DER cert (`_decode_der_cert`) for unverified certs.

These tests are deterministic and require no network access — they exercise the
DER decoder against a self-signed cert generated in-memory and assert that the
issuer/SAN mapping logic surfaces detected systems from the decoded dict shape.
"""
from __future__ import annotations

import datetime

import pytest

from services.scanner import WebsiteScanner


def _make_self_signed_der(common_name: str, org: str, sans: list[str]) -> bytes:
    crypto = pytest.importorskip("cryptography")
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import Encoding

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, org),
    ])
    now = datetime.datetime.utcnow()
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(s) for s in sans]),
            critical=False,
        )
    )
    cert = builder.sign(key, hashes.SHA256())
    return cert.public_bytes(Encoding.DER)


def test_decode_der_cert_extracts_issuer_and_sans():
    der = _make_self_signed_der(
        common_name="*.cloudflaressl.com",
        org="Cloudflare, Inc.",
        sans=["myshopify.com", "shop.example.com"],
    )
    decoded = WebsiteScanner._decode_der_cert(der)

    # Same shape as ssl.getpeercert(): issuer tuple-of-tuples + subjectAltName.
    issuer_blob = " ".join(
        v for rdn in decoded["issuer"] for _k, v in rdn
    ).lower()
    assert "cloudflare" in issuer_blob

    san_values = {san for typ, san in decoded["subjectAltName"] if typ == "DNS"}
    assert "myshopify.com" in san_values


def test_decode_der_cert_bad_input_returns_empty_dict():
    # Garbage input must degrade to {} and never raise into the scan.
    assert WebsiteScanner._decode_der_cert(b"not-a-cert") == {}


def test_analyze_ssl_cert_maps_decoded_cert_to_systems(monkeypatch):
    """End-to-end (no network): force the unverified DER path and assert the
    issuer/SAN maps turn the decoded cert into detected systems — the exact
    behaviour that silently broke before the fix."""
    der = _make_self_signed_der(
        common_name="example.com",
        org="Let's Encrypt",
        sans=["www.vercel.app", "example.com"],
    )

    scanner = WebsiteScanner()

    class _FakeSSock:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def getpeercert(self, binary_form=False):
            # Mirror CPython: unverified handshake yields no parsed dict, only DER.
            return der if binary_form else {}

    class _FakeCtx:
        check_hostname = True
        verify_mode = None

        def wrap_socket(self, sock, server_hostname=None):
            return _FakeSSock()

    import ssl as _ssl
    import socket as _socket

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    # First (verified) context raises to exercise the DER fallback path.
    contexts = iter([_RaisingCtx(), _FakeCtx()])
    monkeypatch.setattr(_ssl, "create_default_context", lambda: next(contexts))
    monkeypatch.setattr(_socket, "create_connection", lambda *a, **k: _FakeConn())

    systems = scanner._analyze_ssl_cert("example.com")
    names = {s.name for s in systems}
    assert "Let's Encrypt" in names
    assert "Vercel" in names


class _RaisingCtx:
    check_hostname = True
    veri