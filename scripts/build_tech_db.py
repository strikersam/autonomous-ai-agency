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

We intentionally drop `js` and `dom` signals: they require a live JS runtime /
rendered DOM, which the server-side scanner does not have. `scriptSrc`/`scripts`
patterns are folded into `html` because they match against the raw page text.

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
    categories = {
        str(cid): (cat.get("name") if isinstance(cat, dict) else str(cat))
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

        html_patterns: List[str] = []
        for key in ("html", "scriptSrc", "scripts"):
            html_patterns.extend(_clean(p) for p in _as_list(spec.get(key)))
        html_patterns = [p for p in html_patterns if p]
        if html_patterns:
            out["html"] = html_patterns

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
