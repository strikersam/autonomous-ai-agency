#!/usr/bin/env python3
"""
CI helper: generate an API key and print ONLY the plaintext to stdout.
Used by the E2E GitHub Actions workflow so the key can be captured cleanly.

Usage:
    python scripts/e2e_generate_key.py --keys-file e2e-keys.json
"""
from __future__ import annotations
import argparse, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from key_store import KeyStore, issue_new_api_key


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keys-file", default=os.environ.get("KEYS_FILE", "e2e-keys.json"))
    parser.add_argument("--email", default="ci@llmrelay.local")
    parser.add_argument("--department", default="ci")
    args = parser.parse_args()

    ks = KeyStore(Path(args.keys_file))
    plain, _ = issue_new_api_key(ks, args.email, args.department)
    # Print ONLY the key so the workflow can do: KEY=$(python ...) without parsing
    print(plain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
