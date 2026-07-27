from __future__ import annotations

"""
Multi-strategy URL content fetcher for process-quick-note workflow.

Exit codes:
  0 — success, content written to /tmp/note_content.txt
  2 — all strategies exhausted, URL inaccessible
  1 — bad args / unexpected error
"""


import re
import sys
import urllib.parse
import urllib.request

TARGET = sys.argv[1] if len(sys.argv) > 1 else ""
OUT_FILE = "/tmp/note_content.txt"  # nosec: B108
MIN_CHARS = 500

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch(url: str, timeout: int = 30) -> tuple[str | None, str, object]:
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return None, url, f"unsupported scheme: {parsed.scheme}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec: B310
            return r.read().decode("utf-8", errors="replace"), r.geturl(), r.status
    except Exception as exc:
        return None, url, str(exc)


def strip_html(html: str) -> str:
    # Use an HTML parser for tag stripping instead of regex to avoid ReDoS
    try:
        from html.parser import HTMLParser
        class _TagStripper(HTMLParser):
            def __init__(self):
                super().__init__()
                self._parts = []
                self._skip_tags = {"script", "style", "nav", "footer", "header"}
                self._skip_depth = 0
                self._skip_tag = None
            def handle_starttag(self, tag, attrs):
                if tag in self._skip_tags:
                    self._skip_depth += 1
                    self._skip_tag = tag
                else:
                    self._parts.append(" ")
            def handle_endtag(self, tag):
                if self._skip_tag == tag and self._skip_depth > 0:
                    self._skip_depth -= 1
                    if self._skip_depth == 0:
                        self._skip_tag = None
                else:
                    self._parts.append(" ")
            def handle_data(self, data):
                if self._skip_depth == 0:
                    self._parts.append(data)
            def get_text(self):
                return "".join(self._parts)
        stripper = _TagStripper()
        stripper.feed(html)
        text = stripper.get_text()
    except Exception:
        text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"[ \t]+", " ", text)
    # Boilerplate is removed before the length check so a page that is nothing
    # but navigation fails `meaningful()` and falls through to the next strategy.
    return strip_boilerplate(text)


def extract_real_url(html: str) -> str | None:
    for pat in [
        r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:url["\']',
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
        r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\'][^;]+;\s*url=([^"\']+)["\']',
    ]:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if candidate.startswith("http"):
                return candidate
    return None


#: Site chrome that survives tag-stripping because it does not live in
#: script/style/nav/footer/header tags. Matched case-insensitively against a
#: whole stripped line, so it can never truncate a line of real prose.
CHROME_LINES = {
    "skip to content", "sign in", "sign up", "search", "search gists",
    "search code, repositories, users, issues, pull requests...",
    "dismiss alert", "{{ message }}", "toggle navigation", "menu", "close",
    "you must be signed in to star a gist", "you must be signed in to fork a gist",
    "show gist options", "download zip", "star", "fork", "embed", "share",
    "select an option", "raw", "no results found", "learn more about clone urls",
    "clone via https", "clone using the web url", "instantly share code, notes, and snippets",
    "embed this gist in your website", "copy sharable link for this gist",
    "cookie preferences", "terms", "privacy", "about", "blog", "contact github",
    "reload to refresh your session", "created", "footer",
}

#: Prefixes whose whole line is chrome regardless of the trailing text.
CHROME_PREFIXES = (
    "you signed in with another tab",
    "you signed out in another tab",
    "you switched accounts on another tab",
    "clone this repository at",
    "save ",
)

#: Only short lines are eligible for de-duplication. Real prose repeating
#: verbatim at this length is vanishingly rare; nav blocks repeat constantly.
MAX_DEDUPE_LINE = 120


def strip_boilerplate(text: str) -> str:
    """Drop site navigation chrome and repeated nav blocks from stripped text.

    A fetch is capped at 6000 chars before it reaches the LLM. On a GitHub gist
    roughly a quarter of that budget was nav furniture ("Sign in", "You must be
    signed in to star a gist", the embed block rendered twice), which pushed the
    actual article out of the window and left the model planning from the title.

    Conservative by construction: a line is removed only on an exact match
    against the chrome list, a known chrome prefix, or as the second-or-later
    occurrence of a short duplicate line. Long-form content is never touched.
    """
    seen: dict[str, int] = {}
    kept: list[str] = []
    for line in text.splitlines():
        # Sites render nav labels with non-breaking spaces ("Sign\xa0in"), which
        # would defeat an exact match, so normalise every Unicode space first.
        stripped = re.sub(r"\s+", " ", line).strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        # Trailing punctuation varies between templates for the same nav label.
        key = lowered.rstrip(" .")
        if key in CHROME_LINES or lowered.startswith(CHROME_PREFIXES):
            continue
        if len(stripped) <= MAX_DEDUPE_LINE:
            seen[lowered] = seen.get(lowered, 0) + 1
            if seen[lowered] > 1:
                continue
        kept.append(stripped)
    return "\n".join(kept)


def meaningful(text: str) -> bool:
    return len(text) >= MIN_CHARS


def main() -> None:
    if not TARGET:
        print("ERROR: no URL argument", file=sys.stderr)
        sys.exit(1)

    html: str | None = None
    final_url = TARGET
    status: object = None

    # Strategy 0 — video transcript. A YouTube watch page strips down to nav
    # chrome and a title, so every other strategy returns a page that contains
    # none of what was actually said. Runs first, and only for video hosts.
    try:
        import video_transcript

        if video_transcript.is_video_url(TARGET):
            print(f"[fetch] Strategy 0 — video transcript: {TARGET}")
            transcript = video_transcript.fetch_transcript(TARGET)
            if meaningful(transcript):
                with open(OUT_FILE, "w") as f:  # nosec: B603
                    f.write(f"Source URL: {TARGET}\n\n{transcript}")
                print(f"[fetch] OK — {len(transcript)} chars of transcript")
                return
            print("[fetch] No transcript available — falling through to page fetch")
    except ImportError:
        print("[fetch] video_transcript unavailable — skipping transcript strategy")

    # Strategy 1 — direct fetch
    print(f"[fetch] Strategy 1 — direct: {TARGET}")
    html, final_url, status = fetch(TARGET)
    text = strip_html(html) if html else ""

    # Strategy 2 — follow og:url / canonical (redirect-wrapper pages)
    if html and not meaningful(text):
        real = extract_real_url(html)
        if real and real != TARGET:
            print(f"[fetch] Strategy 2 — resolved canonical URL: {real}")
            html2, final_url2, status2 = fetch(real)
            text2 = strip_html(html2) if html2 else ""
            if meaningful(text2):
                html, final_url, status, text = html2, final_url2, status2, text2

    # Strategy 3 — Jina AI Reader (renders JavaScript; works for SPAs, X.com, etc.)
    if not meaningful(text):
        jina_url = "https://r.jina.ai/" + TARGET
        print(f"[fetch] Strategy 3 — Jina AI Reader: {jina_url}")
        html3, final_url3, status3 = fetch(jina_url, timeout=45)
        if html3:
            text3 = strip_html(html3) if "<html" in html3.lower() else html3
            if meaningful(text3):
                html, final_url, status, text = html3, final_url3, status3, text3

    # Strategy 4 — Nitter mirror (x.com / twitter.com only)
    if not meaningful(text) and re.search(r"https?://(x|twitter)\.com", TARGET):
        nitter = re.sub(r"https?://(x|twitter)\.com", "https://nitter.net", TARGET)
        print(f"[fetch] Strategy 4 — Nitter: {nitter}")
        html4, final_url4, status4 = fetch(nitter)
        text4 = strip_html(html4) if html4 else ""
        if meaningful(text4):
            html, final_url, status, text = html4, final_url4, status4, text4

    # Strategy 5 — Google Cache
    if not meaningful(text):
        cache_url = (
            "https://webcache.googleusercontent.com/search?q=cache:"
            + urllib.parse.quote(TARGET, safe="")
        )
        print(f"[fetch] Strategy 5 — Google Cache: {cache_url}")
        html, final_url, status = fetch(cache_url)
        text = strip_html(html) if html else ""

    # Strategy 6 — Wayback Machine
    if not meaningful(text):
        wb_url = "https://web.archive.org/web/" + urllib.parse.quote(TARGET, safe="")
        print(f"[fetch] Strategy 6 — Wayback Machine: {wb_url}")
        html, final_url, status = fetch(wb_url)
        text = strip_html(html) if html else ""

    if not meaningful(text):
        print(
            f"ERROR: Could not retrieve meaningful content from {TARGET} "
            f"(got {len(text)} chars after all fallbacks). Last status: {status}",
            file=sys.stderr,
        )
        sys.exit(2)

    with open(OUT_FILE, "w") as f:  # nosec: B603
        f.write(f"Source URL: {TARGET}\nFetched from: {final_url}\n\n{text[:6000]}")
    print(f"[fetch] OK — {len(text)} chars from {final_url}")


if __name__ == "__main__":
    main()
