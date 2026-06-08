#!/usr/bin/env python3
"""Generate services/technologies.json — the website scanner's signature database.

Source of truth is the Wappalyzer fingerprint dataset bundled with the
`python-Wappalyzer` package (a snapshot of the open-source Wappalyzer technology
definitions). We convert it into the compact schema that
`WebsiteScanner._detect_systems_generic` consumes:

    {
      "categories": { "<id>": "<name>", ... },
      "apps": {
        "<TechName>": {
          "cats":    [<category id>, ...],
          "headers": { "<Header>": "<regex>", ... },   # optional
          "cookies": { "<Cookie>": "<regex>", ... },   # optional
          "html":    ["<regex>", ...],                  # html + scriptSrc + scripts merged
          "meta":    { "<name>": "<regex>", ... },      # optional
          "implies": ["<TechName>", ...]                # optional
        }, ...
      }
    }

`scriptSrc`/`scripts` URL patterns go to a separate `scriptSrc` field (matched
against extracted <script src> URLs, not the whole document). `js`/`dom` signals
require a live JS runtime / rendered DOM and are only used by the optional render
pass (services/scanner_render.py); the static converter omits them.

Wappalyzer appends metadata tags to patterns using a backslash-semicolon
delimiter (e.g. `jquery.*\.js\;confidence:50\;version:\1`). We strip everything
from the first `\;` so the stored value is a plain regex.

Usage:
    pip install python-Wappalyzer        # provides the source dataset
    python scripts/build_tech_db.py      # writes services/technologies.json
    python scripts/build_tech_db.py --source /path/to/technologies.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(REPO_ROOT, "services", "technologies.json")

# Map Wappalyzer category names (lowercased) to this repo's SystemType literal
# (see models.company_graph.SystemType). Anything unmapped becomes "custom".
SYSTEMTYPE_MAP = {
    "cms": "CMS",
    "blogs": "CMS",
    "wikis": "CMS",
    "documentation": "CMS",
    "editors": "CMS",
    "rich text editors": "CMS",
    "page builders": "CMS",
    "static site generator": "CMS",
    "ecommerce": "OMS",
    "payment processors": "payment_gateway",
    "buy now pay later": "payment_gateway",
    "accounting": "billing",
    "analytics": "analytics",
    "a/b testing": "analytics",
    "tag managers": "analytics",
    "marketing automation": "marketing_automation",
    "advertising": "marketing_automation",
    "retargeting": "marketing_automation",
    "email": "email_service",
    "webmail": "email_service",
    "databases": "database",
    "database managers": "database",
    "caching": "cache",
    "search engines": "search",
    "site search": "search",
    "crm": "CRM",
    "customer data platform": "CRM",
    "lms": "LMS",
    "issue trackers": "support",
    "helpdesk": "support",
    "message boards": "support",
    "live chat": "chat",
    "video players": "video",
    "media servers": "video",
    "authentication": "auth",
    "iot": "iot",
    "shipping carriers": "shipping",
}


def _system_type(category_name: str) -> str:
    return SYSTEMTYPE_MAP.get(str(category_name).strip().lower(), "custom")


# Curated signatures preserved from the previous hand-tuned scanner DB. The Wappalyzer
# snapshot is missing some of these (Datadog/Klarna/Klaviyo) or carries them without any
# matchable pattern (Adyen). Each entry declares an explicit SystemType via "type".
# Merged in only where the upstream dataset lacks a usable signature, so it never weakens
# richer upstream entries.
CURATED_OVERLAY: Dict[str, Dict[str, Any]] = {
    "Adyen": {"type": "payment_gateway", "html": "checkoutshopper-[a-z]+\\.adyen\\.com"},
    "Akamai": {"type": "custom", "headers": {"X-Akamai-Transformed": ".*", "X-Cache": ".*Akamai.*"}},
    "Algolia": {"type": "search", "html": "algoliasearch"},
    "Contentful": {"type": "CMS", "html": "images\\.ctfassets\\.net"},
    "Datadog": {"type": "analytics", "html": "datadog-rum-[a-z0-9]+\\.js"},
    "Intercom": {"type": "support", "html": "widget\\.intercom\\.io"},
    "Klarna": {"type": "payment_gateway", "html": "js\\.klarna\\.com"},
    "Klaviyo": {"type": "marketing_automation", "html": "static\\.klaviyo\\.com"},
    "Mixpanel": {"type": "analytics", "html": "cdn\\.mxpnl\\.com"},
    "Segment": {"type": "analytics", "html": "cdn\\.segment\\.com"},
    "Zendesk": {"type": "support", "html": "static\\.zdassets\\.com"},
}

_PATTERN_KEYS = ("html", "headers", "cookies", "meta", "scriptSrc")


def _has_pattern(spec: Dict[str, Any]) -> bool:
    return any(spec.get(k) for k in _PATTERN_KEYS)


def _default_source() -> str | None:
    try:
        import Wappalyzer  # type: ignore

        path = os.path.join(os.path.dirname(Wappalyzer.__file__), "data", "technologies.json")
        return path if os.path.exists(path) else None
    except Exception:
        return None


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _clean(pattern: Any) -> str:
    """Strip Wappalyzer's `\\;tag:...` metadata, leaving a plain regex."""
    return str(pattern).split("\\;")[0]


def convert(source: Dict[str, Any]) -> Dict[str, Any]:
    raw_categories = source.get("categories", {})
    # Store each category id as the repo SystemType it maps to, so the scanner can
    # emit a meaningful system_type (analytics, payment_gateway, …) rather than "custom".
    categories = {
        str(cid): _system_type(cat.get("name") if isinstance(cat, dict) else cat)
        for cid, cat in raw_categories.items()
    }

    technologies = source.get("technologies") or source.get("apps") or {}
    apps: Dict[str, Any] = {}
    for name, spec in technologies.items():
        out: Dict[str, Any] = {"cats": spec.get("cats", [1])}

        if spec.get("headers"):
            out["headers"] = {k: _clean(v) for k, v in spec["headers"].items()}
        if spec.get("cookies"):
            out["cookies"] = {k: _clean(v) for k, v in spec["cookies"].items()}

        # `html` patterns match against the page body / inline markup.
        html_patterns = [p for p in (_clean(p) for p in _as_list(spec.get("html"))) if p]
        if html_patterns:
            out["html"] = html_patterns

        # `scriptSrc` and `scripts` are URL patterns (often anchored, e.g. ^https?://…)
        # and must be matched against extracted <script src> URLs, not the whole document.
        script_src = [
            p for p in (_clean(p) for p in (_as_list(spec.get("scriptSrc")) + _as_list(spec.get("scripts")))) if p
        ]
        if script_src:
            out["scriptSrc"] = script_src

        if spec.get("meta"):
            meta = {}
            for m_name, m_val in spec["meta"].items():
                vals = _as_list(m_val)
                if vals:
                    meta[m_name] = _clean(vals[0])
            if meta:
                out["meta"] = meta

        if spec.get("implies"):
            out["implies"] = [_clean(p) for p in _as_list(spec["implies"])]

        apps[name] = out

    # Fill gaps with curated signatures where upstream is missing or pattern-less.
    for name, entry in CURATED_OVERLAY.items():
        if name not in apps or not _has_pattern(apps[name]):
            apps[name] = dict(entry)

    return {"categories": categories, "apps": apps}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=None, help="Path to a Wappalyzer technologies.json")
    parser.add_argument("--output", default=OUTPUT, help="Where to write the converted database")
    args = parser.parse_args()

    source_path = args.source or _default_source()
    if not source_path or not os.path.exists(source_path):
        print(
            "error: could not find a Wappalyzer dataset.\n"
            "Install it with `pip install python-Wappalyzer`, or pass --source <path>.",
            file=sys.stderr,
        )
        return 1

    with open(source_path, "r", encoding="utf-8") as f:
        source = json.load(f)

    converted = convert(source)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(converted, f, separators=(",", ":"), sort_keys=True)
        f.write("\n")

    print(
        f"wrote {args.output}: {len(converted['apps'])} technologies, "
        f"{len(converted['categories'])} categories (source: {source_path})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
