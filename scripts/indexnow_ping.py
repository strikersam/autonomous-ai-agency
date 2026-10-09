#!/usr/bin/env python3
"""Tell IndexNow search engines (Bing, Yandex, Seznam, Naver) that public URLs changed.

Run after a deploy that changes the landing page:  python scripts/indexnow_ping.py
The key is public by design: it is the filename of the one `<key>.txt` file in
frontend/public/, which proves to the engines that we own the host.
"""
from __future__ import annotations

import json
import logging
import sys
import urllib.request
from pathlib import Path

log = logging.getLogger("qwen-proxy")

HOST = "autonomous-ai-agency.strikersam.workers.dev"
PUBLIC = Path(__file__).resolve().parent.parent / "frontend" / "public"
ENDPOINT = "https://api.indexnow.org/indexnow"
URLS = [f"https://{HOST}/"]


def find_key() -> str:
    """Return the IndexNow key: the stem of the single 32-hex `.txt` file in public/."""
    keys = [p.stem for p in PUBLIC.glob("*.txt")
            if len(p.stem) == 32 and p.read_text(encoding="utf-8").strip() == p.stem]
    if len(keys) != 1:
        raise SystemExit(f"expected exactly one IndexNow key file in {PUBLIC}, found {len(keys)}")
    return keys[0]


def main() -> int:
    """POST the URL list to IndexNow and return a process exit code."""
    key = find_key()
    body = json.dumps({"host": HOST, "key": key, "keyLocation": f"https://{HOST}/{key}.txt",
                       "urlList": URLS}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:  # fixed https endpoint, not user-influenced
        log.warning("IndexNow responded %s (200/202 = accepted)", resp.status)
        return 0 if resp.status in (200, 202) else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
