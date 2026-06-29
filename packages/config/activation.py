"""packages.config.activation.py — Instance activation & phone-home licensing.

Design:
  1. On first run this server generates a unique instanceId (UUID v4) stored
     in .instance_id at the repo root (git-ignored).
  2. The onboarding wizard is LOCKED until the instance is activated.
  3. Activation flow:
       a. Admin copies instanceId from the UI and emails strikersam@gmail.com.
       b. Owner generates a signed activation token (JWT, Ed25519, private key
          never leaves owner's machine).
       c. Admin pastes token into the UI → server verifies → onboarding unlocks.
  4. Verification uses the **public key embedded here** — even if someone forks
     the repo and swaps the public key they can no longer use your relay/service,
     so the real gate is always the relay-side check.

Security properties:
  - Tokens are signed JWTs; forging one requires the Ed25519 private key.
  - instanceId is bound inside the token payload, so tokens cannot be reused
    across installations.
  - Token expiry is optional (set exp claim to enforce time-bound activations).
  - The activation state is cached in-process; the file is re-read on restart.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.exceptions import InvalidSignature

log = logging.getLogger("qwen-proxy")

# ── Embedded owner public key (Ed25519, base64-raw) ──────────────────────────
# To rotate: generate a new key pair, paste the new public key here, re-deploy.
# The corresponding private key is stored ONLY by the repo owner.
_OWNER_PUBLIC_KEY_B64 = "ed0rrMq2r56nlh8n9iQ4IHm9fS25qG3DQyOU1Bysnko="

# ── Paths ─────────────────────────────────────────────────────────────────────
_REPO_ROOT    = Path(__file__).resolve().parent
_INSTANCE_ID_FILE   = _REPO_ROOT / ".instance_id"
_ACTIVATION_FILE    = _REPO_ROOT / ".activation_token"

# ── JWT helpers (minimal, no external jwt lib needed) ────────────────────────

def _b64url_decode(s: str) -> bytes:
    # Pad to multiple of 4
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _decode_jwt_unverified(token: str) -> tuple[dict, dict, bytes, bytes]:
    """Split token into (header, payload, signing_input_bytes, signature_bytes)."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Not a JWT (expected 3 dot-separated parts)")
    header   = json.loads(_b64url_decode(parts[0]))
    payload  = json.loads(_b64url_decode(parts[1]))
    sig_input = f"{parts[0]}.{parts[1]}".encode()
    sig       = _b64url_decode(parts[2])
    return header, payload, sig_input, sig


# ── Public key loading ────────────────────────────────────────────────────────

# Ed25519 SubjectPublicKeyInfo DER prefix (RFC 8410)
_ED25519_DER_PREFIX = bytes.fromhex("302a300506032b6570032100")


def owner_public_key_b64() -> str:
    """Return the trusted owner public key (base64, raw 32 bytes).

    Operators self-hosting their own instance can override the embedded key by
    setting ``ACTIVATION_PUBLIC_KEY_B64`` in the environment. This lets them mint
    activation tokens with their own keypair (via ``scripts/activate.py``) without
    editing source. Falls back to the embedded owner key when the env var is unset.
    """
    return os.environ.get("ACTIVATION_PUBLIC_KEY_B64", "").strip() or _OWNER_PUBLIC_KEY_B64


def _load_public_key() -> Ed25519PublicKey:
    raw = base64.b64decode(owner_public_key_b64())
    if len(raw) != 32:
        raise ValueError(f"Ed25519 public key must be 32 raw bytes, got {len(raw)}")
    from cryptography.hazmat.primitives.serialization import load_der_public_key
    return load_der_public_key(_ED25519_DER_PREFIX + raw)  # type: ignore[return-value]


# ── Instance ID ───────────────────────────────────────────────────────────────

def get_or_create_instance_id() -> str:
    """Return the persistent instanceId, creating it on first call."""
    if _INSTANCE_ID_FILE.exists():
        val = _INSTANCE_ID_FILE.read_text().strip()
        if val:
            return val
    new_id = str(uuid.uuid4())
    try:
        _INSTANCE_ID_FILE.write_text(new_id + "\n")
        _INSTANCE_ID_FILE.chmod(0o600)
    except OSError as exc:
        log.warning("Could not persist instanceId: %s", exc)
    return new_id


# Lazily initialised at startup
_INSTANCE_ID: str = ""

def instance_id() -> str:
    global _INSTANCE_ID
    if not _INSTANCE_ID:
        _INSTANCE_ID = get_or_create_instance_id()
    return _INSTANCE_ID


# ── Activation verification ───────────────────────────────────────────────────

@dataclass
class ActivationResult:
    valid:        bool
    instance_id:  str = ""
    email:        str = ""
    issued_at:    float = 0.0
    expires_at:   float | None = None
    error:        str = ""
    raw_payload:  dict = field(default_factory=dict)


def verify_activation_token(token: str, iid: str | None = None) -> ActivationResult:
    """Verify a signed activation JWT.

    Args:
        token: The JWT string.
        iid:   Expected instanceId. Defaults to this server's instanceId.
    """
    expected_iid = iid or instance_id()
    try:
        header, payload, sig_input, sig = _decode_jwt_unverified(token)
        alg = header.get("alg", "")
        if alg != "EdDSA":
            return ActivationResult(valid=False, error=f"Unexpected algorithm: {alg!r}")

        pub = _load_public_key()
        try:
            pub.verify(sig, sig_input)
        except InvalidSignature:
            return ActivationResult(valid=False, error="Invalid signature")

        # Signature OK — validate claims
        token_iid = payload.get("iid", "")
        if token_iid != expected_iid:
            return ActivationResult(
                valid=False,
                error=f"instanceId mismatch (token={token_iid!r}, server={expected_iid!r})",
            )

        exp = payload.get("exp")
        if exp and time.time() > exp:
            return ActivationResult(valid=False, error="Activation token has expired")

        return ActivationResult(
            valid=True,
            instance_id=token_iid,
            email=payload.get("email", ""),
            issued_at=payload.get("iat", 0.0),
            expires_at=exp,
            raw_payload=payload,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("Unexpected error verifying activation token")
        return ActivationResult(valid=False, error=f"Verification error: {exc}")


# ── Persistent activation state ───────────────────────────────────────────────

def load_activation() -> ActivationResult | None:
    """Load and re-verify the persisted activation token, or None if not activated."""
    if not _ACTIVATION_FILE.exists():
        return None
    token = _ACTIVATION_FILE.read_text().strip()
    if not token:
        return None
    result = verify_activation_token(token)
    if not result.valid:
        log.warning("Stored activation token is invalid: %s", result.error)
        return None
    return result


def save_activation(token: str) -> ActivationResult:
    """Verify and persist an activation token. Returns the result."""
    result = verify_activation_token(token)
    if result.valid:
        try:
            _ACTIVATION_FILE.write_text(token + "\n")
            _ACTIVATION_FILE.chmod(0o600)
        except OSError as exc:
            log.warning("Could not persist activation token: %s", exc)
    return result


# ── In-process cache ──────────────────────────────────────────────────────────

_activation_cache: ActivationResult | None = None
_activation_loaded = False
_bypass_warned = False


def activation_required() -> bool:
    """Whether the licensing gate is enforced.

    Self-hosters who own the instance can disable the gate entirely by setting
    ``ACTIVATION_REQUIRED=false``. Defaults to enforced (``true``) so the
    signed-token path remains the standard for distributed installs.
    """
    val = os.environ.get("ACTIVATION_REQUIRED", "true").strip().lower()
    return val not in ("0", "false", "no", "off")


def is_activated() -> bool:
    """Fast in-process check. Loads from disk on first call.

    When ``ACTIVATION_REQUIRED=false`` the gate is bypassed and the instance is
    always treated as activated (self-hosted mode). This never weakens signature
    verification — it only makes the gate opt-out for the operator running the box.
    """
    global _activation_cache, _activation_loaded, _bypass_warned
    if not activation_required():
        if not _bypass_warned:
            log.warning(
                "ACTIVATION_REQUIRED=false — instance activation gate is DISABLED "
                "(self-hosted mode). Onboarding is unlocked without a signed token."
            )
            _bypass_warned = True
        return True
    if not _activation_loaded:
        _activation_cache = load_activation()
        _activation_loaded = True
    return _activation_cache is not None and _activation_cache.valid


def get_activation() -> ActivationResult | None:
    """Return the current activation, or None."""
    is_activated()  # ensure loaded
    return _activation_cache


def invalidate_activation_cache() -> None:
    global _activation_loaded
    _activation_loaded = False


# ── API helper — generate activation token (owner tool, not shipped in prod) ──

def _generate_token_for_owner(instance_id_val: str, email: str, private_key_b64: str) -> str:  # noqa: E501
    """Owner-side tool: sign an activation token.

    Usage (run from owner's machine, NEVER in the repo):
        python3 -c "from packages.config.activation import _generate_token_for_owner; print(_generate_token_for_owner('<iid>', 'user@example.com', '<PRIV_KEY_B64>'))"
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding as Enc, PrivateFormat, NoEncryption

    raw_priv = base64.b64decode(private_key_b64)
    priv = Ed25519PrivateKey.from_private_bytes(raw_priv)

    header  = _b64url_encode(json.dumps({"alg": "EdDSA", "typ": "JWT"}).encode())
    payload = _b64url_encode(json.dumps({
        "iid":   instance_id_val,
        "email": email,
        "iat":   int(time.time()),
        # "exp": int(time.time()) + 365*24*3600,  # uncomment for 1-year expiry
    }).encode())
    signing_input = f"{header}.{payload}".encode()
    sig = priv.sign(signing_input)
    return f"{header}.{payload}.{_b64url_encode(sig)}"
