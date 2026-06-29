# ADR-005: Merge Hermes into the main backend service

## Status
Accepted

## Context
Hermes ran as a separate Render service (agency-hermes.onrender.com) that
returned "Not Found" — not deployed or sleeping on Render free tier. The
separate service consumed a free-tier slot without providing value.

## Decision
Start services/hermes_server.py as an in-process uvicorn background task on
port 8100 inside the main backend's lifespan. Disable during tests.

## Consequences
- No separate Render service needed
- HermesAdapter resolves HERMES_BASE_URL to http://localhost:8100 by default
- One less service to deploy + monitor
- Set RUN_HERMES_IN_PROCESS=false to disable
