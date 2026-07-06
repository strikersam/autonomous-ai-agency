#!/bin/bash
# docker/start_web_with_openclaw.sh — launches the OpenClaw Gateway as a
# background subprocess, then starts uvicorn.
#
# On Render free tier, we can only run ONE web service. This script runs
# the OpenClaw Gateway (Node.js, port 18789) in the background inside the
# same container as the Python backend (port $PORT). The FastAPI app
# reverse-proxies /openclaw/* to localhost:18789 so the iOS app pairs
# against https://local-llm-server.onrender.com/openclaw.
#
# If the OpenClaw CLI is not installed (not yet published to npm), the
# gateway subprocess is skipped and the in-process FastAPI fallback
# handles /openclaw/health and /api/openclaw/qr.

set -e

# ── Launch OpenClaw Gateway in the background (if CLI is installed) ──────
if command -v openclaw >/dev/null 2>&1; then
  echo "Starting OpenClaw Gateway on port 18789..."
  OPENCLAW_PORT=18789 openclaw gateway &
  OPENCLAW_PID=$!
  echo "OpenClaw Gateway started (PID: $OPENCLAW_PID)"

  # Give it 3s to boot, then check if it's still alive
  sleep 3
  if kill -0 $OPENCLAW_PID 2>/dev/null; then
    echo "OpenClaw Gateway is running."
  else
    echo "WARNING: OpenClaw Gateway exited early; continuing without it."
    OPENCLAW_PID=""
  fi
else
  echo "OpenClaw CLI not installed; using in-process FastAPI fallback for /openclaw/*."
  OPENCLAW_PID=""
fi

# ── Start the Python backend (uvicorn) ───────────────────────────────────
# Render injects PORT; fall back to 8001 for local use.
exec uvicorn backend.server:app --host 0.0.0.0 --port "${PORT:-8001}"
