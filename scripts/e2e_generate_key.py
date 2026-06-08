#!/usr/bin/env python3
"""
CI helper: generate an API key and write it to a file (not stdout).

Writing to a file rather than stdout avoids the CodeQL
"clear-text logging of sensitive data" finding — the key never appears
in the Actions log; the workflow reads and immediately masks it.

Usage (CI):
    export E2E_KEY_OUTPUT_FILE=/tmp/e2e_api_key.txt
    python scripts/e2e_generate_key.py --keys-file e2e-keys.json

Usage (local, writes to stdout-compatible path /dev/stdout):
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

    # Write to E2E_KEY_OUTPUT_FILE if set (CI); fall back to /dev/stdout (local).
    # Never print the key directly — keeps it out of the Actions log until the
    # workflow masks it with  echo "::add-mask::$(cat $file)".
    # CodeQL: py/clear-text-storage-of-sensitive-data — intentional: CI helper
    # writes to a file that the workflow immediately masks with ::add-mask::.
    output_path = os.environ.get("E2E_KEY_OUTPUT_FILE", "/dev/stdout")
    Path(output_path).write_text(plain, encoding="utf-8")  # nosec B108 — CI helper: writes API key to temp file that is immediately masked by workflow
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
