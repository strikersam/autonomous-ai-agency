"""Tests for video transcript extraction (`.github/scripts/video_transcript.py`).

The module is split so everything fragile about YouTube's page shape is isolated
from the parsing, and the parsing is pure. These tests cover the pure half
against recorded fragments — no network, so they are hermetic and cannot flake
on a rate limit or a blocked datacenter IP.

The network paths (`_get`, and `fetch_transcript`'s orchestration of it) are
deliberately not unit-tested: they are the part that legitimately varies, and a
mock of them would assert only that the mock was called.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / ".github" / "scripts"


@pytest.fixture(scope="module")
def vt():
    spec = importlib.util.spec_from_file_location(
        "video_transcript", SCRIPTS / "video_transcript.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["video_transcript"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


# ---------------------------------------------------------------------------
# URL shapes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ&t=42s", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ],
)
def test_video_id_handles_every_url_shape(vt, url: str, expected: str) -> None:
    assert vt.video_id(url) == expected


def test_video_id_ignores_social_tracking_parameters(vt) -> None:
    """Issue #1135's URL arrived with an fbclid; shares routinely add these."""
    url = "https://youtu.be/dQw4w9WgXcQ?si=abc123&fbclid=PAVERFWATTEI1wZG9mAmV4dG4"
    assert vt.video_id(url) == "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        "https://gist.github.com/someone/abc123",
        "https://example.com/watch?v=notyoutube",
        "not a url at all",
        "",
    ],
)
def test_non_video_urls_are_declined(vt, url: str) -> None:
    assert vt.video_id(url) is None
    assert vt.is_video_url(url) is False


def test_is_video_url_accepts_known_hosts(vt) -> None:
    assert vt.is_video_url("https://www.youtube.com/watch?v=x")
    assert vt.is_video_url("https://youtu.be/x")


# ---------------------------------------------------------------------------
# Caption track preference
# ---------------------------------------------------------------------------

def test_manual_english_beats_auto_generated_english(vt) -> None:
    """ASR wording is materially worse; prefer a human track when one exists."""
    tracks = [
        {"languageCode": "en", "kind": "asr", "baseUrl": "auto"},
        {"languageCode": "en", "baseUrl": "manual"},
    ]
    assert vt.select_caption_track(tracks)["baseUrl"] == "manual"


def test_auto_english_beats_another_language(vt) -> None:
    tracks = [
        {"languageCode": "de", "baseUrl": "german"},
        {"languageCode": "en", "kind": "asr", "baseUrl": "auto-en"},
    ]
    assert vt.select_caption_track(tracks)["baseUrl"] == "auto-en"


def test_falls_back_to_first_track_when_no_english_exists(vt) -> None:
    tracks = [{"languageCode": "ja", "baseUrl": "japanese"}]
    assert vt.select_caption_track(tracks)["baseUrl"] == "japanese"


def test_no_tracks_selects_nothing(vt) -> None:
    assert vt.select_caption_track([]) is None


# ---------------------------------------------------------------------------
# Timed-text formats
# ---------------------------------------------------------------------------

def test_parse_json3_flattens_segments_into_prose(vt) -> None:
    payload = json.dumps(
        {
            "events": [
                {"segs": [{"utf8": "A 40-minute video "}, {"utf8": "holds maybe "}]},
                {"segs": [{"utf8": "six minutes of signal."}]},
            ]
        }
    )
    assert vt.parse_json3(payload) == "A 40-minute video holds maybe six minutes of signal."


def test_parse_json3_skips_timing_padding_events(vt) -> None:
    """Events without `segs` carry no text and must not produce stray spaces."""
    payload = json.dumps({"events": [{"tStartMs": 0}, {"segs": [{"utf8": "real text"}]}]})
    assert vt.parse_json3(payload) == "real text"


def test_parse_json3_survives_malformed_payloads(vt) -> None:
    assert vt.parse_json3("not json at all") == ""
    assert vt.parse_json3("") == ""


def test_parse_timedtext_xml_decodes_double_encoded_entities(vt) -> None:
    """This format double-encodes: `&amp;#39;` must resolve to a single quote."""
    payload = "<transcript><text start='0'>it&amp;#39;s here</text></transcript>"
    assert vt.parse_timedtext_xml(payload) == "it's here"


def test_parse_timedtext_xml_returns_empty_for_other_content(vt) -> None:
    assert vt.parse_timedtext_xml("<html><body>nope</body></html>") == ""


# ---------------------------------------------------------------------------
# Player response extraction
# ---------------------------------------------------------------------------

def test_extract_player_response_handles_nested_braces(vt) -> None:
    """Regex-terminated matching truncates this; brace matching must not.

    The blob nests objects several levels deep, so a lazy `{.*?}` match stops at
    the first inner closing brace and yields invalid JSON.
    """
    page = (
        '<script>var ytInitialPlayerResponse = '
        '{"videoDetails":{"title":"Deep","author":{"name":"x"}},"captions":{"a":{"b":1}}};'
        "</script>"
    )
    parsed = vt.extract_player_response(page)
    assert parsed["videoDetails"]["title"] == "Deep"
    assert parsed["captions"]["a"]["b"] == 1


def test_extract_player_response_ignores_braces_inside_strings(vt) -> None:
    """A title containing a brace must not unbalance the matcher."""
    page = 'ytInitialPlayerResponse = {"videoDetails":{"title":"a } brace"}};'
    assert vt.extract_player_response(page)["videoDetails"]["title"] == "a } brace"


def test_extract_player_response_absent_marker_returns_empty(vt) -> None:
    assert vt.extract_player_response("<html>no player response here</html>") == {}


def test_caption_tracks_and_title_degrade_gracefully(vt) -> None:
    """An unfamiliar page shape must yield empties, never raise."""
    assert vt.caption_tracks({}) == []
    assert vt.caption_tracks({"captions": {}}) == []
    assert vt.video_title({}) == ""


def test_caption_tracks_reads_the_documented_path(vt) -> None:
    response = {
        "captions": {
            "playerCaptionsTracklistRenderer": {
                "captionTracks": [{"languageCode": "en", "baseUrl": "u"}]
            }
        }
    }
    assert vt.caption_tracks(response) == [{"languageCode": "en", "baseUrl": "u"}]


# ---------------------------------------------------------------------------
# Contract: never raise, never fabricate
# ---------------------------------------------------------------------------

def test_fetch_transcript_declines_non_video_urls_without_network(vt) -> None:
    """A non-video URL must short-circuit before any request is attempted."""
    assert vt.fetch_transcript("https://gist.github.com/someone/abc") == ""


def test_fetch_transcript_returns_empty_when_the_page_is_unavailable(vt, monkeypatch) -> None:
    """No transcript means "", so the caller falls back — never a fabrication."""
    monkeypatch.setattr(vt, "_get", lambda *a, **k: "")
    assert vt.fetch_transcript("https://youtu.be/dQw4w9WgXcQ") == ""


def test_fetch_transcript_returns_empty_when_captions_are_disabled(vt, monkeypatch) -> None:
    monkeypatch.setattr(
        vt, "_get", lambda *a, **k: 'ytInitialPlayerResponse = {"videoDetails":{"title":"T"}};'
    )
    assert vt.fetch_transcript("https://youtu.be/dQw4w9WgXcQ") == ""


def test_fetch_transcript_labels_auto_generated_captions(vt, monkeypatch) -> None:
    """ASR wording is approximate; the header must say so before it is quoted."""
    page = (
        'ytInitialPlayerResponse = {"videoDetails":{"title":"A Talk"},"captions":'
        '{"playerCaptionsTracklistRenderer":{"captionTracks":'
        '[{"languageCode":"en","kind":"asr","baseUrl":"https://cc/track"}]}}};'
    )
    transcript = json.dumps({"events": [{"segs": [{"utf8": "spoken words here"}]}]})

    def fake_get(url: str, timeout: int = 30) -> str:
        return transcript if "cc/track" in url else page

    monkeypatch.setattr(vt, "_get", fake_get)
    out = vt.fetch_transcript("https://youtu.be/dQw4w9WgXcQ")

    assert "A Talk" in out
    assert "auto-generated" in out
    assert "spoken words here" in out


def test_fetch_transcript_truncates_a_very_long_talk(vt, monkeypatch) -> None:
    """One video must not be able to consume an entire context window."""
    page = (
        'ytInitialPlayerResponse = {"videoDetails":{"title":"Long"},"captions":'
        '{"playerCaptionsTracklistRenderer":{"captionTracks":'
        '[{"languageCode":"en","baseUrl":"https://cc/track"}]}}};'
    )
    huge = json.dumps({"events": [{"segs": [{"utf8": "word " * 20000}]}]})

    def fake_get(url: str, timeout: int = 30) -> str:
        return huge if "cc/track" in url else page

    monkeypatch.setattr(vt, "_get", fake_get)
    out = vt.fetch_transcript("https://youtu.be/dQw4w9WgXcQ")
    body = out.split("\n\n", 1)[1]
    assert len(body) <= vt.MAX_TRANSCRIPT_CHARS


# ---------------------------------------------------------------------------
# Integration with the shared fetcher
# ---------------------------------------------------------------------------

def test_fetch_url_runs_the_transcript_strategy_before_page_strategies() -> None:
    """A video URL must not fall through to the page fetch that loses the audio."""
    source = (SCRIPTS / "fetch_url.py").read_text()
    strategy_zero = source.index("Strategy 0 — video transcript")
    strategy_one = source.index("Strategy 1 — direct")
    assert strategy_zero < strategy_one
    assert "video_transcript.is_video_url" in source


def test_bulk_workflow_stages_the_transcript_module() -> None:
    """fetch_url.py imports it, so a /tmp copy without it silently degrades."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "bulk-issue-context.yml").read_text()
    assert "cp .github/scripts/video_transcript.py /tmp/video_transcript.py" in workflow


def test_rejected_issues_are_excluded_from_the_scheduled_sweep() -> None:
    """A reject that the 4-hourly sweep ignores is not a reject at all.

    The issue stays open by design, so without this filter the sweep would pick
    it up hours later and build the source the architect pass ruled out.
    """
    sweep = (REPO_ROOT / ".github" / "workflows" / "process-quick-note.yml").read_text()
    # Asserted on the label, not on the jq that excludes it. This previously
    # pinned `index("quick-note:rejected") == null`, so widening the selector to
    # also drop status-report issues broke a test whose actual subject —
    # "a rejected issue is not re-picked" — was unchanged.
    # `tests/test_autonomous_pipeline_gates.py` executes the real expression
    # against sample issues and checks which number comes back.
    assert "quick-note:rejected" in sweep

    generator = (REPO_ROOT / ".github" / "workflows" / "issue-context-generator.yml").read_text()
    assert "--add-label \"quick-note:rejected\"" in generator
