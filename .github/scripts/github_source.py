"""Read a GitHub repository or file link as plain text for quick-note context.

A GitHub repository page strips down to navigation chrome, so fetch_url.py's
HTML strategies returned too little and every fallback (Jina, Google Cache,
Wayback) failed too. Quick notes #1569 and #1570 were then *rejected* by the
architect pass without it ever having read the repositories.

This module skips the HTML entirely: repository metadata and the top-level
file list come from the GitHub REST API, the README and single files come from
raw.githubusercontent.com. Both hosts are fixed here; the only caller-supplied
parts are the owner/repo/ref/path segments, which are validated first.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
import urllib.parse
from typing import Callable

API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"

# GitHub owner / repo names: letters, digits, '-', '_', '.'.
_NAME = r"[A-Za-z0-9_.-]+"
_REPO_RE = re.compile(
    rf"^https?://(?:www\.)?github\.com/(?P<owner>{_NAME})/(?P<repo>{_NAME})"
    r"(?:/(?P<kind>tree|blob)/(?P<ref>[^/?#]+)(?:/(?P<path>[^?#]*))?)?/?(?:[?#].*)?$"
)
# Top-level paths on github.com that are not user/org names.
_RESERVED_OWNERS = {"orgs", "settings", "marketplace", "topics", "features", "sponsors"}

FetchText = Callable[[str], "str | None"]


def parse(url: str) -> dict | None:
    """Return owner/repo/kind/ref/path for a repository or file URL, else None.

    Issue, pull-request and Actions URLs return None so the caller falls back
    to its ordinary page strategies.
    """
    m = _REPO_RE.match(url.strip())
    if not m or m.group("owner").lower() in _RESERVED_OWNERS:
        return None
    parts = m.groupdict()
    parts["repo"] = parts["repo"].removesuffix(".git")
    if ".." in (parts.get("path") or "") or ".." in (parts.get("ref") or ""):
        return None
    return parts


def is_github_source(url: str) -> bool:
    return parse(url) is not None


def _q(segment: str) -> str:
    return urllib.parse.quote(segment, safe="/")


def _repo_summary(meta: dict) -> list[str]:
    lines = [f"Repository: {meta.get('full_name', '')}"]
    if meta.get("description"):
        lines.append(f"Description: {meta['description']}")
    if meta.get("topics"):
        lines.append("Topics: " + ", ".join(meta["topics"]))
    lic = (meta.get("license") or {}).get("spdx_id")
    lines.append(
        f"Language: {meta.get('language') or 'n/a'} · Stars: {meta.get('stargazers_count', 0)}"
        f" · License: {lic or 'none declared'}"
    )
    return lines


# README lines that carry no information for an architect: badge rows, bare
# images and centring wrappers. They cost a large slice of the 6000-char budget
# the context generator passes on (#1570's README spent ~800 chars on badges).
_NOISE_LINE = re.compile(r"^\s*(\[!\[|!\[|<img\b|<p align=|</p>|<a href=[^>]*>\s*<img)", re.I)


def _strip_readme_noise(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not _NOISE_LINE.match(line))


def _decode_readme(raw: str | None) -> str | None:
    """Body of a ``GET /repos/{o}/{r}/readme`` response, or None."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if data.get("encoding") != "base64":
            return None
        return base64.b64decode(data.get("content", "")).decode("utf-8", "replace") or None
    except (json.JSONDecodeError, AttributeError, binascii.Error, ValueError):
        return None


def _readme(owner: str, repo: str, ref: str, path: str, fetch_text: FetchText) -> str | None:
    """The README for ``path`` (repo root when empty), whatever its name.

    The API resolves any README spelling (README.markdown, docs/README.md,
    ...); guessing names on the raw host is the fallback when the API is
    rate-limited.
    """
    sub = f"/{_q(path)}" if path else ""
    readme = _decode_readme(fetch_text(f"{API}/repos/{owner}/{repo}/readme{sub}?ref={_q(ref)}"))
    if readme:
        return readme
    prefix = f"{_q(path)}/" if path else ""
    for name in ("README.md", "readme.md", "README.rst", "README"):
        readme = fetch_text(f"{RAW}/{owner}/{repo}/{_q(ref)}/{prefix}{name}")
        if readme:
            return readme
    return None


def fetch_github_source(url: str, fetch_text: FetchText) -> str:
    """Return a plain-text rendering of the linked repo or file ('' on failure).

    ``fetch_text(url) -> str | None`` performs the HTTP GET; it is injected so
    the caller controls headers/auth and tests need no network.
    """
    parts = parse(url)
    if parts is None:
        return ""
    owner, repo = _q(parts["owner"]), _q(parts["repo"])

    if parts["kind"] == "blob" and parts.get("path"):
        body = fetch_text(f"{RAW}/{owner}/{repo}/{_q(parts['ref'])}/{_q(parts['path'])}")
        if not body:
            return ""
        return f"File: {parts['owner']}/{parts['repo']}/{parts['path']}\n\n{body}"

    out: list[str] = []
    meta_raw = fetch_text(f"{API}/repos/{owner}/{repo}")
    ref = parts.get("ref") or "HEAD"
    if meta_raw:
        try:
            meta = json.loads(meta_raw)
            out += _repo_summary(meta)
            ref = parts.get("ref") or meta.get("default_branch") or "HEAD"
        except (json.JSONDecodeError, AttributeError):
            pass

    path = (parts.get("path") or "").strip("/")
    sub = f"/{_q(path)}" if path else ""
    listing_raw = fetch_text(f"{API}/repos/{owner}/{repo}/contents{sub}?ref={_q(ref)}")
    if listing_raw:
        try:
            entries = json.loads(listing_raw)
            names = [
                e["name"] + ("/" if e.get("type") == "dir" else "")
                for e in entries if isinstance(e, dict) and "name" in e
            ]
            if names:
                where = f"Files in {path}" if path else "Top-level files"
                out.append(f"{where}: " + ", ".join(sorted(names)))
        except (json.JSONDecodeError, TypeError):
            pass

    readme = _readme(owner, repo, ref, path, fetch_text)
    if readme:
        out += ["", "README:", _strip_readme_noise(readme)]
    # Metadata alone is not the source; without a README there is nothing to
    # ground a verdict in, so report failure and let other strategies try.
    return "\n".join(out) if readme else ""
