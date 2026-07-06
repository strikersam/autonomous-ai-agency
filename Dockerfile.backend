# ── Stage 1: build the React SPA from source ──────────────────────────────────
# The backend serves the built SPA from ../frontend/build. frontend/build/ is
# gitignored (untracked), so we must NOT depend on it existing in the build
# context — building it here from the tracked frontend/ source makes the image
# self-contained for BOTH the Render production build (which uses this
# Dockerfile from a clean checkout) and the Browser E2E CI job.
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --prefer-offline
COPY frontend/ ./
# CI=false so build-time ESLint warnings don't fail the production build.
RUN CI=false npm run build

# ── Stage 2: the Python backend ───────────────────────────────────────────────
FROM python:3.11-slim

# git is required by mcp_server workspace tools (clone_repo, git_commit, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN echo "Cache bust: $CACHE_BUST"
ARG CACHE_BUST=1
RUN pip install --no-cache-dir -r backend/requirements.txt

# NOTE: the SAM realtime voice worker deps (livekit-agents + onnxruntime/av,
# ~600MB installed) are deliberately NOT installed here — they live in their
# own image (Dockerfile.voice) so the web image stays small and cold starts
# fast. The in-process fallback (SAM_VOICE_IN_PROCESS=true) therefore needs
# both a >=2GB instance AND this line re-added:
#   COPY voice/requirements-livekit.txt voice/requirements-livekit.txt
#   RUN pip install --no-cache-dir -r voice/requirements-livekit.txt
# Preferred: run the worker from Dockerfile.voice on any machine with RAM
# (it dials out to LiveKit Cloud — no inbound networking needed).

# Install the Chromium browser (+ OS deps) that Playwright drives for the
# scanner's headless render pass, so JS-rendered / bot-protected sites are
# detectable in production. If this layer is removed the scanner still works
# (static-HTML fallback) — it just can't execute JS.
RUN python -m playwright install --with-deps chromium

COPY backend/ backend/
RUN echo "Cache bust: $CACHE_BUST"
COPY packages/ packages/
COPY db/ db/
COPY agent/ agent/
COPY router/ router/
COPY agents/ agents/
COPY mcp_server/ mcp_server/
COPY schedules/ schedules/
COPY docker/ docker/
COPY runtimes/ runtimes/
COPY loops/ loops/
COPY tasks/ tasks/
COPY handlers/ handlers/
COPY workflow/ workflow/
COPY sync/ sync/
COPY setup/ setup/
COPY hardware/ hardware/
# Ship EVERY root-level Python module wholesale. Copying them one-by-one
# silently dropped newly-added modules from the image and caused
# "works locally, ModuleNotFoundError in prod" outages (e.g. brain_policy.py →
# "No module named brain_policy" blocked every agent task; telegram_service.py
# → approval gate never fired). The wholesale copy is future-proof and is
# enforced by tests/test_dockerfile_ships_root_modules.py.
COPY *.py ./
COPY models/ models/
COPY services/ services/
# Voice package: server-side TTS (voice/tts.py, /agent/sam/speak) + the SAM
# LiveKit realtime voice pipeline (config/token/worker). Before this line the
# image never shipped voice/, so /agent/sam/speak silently failed in prod.
COPY voice/ voice/
# Ship the skill library so /api/skills (SkillRegistry._index_local) finds the
# .claude/skills/*/SKILL.md descriptors at runtime. Without this the Skills
# screen shows 0 skills in production: the dir is resolved relative to the repo
# root but was never copied into the image, so _index_local() early-returns.
COPY .claude/ .claude/
# The built SPA from stage 1 (backend/server.py `_FRONTEND_BUILD` serves it at
# /login and every UI route). Built from source in-image, so this never depends
# on the gitignored frontend/build/ existing in the build context.
COPY --from=frontend-build /frontend/build/ frontend/build/

EXPOSE 8001

# Render injects PORT; fall back to 8001 for local use.
# The OpenClaw Gateway is an in-process WebSocket server — no background subprocess needed.
CMD ["sh", "-c", "uvicorn backend.server:app --host 0.0.0.0 --port ${PORT:-8001}"]
