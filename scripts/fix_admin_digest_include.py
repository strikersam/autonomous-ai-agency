#!/usr/bin/env python3
"""scripts/fix_admin_digest_include.py — byte-exact include_router inserter.

Previous str_replace attempts on backend/server.py failed with
"old string not found" despite the line existing. Root cause
suspected: a single non-printable char (CRLF, NBSP, or escaped
quote) in the file that the str_replace tool does not normalize.
This script does the byte-exact replacement using pathlib +
str.replace on the raw decoded text, retrying with a few
common variants.

Idempotent: if the constant `_register_admin_digest_router`
is already present, the script exits 0 with a no-op message.
"""
from __future__ import annotations

import sys
from pathlib import Path

PATH = Path("backend/server.py")

NEW_BLOCK = """
# Admin router: service-to-service digest endpoint (X-Admin-Secret auth)
try:
    from backend.admin_digest_router import register as _register_admin_digest_router
    _register_admin_digest_router(app)
except Exception as _admin_digest_err:  # noqa: BLE001
    log.warning("admin digest router not mounted: %s", _admin_digest_err, exc_info=True)
"""

ANCHOR_VARIANTS: tuple[str, ...] = (
    # Plain LF, 4-space indent on the inner warning
    (
        '    log.warning("SEO audit API not mounted: %s", _seo_err, exc_info=True)'
    ),
    # CRLF on the inner warning line (file might be Windows-line-ending)
    (
        '    log.warning("SEO audit API not mounted: %s", _seo_err, exc_info=True)\r'
    ),
    # Surrounding multi-line context (most likely to be unique on disk)
    (
        '    app.include_router(seo_api_module.router)\n'
        'except Exception as _seo_err:  # noqa: BLE001 - SEO API must not block startup\n'
        '    log.warning("SEO audit API not mounted: %s", _seo_err, exc_info=True)'
    ),
    (
        '    app.include_router(seo_api_module.router)\r\n'
        'except Exception as _seo_err:  # noqa: BLE001 - SEO API must not block startup\r\n'
        '    log.warning("SEO audit API not mounted: %s", _seo_err, exc_info=True)'
    ),
)


def main() -> int:
    src = PATH.read_text(encoding="utf-8", newline="")

    if "_register_admin_digest_router" in src:
        print("OK: include_router already present — no-op")
        return 0

    for i, anchor in enumerate(ANCHOR_VARIANTS, 1):
        if anchor in src:
            new_src = src.replace(anchor, anchor + NEW_BLOCK, 1)
            PATH.write_text(new_src, encoding="utf-8", newline="")
            print(f"OK: applied with anchor variant #{i}")
            print(f"  matched-bytes: {len(anchor)}")
            return 0

    print("ERROR: no anchor variant matched. Print diagnostic:", file=sys.stderr)
    for j, line in enumerate(src.splitlines(), 1):
        if 7210 <= j <= 7235:
            print(f"  LINENO {j}: {line!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
