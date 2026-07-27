---
name: video-context
description: >
  Extract what was actually said in a video — transcript, structure, and key
  moments — from a YouTube URL, without an API key or account. Use whenever a
  task hands you a video link and expects you to know its contents: quick-note
  issues, research requests, "what's in this talk", "steal this structure".
triggers:
  - "/video-context"
  - "youtube.com/watch"
  - "youtu.be/"
  - "analyze this video"
  - "break down this video"
  - "what's in this video"
  - "summarize this talk"
  - "transcript of"
references:
  - .github/scripts/video_transcript.py
  - .github/scripts/fetch_url.py
  - docs/QUICK_NOTE_CONTEXT_RULEBOOK.md
---

# Skill: video-context — read a video without watching it

## Why This Exists

A video URL used to be a dead end in this repo. `fetch_url.py` would retrieve a
YouTube watch page, strip the tags, and return navigation chrome plus a title —
none of what was actually said. Any context generated from a video quick-note
was therefore derived from the URL slug and the model's guesses about the topic,
which is exactly the failure `docs/QUICK_NOTE_CONTEXT_RULEBOOK.md` R1 exists to
prevent.

A 40-minute talk holds maybe six minutes of signal. Reading the transcript costs
a few thousand tokens; watching costs 40 minutes and cannot be done by an agent
at all.

## When To Use This

Use it the moment a task contains a video URL and the task depends on the
video's contents. Do **not** guess a video's contents from its title — that is a
fabricated-specifics failure (CLAUDE.md §14.10 pattern 1), and titles are
written to be clicked, not to be accurate.

If the transcript cannot be retrieved, say so and mark every downstream claim as
an Assumption per CLAUDE.md §14.5. Do not quietly substitute your prior
knowledge of the topic.

## How It Works

`.github/scripts/video_transcript.py`, standard library only — no API key, no
account, no third-party scraper, no new dependency.

1. Parse the video id out of the URL. Handles `/watch?v=`, `youtu.be/`,
   `/shorts/`, `/embed/` and `/live/`, and ignores the tracking parameters
   social shares append (`?fbclid=`, `?si=`).
2. Fetch the watch page and brace-match the `ytInitialPlayerResponse` JSON blob
   out of it. (Brace-matched, not regex-terminated — the blob nests objects and
   contains escaped braces inside strings, so a lazy match truncates it.)
3. Read `captions.playerCaptionsTracklistRenderer.captionTracks`, then pick a
   track: manually-written English beats auto-generated English (`kind == "asr"`)
   beats any other language.
4. Fetch the track's `baseUrl` with `&fmt=json3` and flatten it to prose,
   falling back to the older `<transcript><text>` XML format.

Output is prefixed with the video title, source URL, and caption language. When
the track is auto-generated the header says so, because ASR wording is
approximate and should not be quoted as verbatim speech.

## Usage

Automatic in the quick-note pipeline — `fetch_url.py` runs this as Strategy 0
for any video host before its ordinary page-fetch strategies, so
`generate_context.py` receives spoken content rather than page chrome.

Directly, from a session:

```bash
python .github/scripts/video_transcript.py 2>/dev/null || \
python -c "
import sys; sys.path.insert(0, '.github/scripts')
import video_transcript
print(video_transcript.fetch_transcript('https://www.youtube.com/watch?v=VIDEO_ID'))
"
```

Or through the shared fetcher, which handles videos and articles alike:

```bash
python .github/scripts/fetch_url.py "https://youtu.be/VIDEO_ID"
cat /tmp/note_content.txt
```

## What To Do With The Transcript

Once you have the text, the value is in compressing it — not in echoing it back.
Answer the question that was actually asked. If the task is open-ended, the
useful shape is:

- **What it is** — the one-sentence claim the video makes.
- **Structure** — how it is organised, with the timestamps or ordering that
  matter.
- **Key moments** — the few passages carrying the signal, quoted.
- **What is applicable here** — mapped onto real modules in this repo, or an
  explicit "nothing applicable", which is a valid and common answer.

That last point matters. When a video informs a quick-note issue, the rulebook's
R3 verdict applies: `adopt`, `adapt`, or `reject`, with a reason. Most linked
videos do not translate into changes to this codebase, and inventing a feature
to justify the link is worse than rejecting it.

## Limits — know these before relying on it

- **No captions, no transcript.** Some videos disable them entirely. The
  function returns `""`; it does not fabricate.
- **Auto-generated captions are approximate.** Punctuation and proper nouns are
  frequently wrong. Do not present ASR text as an exact quote.
- **Age-gated and members-only videos will not resolve** — the watch page does
  not carry a player response for them.
- **YouTube can block datacenter IPs.** From CI this sometimes returns nothing;
  the caller falls back to its ordinary strategies rather than failing the run.
- **Long talks are truncated** at `MAX_TRANSCRIPT_CHARS` (20,000) so a single
  video cannot consume an entire context window.
- **YouTube only, today.** Other hosts fall through to the normal page fetch.
  `VIDEO_HOSTS` is where support for another platform would be added.

## Testing

`tests/test_video_transcript.py` covers URL-shape parsing, caption-track
preference, both timed-text formats, and the brace-matching extractor — all
without network access, using recorded page fragments. Network paths are not
unit-tested by design; they are the part that legitimately varies.
