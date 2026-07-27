"""Extract a usable text transcript from a video URL, without an API key.

Why this exists: quick-note issues carry their whole value in a URL, and some of
those URLs are videos. `fetch_url.py` strips a YouTube watch page down to
navigation chrome and a title — no spoken content — so context generated from a
video link was derived from nothing. An agent handed "here's a 40-minute talk,
what's in it" had no way to answer.

Approach: YouTube embeds a JSON blob (`ytInitialPlayerResponse`) in the watch
page that lists caption tracks. Each track has a `baseUrl` serving the timed
text. Both are public and need no key, no account, and no third-party scraper.

The module is split so the fragile part (YouTube's page shape) is isolated from
the parsing, which is pure and unit-testable without network access:

    video_id(url)                  -> "dQw4w9WgXcQ" | None
    select_caption_track(tracks)   -> track dict | None
    parse_json3(payload)           -> "spoken text ..."
    parse_timedtext_xml(payload)   -> "spoken text ..."
    fetch_transcript(url)          -> "Title\\n\\ntranscript" | ""

`fetch_transcript` never raises: a video with captions disabled, an age-gated
video, or a datacenter IP that YouTube blocks all return "" so the caller can
fall back to its normal strategies.
"""
from __future__ import annotations

import html
import json
import logging
import re
import urllib.parse
import urllib.request

log = logging.getLogger("video_transcript")

#: Hosts whose URLs this module knows how to read.
VIDEO_HOSTS = ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "music.youtube.com")

#: Caption languages preferred in order. A manually-written English track beats
#: an auto-generated one, which beats any other language.
PREFERRED_LANGS = ("en", "en-US", "en-GB")

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

#: Cap so one long talk cannot consume an entire LLM context window.
MAX_TRANSCRIPT_CHARS = 20000


def is_video_url(url: str) -> bool:
    """True when this module should handle *url* instead of a generic fetch."""
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except ValueError:
        return False
    return host in VIDEO_HOSTS


def video_id(url: str) -> str | None:
    """Return the YouTube video id from any of its URL shapes.

    Handles /watch?v=, youtu.be/, /shorts/, /embed/ and /live/, ignoring the
    tracking parameters that social shares append (?fbclid=..., ?si=...).
    """
    try:
        parts = urllib.parse.urlparse(url)
    except ValueError:
        return None

    host = parts.netloc.lower()
    if host == "youtu.be":
        candidate = parts.path.lstrip("/").split("/")[0]
        return candidate or None

    if host not in VIDEO_HOSTS:
        return None

    if parts.path == "/watch":
        values = urllib.parse.parse_qs(parts.query).get("v")
        return values[0] if values else None

    match = re.match(r"^/(?:shorts|embed|live|v)/([^/?#]+)", parts.path)
    return match.group(1) if match else None


def select_caption_track(tracks: list[dict]) -> dict | None:
    """Pick the most useful caption track: English manual > English auto > first.

    `kind == "asr"` marks YouTube's automatic speech recognition. It is usable
    but noticeably worse than a human track, so it only wins when no manual
    English track exists.
    """
    if not tracks:
        return None

    def lang_of(track: dict) -> str:
        return str(track.get("languageCode") or "")

    manual_en = [t for t in tracks if lang_of(t) in PREFERRED_LANGS and t.get("kind") != "asr"]
    if manual_en:
        return manual_en[0]

    auto_en = [t for t in tracks if lang_of(t) in PREFERRED_LANGS]
    if auto_en:
        return auto_en[0]

    return tracks[0]


def parse_json3(payload: str) -> str:
    """Flatten YouTube's json3 timed-text format into plain prose.

    Shape: {"events": [{"segs": [{"utf8": "word "}, ...]}, ...]}. Events with no
    `segs` are timing padding and carry no text.
    """
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return ""

    chunks: list[str] = []
    for event in data.get("events") or []:
        for seg in event.get("segs") or []:
            text = seg.get("utf8", "")
            if text and text != "\n":
                chunks.append(text)
    return _tidy("".join(chunks))


def parse_timedtext_xml(payload: str) -> str:
    """Flatten the older `<transcript><text ...>` timed-text format."""
    if "<text" not in payload:
        return ""
    pieces = re.findall(r"<text[^>]*>(.*?)</text>", payload, re.DOTALL)
    # Entities are double-encoded in this format (&amp;#39; -> ').
    decoded = [html.unescape(html.unescape(piece)) for piece in pieces]
    return _tidy(" ".join(decoded))


def _tidy(text: str) -> str:
    """Collapse the whitespace that caption formats scatter through the text."""
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _get(url: str, timeout: int = 30) -> str:
    """Fetch *url* as text, returning "" on any failure."""
    try:
        request = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - https only, checked by caller
            return response.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 - any failure means "fall back"
        log.warning("video fetch failed for %s: %s", url, exc)
        return ""


def extract_player_response(page_html: str) -> dict:
    """Pull the `ytInitialPlayerResponse` JSON object out of a watch page.

    Brace-matched rather than regex-terminated: the blob contains nested objects
    and escaped braces inside strings, so a lazy `\\{.*?\\}` match truncates it.
    """
    marker = "ytInitialPlayerResponse"
    start = page_html.find(marker)
    if start == -1:
        return {}
    brace = page_html.find("{", start)
    if brace == -1:
        return {}

    depth = 0
    in_string = False
    escaped = False
    for index in range(brace, len(page_html)):
        char = page_html[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(page_html[brace : index + 1])
                except json.JSONDecodeError:
                    return {}
    return {}


def caption_tracks(player_response: dict) -> list[dict]:
    """Return the caption tracks a player response advertises, or []."""
    try:
        renderer = player_response["captions"]["playerCaptionsTracklistRenderer"]
    except (KeyError, TypeError):
        return []
    tracks = renderer.get("captionTracks")
    return tracks if isinstance(tracks, list) else []


def video_title(player_response: dict) -> str:
    """Return the video title, or "" when the page shape is unfamiliar."""
    try:
        return str(player_response["videoDetails"]["title"])
    except (KeyError, TypeError):
        return ""


def fetch_transcript(url: str, timeout: int = 30) -> str:
    """Return "Title\\n\\n<transcript>" for *url*, or "" if unavailable.

    Never raises. An empty return means the caller should fall back to its
    ordinary fetch strategies — captions may be disabled, the video age-gated,
    or the request blocked.
    """
    vid = video_id(url)
    if not vid:
        return ""

    page = _get(f"https://www.youtube.com/watch?v={urllib.parse.quote(vid)}", timeout)
    if not page:
        return ""

    player_response = extract_player_response(page)
    track = select_caption_track(caption_tracks(player_response))
    if not track or not track.get("baseUrl"):
        log.info("no caption track available for video %s", vid)
        return ""

    # json3 is easier to parse and less lossy than the default XML.
    base_url = str(track["baseUrl"])
    payload = _get(base_url + "&fmt=json3", timeout)
    transcript = parse_json3(payload) if payload else ""
    if not transcript:
        transcript = parse_timedtext_xml(_get(base_url, timeout))
    if not transcript:
        return ""

    title = video_title(player_response)
    body = transcript[:MAX_TRANSCRIPT_CHARS]
    header = f"Video title: {title}\nSource: {url}\nTranscript language: {track.get('languageCode', '?')}"
    if track.get("kind") == "asr":
        header += " (auto-generated captions — treat wording as approximate)"
    return f"{header}\n\n{body}"
