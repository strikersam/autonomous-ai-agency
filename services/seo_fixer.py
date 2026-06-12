"""
services/seo_fixer.py - Repo-Aware SEO Auto-Fixer

When a company has a code repository available, this service remediates the
auto-fixable findings from a SEO audit directly in the repo checkout:

- HTML hygiene: meta charset, viewport, lang attribute, meta description,
  canonical link, Open Graph + Twitter card tags
- Image fixes: alt attributes (humanized from the filename), width/height
  size attributes (measured with Pillow when the image file exists locally)
- Link hygiene: rel="noopener" on target="_blank", protocol-relative -> https
- GEO files: robots.txt, sitemap.xml, llms.txt generation
- Security headers: ready-to-apply config suggestions for the platform
  detected in the repo (netlify.toml / vercel.json / generic)

All edits are *targeted text edits* (regex-scoped insertions and attribute
rewrites) rather than full DOM re-serialization, so diffs stay minimal and
the original formatting is preserved.

Default mode is a dry run that returns unified diffs; pass ``apply=True``
to write changes to disk. The caller is responsible for restricting
``repo_path`` to a safe workspace root (the API layer enforces this).
"""

from __future__ import annotations

import difflib
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from models.seo_audit import SeoFixAction, SeoFixRequest, SeoFixResult

log = logging.getLogger("seo_fixer")

# Directories never scanned for fixable files.
_SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "out", ".next", ".nuxt",
    "vendor", "__pycache__", ".venv", "venv", "coverage", ".cache",
}
_HTML_SUFFIXES = {".html", ".htm"}
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif"}

_HEAD_OPEN_RE = re.compile(r"<head[^>]*>", re.IGNORECASE)
_HEAD_CLOSE_RE = re.compile(r"</head>", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<html(?P<attrs>[^>]*)>", re.IGNORECASE)
_IMG_TAG_RE = re.compile(r"<img\b[^>]*?/?>", re.IGNORECASE | re.DOTALL)
_A_BLANK_RE = re.compile(r"<a\b[^>]*target\s*=\s*([\"'])_blank\1[^>]*>", re.IGNORECASE | re.DOTALL)
_PROTOCOL_RELATIVE_RE = re.compile(r"(\b(?:src|href)\s*=\s*)([\"'])//", re.IGNORECASE)


def _humanize_filename(src: str) -> str:
    """Derive readable alt text from an image path: 'img/hero-banner_2.jpg' -> 'Hero banner 2'."""
    name = Path(src.split("?")[0]).stem
    words = re.sub(r"[-_]+", " ", name).strip()
    words = re.sub(r"\s+", " ", words)
    return words[:1].upper() + words[1:] if words else "Image"


def _unified_diff(before: str, after: str, rel_path: str) -> str:
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"a/{rel_path}",
        tofile=f"b/{rel_path}",
    ))


class SeoFixer:
    """Applies (or proposes) automatic SEO remediations inside a repo checkout."""

    def __init__(self, request: SeoFixRequest) -> None:
        self.request = request
        self.repo = Path(request.repo_path).resolve()
        self.base_url = request.base_url.rstrip("/")
        self.actions: List[SeoFixAction] = []
        self._wanted = set(request.include_checks)

    # ------------------------------------------------------------------
    # public entry point
    # ------------------------------------------------------------------

    def run(self) -> SeoFixResult:
        """Scan the repo, fix every enabled auto-fixable problem found."""
        if not self.repo.is_dir():
            return SeoFixResult(
                repo_path=str(self.repo), audit_id=self.request.audit_id,
                dry_run=not self.request.apply,
                summary=f"Repository path does not exist: {self.repo}",
            )

        html_files = self._find_html_files()
        for path in html_files:
            try:
                self._fix_html_file(path)
            except Exception as exc:  # noqa: BLE001 - one bad file must not stop the run
                log.warning("SEO fixer skipped %s: %s", path, exc)

        self._fix_site_files(html_files)
        self._suggest_security_headers()

        modified = sum(1 for a in self.actions if a.action == "modified")
        created = sum(1 for a in self.actions if a.action == "created")
        suggested = sum(1 for a in self.actions if a.action == "suggested")
        mode = "applied" if self.request.apply else "proposed (dry run)"
        return SeoFixResult(
            repo_path=str(self.repo),
            audit_id=self.request.audit_id,
            dry_run=not self.request.apply,
            files_scanned=len(html_files),
            files_modified=modified,
            files_created=created,
            suggestions=suggested,
            actions=self.actions,
            summary=(
                f"Scanned {len(html_files)} HTML file(s); {mode} "
                f"{modified} modification(s), {created} new file(s), "
                f"{suggested} suggestion(s)."
            ),
        )

    # ------------------------------------------------------------------
    # discovery
    # ------------------------------------------------------------------

    def _enabled(self, check_code: str) -> bool:
        return not self._wanted or check_code in self._wanted

    def _find_html_files(self) -> List[Path]:
        files: List[Path] = []
        # os.walk with in-place dirnames pruning so we never descend into
        # .git/node_modules/dist on large repos (rglob would walk them first).
        for dirpath, dirnames, filenames in os.walk(self.repo):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for filename in filenames:
                path = Path(dirpath) / filename
                if path.suffix.lower() in _HTML_SUFFIXES:
                    files.append(path)
        files.sort()
        return files

    def _record(
        self,
        check_code: str,
        path: Path,
        action: str,
        description: str,
        diff: str,
        new_content: Optional[str] = None,
    ) -> None:
        rel = str(path.relative_to(self.repo)) if path.is_absolute() else str(path)
        applied = False
        if self.request.apply and action in ("modified", "created") and new_content is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(new_content, encoding="utf-8")
            applied = True
        self.actions.append(SeoFixAction(
            check_code=check_code, file_path=rel,
            action=action,  # type: ignore[arg-type]
            description=description, diff=diff, applied=applied,
        ))

    # ------------------------------------------------------------------
    # per-file HTML fixes
    # ------------------------------------------------------------------

    def _fix_html_file(self, path: Path) -> None:
        original = path.read_text(encoding="utf-8", errors="replace")
        content = original
        rel = str(path.relative_to(self.repo))
        soup = BeautifulSoup(original, "lxml")
        descriptions: List[str] = []
        fired: List[str] = []

        head_open = _HEAD_OPEN_RE.search(content)
        head_close = _HEAD_CLOSE_RE.search(content)
        title = (soup.title.get_text().strip() if soup.title else "") or _humanize_filename(rel)

        def insert_in_head(snippet: str, at_start: bool = False) -> bool:
            nonlocal content
            m_open = _HEAD_OPEN_RE.search(content)
            m_close = _HEAD_CLOSE_RE.search(content)
            if at_start and m_open:
                pos = m_open.end()
            elif m_close:
                pos = m_close.start()
            else:
                return False
            content = content[:pos] + snippet + content[pos:]
            return True

        has_head = bool(head_open and head_close)

        # charset
        if (self._enabled("validation_missing_charset") and has_head
                and not soup.find("meta", charset=True)
                and not soup.find("meta", attrs={"http-equiv": re.compile("^content-type$", re.I)})):
            if insert_in_head('\n    <meta charset="utf-8">', at_start=True):
                fired.append("validation_missing_charset")
                descriptions.append("added <meta charset>")

        # viewport
        if (self._enabled("validation_missing_viewport") and has_head
                and not soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)})):
            if insert_in_head('\n    <meta name="viewport" content="width=device-width, initial-scale=1">'):
                fired.append("validation_missing_viewport")
                descriptions.append("added viewport meta tag")

        # lang attribute
        if self._enabled("validation_missing_lang"):
            html_tag = soup.find("html")
            if html_tag is not None and not (html_tag.get("lang") or "").strip():
                m = _HTML_TAG_RE.search(content)
                if m and "lang=" not in m.group("attrs").lower():
                    content = (
                        content[:m.start()]
                        + f'<html lang="{self.request.default_lang}"{m.group("attrs")}>'
                        + content[m.end():]
                    )
                    fired.append("validation_missing_lang")
                    descriptions.append(f'added lang="{self.request.default_lang}"')

        # meta description derived from the first substantial paragraph
        description_text = ""
        if (self._enabled("meta_desc_missing") and has_head
                and not soup.find("meta", attrs={"name": re.compile("^description$", re.I)})):
            description_text = self._derive_description(soup)
            if description_text:
                escaped = description_text.replace('"', "&quot;")
                if insert_in_head(f'\n    <meta name="description" content="{escaped}">'):
                    fired.append("meta_desc_missing")
                    descriptions.append("added meta description derived from page copy")

        # canonical (requires base_url to build an absolute URL)
        if (self._enabled("canonical_missing") and has_head and self.base_url
                and not soup.find("link", rel=lambda v: v and "canonical" in v)):
            canonical_url = self._canonical_url_for(rel)
            if insert_in_head(f'\n    <link rel="canonical" href="{canonical_url}">'):
                fired.append("canonical_missing")
                descriptions.append(f"added canonical link {canonical_url}")

        # Open Graph
        if (self._enabled("social_missing_open_graph") and has_head
                and not soup.find("meta", property=re.compile("^og:", re.I))):
            og_desc = description_text or self._derive_description(soup)
            snippet = (
                f'\n    <meta property="og:type" content="website">'
                f'\n    <meta property="og:title" content="{title.replace(chr(34), "&quot;")}">'
            )
            if og_desc:
                snippet += f'\n    <meta property="og:description" content="{og_desc.replace(chr(34), "&quot;")}">'
            if self.base_url:
                snippet += f'\n    <meta property="og:url" content="{self._canonical_url_for(rel)}">'
            if insert_in_head(snippet):
                fired.append("social_missing_open_graph")
                descriptions.append("added Open Graph tags")

        # Twitter card
        if (self._enabled("social_missing_twitter_card") and has_head
                and not soup.find("meta", attrs={"name": re.compile("^twitter:card$", re.I)})):
            if insert_in_head('\n    <meta name="twitter:card" content="summary_large_image">'):
                fired.append("social_missing_twitter_card")
                descriptions.append("added twitter:card meta tag")

        # rel="noopener" on target="_blank"
        if self._enabled("security_unsafe_cross_origin_links"):
            content, count = self._add_noopener(content)
            if count:
                fired.append("security_unsafe_cross_origin_links")
                descriptions.append(f'added rel="noopener" to {count} target="_blank" link(s)')

        # protocol-relative resources -> https
        if self._enabled("security_protocol_relative_resources"):
            content, count = _PROTOCOL_RELATIVE_RE.subn(r"\1\2https://", content)
            if count:
                fired.append("security_protocol_relative_resources")
                descriptions.append(f"rewrote {count} protocol-relative URL(s) to https")

        # image alt + size + lazy-loading attributes
        if (self._enabled("image_missing_alt_attribute")
                or self._enabled("image_missing_size_attributes")
                or self._enabled("image_not_lazy_loaded")):
            content, alt_count, size_count, lazy_count = self._fix_images(content, path)
            if alt_count:
                fired.append("image_missing_alt_attribute")
                descriptions.append(f"added alt text to {alt_count} image(s)")
            if size_count:
                fired.append("image_missing_size_attributes")
                descriptions.append(f"added width/height to {size_count} image(s)")
            if lazy_count:
                fired.append("image_not_lazy_loaded")
                descriptions.append(f'added loading="lazy" to {lazy_count} below-the-fold image(s)')

        if content != original:
            diff = _unified_diff(original, content, rel)
            self._record(
                fired[0] if len(fired) == 1 else "multiple",
                path, "modified", "; ".join(descriptions), diff, new_content=content,
            )

    def _derive_description(self, soup: BeautifulSoup) -> str:
        for p in soup.find_all("p"):
            text = " ".join(p.get_text(" ").split())
            if len(text) >= 50:
                if len(text) > 155:
                    text = text[:152].rsplit(" ", 1)[0] + "..."
                return text
        return ""

    def _canonical_url_for(self, rel_path: str) -> str:
        slug = rel_path.replace("\\", "/")
        if slug.endswith("index.html"):
            slug = slug[: -len("index.html")]
        return f"{self.base_url}/{slug}".rstrip("/") or self.base_url

    @staticmethod
    def _add_noopener(content: str) -> Tuple[str, int]:
        count = 0

        def repl(m: re.Match[str]) -> str:
            nonlocal count
            tag = m.group(0)
            rel_match = re.search(r"rel\s*=\s*([\"'])(.*?)\1", tag, re.IGNORECASE)
            if rel_match:
                if re.search(r"\bnoopener\b|\bnoreferrer\b", rel_match.group(2), re.IGNORECASE):
                    return tag
                count += 1
                return tag.replace(
                    rel_match.group(0),
                    f'rel={rel_match.group(1)}{rel_match.group(2)} noopener{rel_match.group(1)}',
                    1,
                )
            count += 1
            return tag[:-1] + ' rel="noopener">'

        return _A_BLANK_RE.sub(repl, content), count

    def _fix_images(self, content: str, html_path: Path) -> Tuple[str, int, int, int]:
        alt_count = 0
        size_count = 0
        lazy_count = 0
        img_index = 0
        fix_alt = self._enabled("image_missing_alt_attribute")
        fix_size = self._enabled("image_missing_size_attributes")
        fix_lazy = self._enabled("image_not_lazy_loaded")

        def repl(m: re.Match[str]) -> str:
            nonlocal alt_count, size_count, lazy_count, img_index
            img_index += 1
            tag = m.group(0)
            src_match = re.search(r"src\s*=\s*([\"'])(.*?)\1", tag, re.IGNORECASE)
            src = src_match.group(2) if src_match else ""
            closing = " />" if tag.rstrip().endswith("/>") else ">"
            body = tag[: -len(closing)] if tag.endswith(closing) else tag[:-1]

            additions = ""
            if fix_alt and not re.search(r"\balt\s*=", tag, re.IGNORECASE) and src:
                additions += f' alt="{_humanize_filename(src)}"'
                alt_count += 1
            if (fix_size and src and not src.startswith(("http:", "https:", "//", "data:"))
                    and not re.search(r"\bwidth\s*=", tag, re.IGNORECASE)):
                dims = self._measure_image(html_path, src)
                if dims:
                    additions += f' width="{dims[0]}" height="{dims[1]}"'
                    size_count += 1
            # The first image is treated as the LCP/hero candidate and kept eager.
            if (fix_lazy and img_index > 1
                    and not re.search(r"\bloading\s*=", tag, re.IGNORECASE)):
                additions += ' loading="lazy"'
                lazy_count += 1
            if not additions:
                return tag
            return body + additions + closing

        return _IMG_TAG_RE.sub(repl, content), alt_count, size_count, lazy_count

    def _measure_image(self, html_path: Path, src: str) -> Optional[Tuple[int, int]]:
        raw_src = src.split("?")[0]
        # Site-absolute srcs ("/img/x.png") are rooted at the repo; relative
        # srcs resolve against the page's own directory.
        if raw_src.startswith("/"):
            candidate = (self.repo / raw_src.lstrip("/")).resolve()
        else:
            candidate = (html_path.parent / raw_src).resolve()
        # Path-aware containment check (str.startswith would accept sibling
        # directories like /repo-copy when the repo is /repo).
        try:
            candidate.relative_to(self.repo)
        except ValueError:
            return None
        if candidate.suffix.lower() not in _IMAGE_SUFFIXES or not candidate.is_file():
            return None
        try:
            from PIL import Image

            with Image.open(candidate) as img:
                return int(img.width), int(img.height)
        except Exception as exc:  # noqa: BLE001 - measurement is best-effort
            log.warning("Could not measure image %s (from %s): %s",
                        candidate, html_path, exc)
            return None

    # ------------------------------------------------------------------
    # site-level file generation (GEO)
    # ------------------------------------------------------------------

    def _fix_site_files(self, html_files: List[Path]) -> None:
        site_name = self.request.site_name or (self.base_url or str(self.repo.name))

        # robots.txt
        robots_path = self.repo / "robots.txt"
        if self._enabled("geo_missing_robots_txt") and not robots_path.exists():
            sitemap_line = f"Sitemap: {self.base_url}/sitemap.xml\n" if self.base_url else ""
            body = "User-agent: *\nAllow: /\n\n" + sitemap_line
            self._record("geo_missing_robots_txt", robots_path, "created",
                         "generated robots.txt allowing all crawlers and declaring the sitemap",
                         body, new_content=body)
        elif self._enabled("geo_sitemap_not_in_robots") and robots_path.exists() and self.base_url:
            existing = robots_path.read_text(encoding="utf-8", errors="replace")
            if "sitemap:" not in existing.lower():
                updated = existing.rstrip("\n") + f"\n\nSitemap: {self.base_url}/sitemap.xml\n"
                self._record("geo_sitemap_not_in_robots", robots_path, "modified",
                             "declared sitemap.xml in robots.txt",
                             _unified_diff(existing, updated, "robots.txt"),
                             new_content=updated)

        # sitemap.xml from the repo's HTML pages
        sitemap_path = self.repo / "sitemap.xml"
        if (self._enabled("geo_missing_sitemap") and not sitemap_path.exists()
                and self.base_url and html_files):
            today = datetime.now(timezone.utc).date().isoformat()
            urls = []
            for f in html_files:
                rel = str(f.relative_to(self.repo)).replace("\\", "/")
                if rel.endswith("index.html"):
                    rel = rel[: -len("index.html")]
                loc = f"{self.base_url}/{rel}".rstrip("/") or self.base_url
                urls.append(
                    f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{today}</lastmod>\n  </url>"
                )
            body = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + "\n".join(urls) + "\n</urlset>\n"
            )
            self._record("geo_missing_sitemap", sitemap_path, "created",
                         f"generated sitemap.xml with {len(urls)} URL(s)", body,
                         new_content=body)

        # llms.txt (GEO discoverability for AI agents)
        llms_path = self.repo / "llms.txt"
        if self._enabled("geo_missing_llms_txt") and not llms_path.exists():
            links = []
            for f in html_files[:20]:
                rel = str(f.relative_to(self.repo)).replace("\\", "/")
                label = _humanize_filename(rel)
                loc = f"{self.base_url}/{rel}" if self.base_url else f"/{rel}"
                links.append(f"- [{label}]({loc})")
            body = (
                f"# {site_name}\n\n"
                "> Concise, AI-readable map of this site's most important content.\n\n"
                "## Pages\n\n" + "\n".join(links) + "\n"
            )
            self._record("geo_missing_llms_txt", llms_path, "created",
                         "generated llms.txt content map for AI crawlers", body,
                         new_content=body)

    # ------------------------------------------------------------------
    # security header suggestions (platform-aware)
    # ------------------------------------------------------------------

    _SECURITY_HEADERS: Dict[str, str] = {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'; img-src 'self' data: https:; "
                                   "script-src 'self'; style-src 'self' 'unsafe-inline'",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }

    def _suggest_security_headers(self) -> None:
        header_checks = {
            "Strict-Transport-Security": "security_missing_hsts",
            "Content-Security-Policy": "security_missing_csp",
            "X-Content-Type-Options": "security_missing_x_content_type_options",
            "X-Frame-Options": "security_missing_x_frame_options",
            "Referrer-Policy": "security_missing_referrer_policy",
        }
        enabled = [(header, code) for header, code in header_checks.items()
                   if self._enabled(code)]
        if not enabled:
            return

        if (self.repo / "netlify.toml").exists():
            target, snippet = "netlify.toml", self._netlify_headers_snippet()
        elif (self.repo / "vercel.json").exists():
            target, snippet = "vercel.json", self._vercel_headers_snippet()
        elif (self.repo / "wrangler.jsonc").exists() or (self.repo / "wrangler.toml").exists():
            target, snippet = "_headers", self._headers_file_snippet()
        else:
            target, snippet = "security-headers (server config)", self._headers_file_snippet()

        # One suggestion per enabled check so SeoFixAction.check_code stays
        # accurate for include_checks filtering and downstream consumers.
        for header, code in enabled:
            self._record(
                code, Path(target), "suggested",
                f"Set the {header} header on all responses (snippet covers the "
                "full recommended set for the detected hosting platform). "
                "Review the CSP policy against the site's actual resource "
                "origins before applying.",
                snippet,
            )

    def _netlify_headers_snippet(self) -> str:
        lines = ['[[headers]]', '  for = "/*"', "  [headers.values]"]
        for k, v in self._SECURITY_HEADERS.items():
            lines.append(f'    {k} = "{v}"')
        return "\n".join(lines) + "\n"

    def _vercel_headers_snippet(self) -> str:
        import json as _json

        return _json.dumps({
            "headers": [{
                "source": "/(.*)",
                "headers": [{"key": k, "value": v} for k, v in self._SECURITY_HEADERS.items()],
            }]
        }, indent=2) + "\n"

    def _headers_file_snippet(self) -> str:
        lines = ["/*"]
        for k, v in self._SECURITY_HEADERS.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines) + "\n"


def run_fixes(request: SeoFixRequest) -> SeoFixResult:
    """Convenience wrapper used by the API layer and skill executor."""
    return SeoFixer(request).run()
