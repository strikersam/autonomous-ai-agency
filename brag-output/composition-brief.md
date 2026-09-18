# Hyperframes Composition Brief: Autonomous AI Agency (feature tour, v2)

## Objective
A ~44s, feature-focused launch tour for Autonomous AI Agency. Show what the product does across the real flow — no vanity metrics.

## Output
- Composition: `brag-output/composition/` · Rendered: `brag-output/brag.mp4`
- Format: landscape 1920x1080 · Duration ~44s (9 scenes; longer than the /brag default by explicit user request)

## Source Material
- Read: README.md, docs/platform-guide.md, frontend/src/index.css, CLAUDE.md
- Copy that must appear verbatim / near-verbatim:
  - paste your website URL
  - 35 specialist families · CEO-coordinated
  - Plan → Execute → Verify
  - 100+ checks · six pillars (Technical · Content · Security · Social · GEO · AIO)
  - Nothing ships without your sign-off (HITL)
  - Runs 24×7
  - NVIDIA NIM → Cerebras → Groq → Ollama (automatic failover)
  - Self-hosted · MIT · Your servers, your models, your data

## Creative Direction
- Tone: app-store / polished. Clean feature cards, smooth slides, one accent per scene, premium dark UI.
- Avoid: vanity metrics (PR counts etc.), generic SaaS language, abstract filler, waveform/equalizer visuals.

## Visual Identity
- Background #020304; accent #5da2ff; success #46d9a4; text #f7f9fc / #a8b3c2
- Display font Outfit; mono IBM Plex Mono (compiler-injected @font-face)

## Storyboard
See `brag-output/brag-plan.md` (9 scenes). Centerpieces are the working-product moments: stack scan, audit dial, specialist fleet, the plan/execute/verify loop, the approval card, the 24×7 schedule list, and the failover chain.

## Audio
- Music: assets/music/happy-beats-business-moves-vol-1-by-ende-dot-app.mp3 @ 0.26, full length; cues preset alongside
- SFX: keyboard (hook), interface/drop_00x (chips/rows), impact/impactSoft_medium (verify), interface/click_001 (approve), impact/impactBell_heavy_000 (outro)

## Hyperframes Instructions
Single paused GSAP timeline on window.__timelines['main'], seek-safe, deterministic. Visibility keyed off data-start/data-duration; class="clip" on scenes. GSAP vendored locally (assets/vendor/gsap.min.js) — the render browser has no CDN egress. `hyperframes check` must pass (lint, runtime, layout, motion, WCAG-AA contrast) before render.
