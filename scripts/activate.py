#!/usr/bin/env python3
"""Self-service instance activation for the owner / self-hoster.

Mints an Ed25519-signed activation token for THIS instance and installs it so
the onboarding wizard unlocks — no "email the owner and wait for a code" round
trip required when you are the one running the box.

Usage:
    python scripts/activate.py                      # auto: instance id from .instance_id
    python scripts/activate.py --email you@host.com # stamp an email into the token
    python scripts/activate.py --print-only         # print the token, do not install it
    python scripts/activate.py --instance-id <uuid> # activate a specific instance id

Key handling (first match wins):
  1. ACTIVATION_PRIVATE_KEY_B64 env var (base64 of the raw 32-byte Ed25519 private key)
  2. .activation_keypair.json in the repo root (written by a previous run, git-ignored)
  3. A fresh keypair is generated and persisted to .activation_keypair.json (chmod 600)

If a fresh keypair is generated its PUBLIC key will not match the key embedded in
activation.py. The script prints the public key and tells you to export
ACTIVATION_PUBLIC_KEY_B64=<key> so the running server trusts tokens you mint.

Tip: if you just want to disable the licensing gate entirely on your own server,
set ACTIVATION_REQUIRED=false in the backend environment instead of running this.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

# Allow running from repo root: python scripts/activate.py
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from packages.config.activation import (  # noqa: E402
    _ACTIVATION_FILE,
    _generate_token_for_owner,
    get_or_create_instance_id,
    owner_public_key_b64,
    verify_activation_token,
)

_KEYPAIR_FILE = _REPO_ROOT / ".activation_keypair.json"


def _derive_public_b64(private_b64: str) -> str:
    """Derive the base64 raw Ed25519 public key from a base64 raw private key."""
    raw_priv = base64.b64decode(private_b64)
    priv = Ed25519PrivateKey.from_private_bytes(raw_priv)
    pub_raw = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(pub_raw).decode()


def _load_or_create_keypair() -> tuple[str, str, bool]:
    """Return (private_b64, public_b64, generated)."""
    env_priv = os.environ.get("ACTIVATION_PRIVATE_KEY_B64", "").strip()
    if env_priv:
        return env_priv, _derive_public_b64(env_priv), False

    if _KEYPAIR_FILE.exists():
        data = json.loads(_KEYPAIR_FILE.read_text())
        priv = data["private_key_b64"]
        return priv, _derive_public_b64(priv), False

    priv = Ed25519PrivateKey.generate()
    priv_raw = priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    pub_raw = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    priv_b64 = base64.b64encode(priv_raw).decode()
    pub_b64 = base64.b64encode(pub_raw).decode()
    _KEYPAIR_FILE.write_text(json.dumps({"private_key_b64": priv_b64, "public_key_b64": pub_b64}, indent=2))
    _KEYPAIR_FILE.chmod(0o600)
    return priv_b64, pub_b64, True


def main() -> int:
    """Mint an activation token for this instance and install it (or print it)."""
    parser = argparse.ArgumentParser(description="Self-mint and install an instance activation token.")
    parser.add_argument("--instance-id", default="", help="Instance ID (default: read/create .instance_id).")
    parser.add_argument("--email", default="self-hosted@localhost", help="Email stamped into the token.")
    parser.add_argument("--print-only", action="store_true", help="Print the token; do not write .activation_token.")
    args = parser.parse_args()

    iid = args.instance_id.strip() or get_or_create_instance_id()
    # Capture the key the server currently trusts BEFORE we override the env below.
    trusted_before = owner_public_key_b64()
    priv_b64, pub_b64, generated = _load_or_create_keypair()

    token = _generate_token_for_owner(iid, args.email, priv_b64)

    # Verify against the public key we just used, so success means the running
    # server will accept this token once it trusts that key.
    os.environ["ACTIVATION_PUBLIC_KEY_B64"] = pub_b64
    result = verify_activation_token(token, iid)
    if not result.valid:
        print(f"ERROR: minted token failed verification: {result.error}", file=sys.stderr)
        return 1

    embedded_match = pub_b64 == trusted_before

    print(f"Instance ID : {iid}")
    print(f"Public key  : {pub_b64}")
    print()

    if not args.print_only:
        _ACTIVATION_FILE.write_text(token + "\n")
        _ACTIVATION_FILE.chmod(0o600)
        print(f"Installed activation token → {_ACTIVATION_FILE.name}")
    else:
        print("Activation token (paste into the Activation panel):")
        print(token)

    print()
    if generated or not embedded_match:
        print("This token was signed with a keypair that the server does not trust by default.")
        print("Make the server trust it by exporting this in the backend environment:")
        print()
        print(f'    ACTIVATION_PUBLIC_KEY_B64="{pub_b64}"')
        print()
        print("Then restart the backend. (On Render: add it under Environment, then redeploy.)")
    else:
        print("Done — restart the backend and onboarding will be unlocked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
