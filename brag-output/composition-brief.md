# Hyperframes Composition Brief: Autonomous AI Agency

## Objective
Create a short, polished launch-style brag video for Autonomous AI Agency.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080
- Duration: ~20s (five scenes)

## Source Material
- Project root: /home/user/autonomous-ai-agency
- Primary files read: README.md, frontend/src/index.css, frontend/public/index.html, CLAUDE.md
- Product name: Autonomous AI Agency
- Tagline / strongest claim: "Paste your website URL. Get a CTO-grade audit in minutes. Then let the agency that produced it go to work — on your infrastructure."
- Key UI/visual to recreate: dark dashboard surface, blue-accent health-score dial, mono numerics, specialist chips
- Copy that must appear verbatim:
  - paste your website URL
  - 102 checks
  - Technical · Content · Security · Social · GEO · AIO
  - 35 specialist families
  - Plan → Execute → Verify
  - 323 / 906 merged PRs written by the agents themselves
  - Self-hosted · MIT · Your servers, your models, your data

## Creative Direction
- Tone preset: polished
- Creative direction: quiet premium product film — proof over hype, every claim a real number
- Interpretation: fewer scenes, longer holds, smooth motion, no frantic cuts. Numbers and type carry it.
- Angle: The README opens "Most autonomous agent projects show you a demo video. Here are artifacts instead." The video honors that — it does not claim, it shows the one checkable number (323/906) that proves the agents ship.
- Hook: dark terminal, `paste your website URL_` types out in mono with a blinking accent caret.
- Outro / punchline: wordmark + "Self-hosted · MIT · Your servers, your models, your data" + URL.
- Avoid: generic SaaS language, abstract filler visuals, unrelated redesign, waveform/equalizer visuals.

## Visual Identity
- Background: #020304 (surfaces #0a0c0f / #111419)
- Text: #f7f9fc primary, #a8b3c2 tertiary, #6e7786 muted
- Accent: #5da2ff (hover #7ab1ff); success #46d9a4
- Display font: Outfit (Google Fonts), fallback system sans
- Body/mono font: IBM Plex Mono (Google Fonts)
- Visual references: health-score dial, six pillar tags, specialist chips, plan/execute/verify pipeline

## Storyboard
Use `brag-output/brag-plan.md` as the creative contract.

Scene summary:
1. Paste your URL — 3.2s — hook line types out in a dark terminal
2. The audit — 4.8s — score dial counts 0→74, six pillar tags, "102 checks"
3. The agency assembles — 5.0s — 7 specialist chips arrive one by one, Plan→Execute→Verify draws
4. The proof — 4.0s — `323 / 906` counts up, "written by the agents themselves" (payoff lands on strong cue ~13.1s)
5. Lock-up / outro — 3.0s — wordmark, tagline, url, accent underline sweep

## Audio
- Audio role: warm restrained bed + a few precise accents
- Audio arc: bed enters low, lifts slightly through the assemble scene, one bell on the 323 payoff, fades under the logo
- Music: assets/music/happy-beats-business-moves-vol-12-by-ende-dot-app.mp3 at data-volume 0.3
- Music treatment: start 0, gentle fade-out over the last ~2.5s (via WebAudio gain or trailing low volume clip)
- Music cue guidance: bundled preset assets/music/cues/happy-beats-business-moves-vol-12-by-ende-dot-app.music-cues.json; strong cue 13.11s for the 323 reveal (single strong-cue lock); beat grid ~0.54s for chip sequence
- Audio-reactive treatment: subtle — accent glow on the score dial and the proof number may breathe; no waveform/equalizer
- Audio-coupled moments:
  - Scene 1 hook — randomized keyboard/keypress ticks during typing
  - Scene 2 count-up — one soft interface/drop when 74 settles
  - Scene 3 chips — soft interface/drop per chip (thinned)
  - Scene 4 payoff — one impact/impactBell_heavy_000 at ~13.11s (beat-locked)
- SFX selection guidance: keyboard for typing, drop_00x for soft pop-ins, impactBell_heavy_000 for the single payoff; restraint throughout
- Audio files: copied into brag-output/composition/assets/ (music, keyboard, interface, impact)

## Hyperframes Instructions
Single paused GSAP timeline registered on window.__timelines, seek-safe, deterministic. Visibility keyed off data-start/data-duration; class="clip" on scene wrappers. Show real product copy/visuals (health dial, pillars, chips, proof stat). Keep every text line readable (hold to the reading floor). Total 15-25s. Run `hyperframes check` before render (single gate); fix WCAG contrast findings within the palette.
