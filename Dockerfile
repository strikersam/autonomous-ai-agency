FROM node:22-slim AS webui
WORKDIR /src/webui/frontend
COPY webui/frontend/package.json ./
RUN npm install
COPY webui/frontend/ ./
RUN npm run build

FROM python:3.13-slim AS app
WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends git \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Install Playwright + headless Chromium for website scanning (gucci.com, etc.)
RUN playwright install --with-deps chromium

# Optional code graph for agents (agent/code_graph.py, CODE_GRAPH_ENABLED).
# Off by default: the native indexer adds ~300MB to the image. The pip package
# downloads that binary (checksum-verified) on first run, so run it once here
# rather than inside the first agent request. Render passes service env vars to
# the build as build args, so INSTALL_CODE_GRAPH=true there turns this on.
ARG INSTALL_CODE_GRAPH=false
RUN if [ "$INSTALL_CODE_GRAPH" = "true" ]; then \
      pip install --no-cache-dir codebase-memory-mcp==0.11.0 \
      && codebase-memory-mcp --version; \
    fi

COPY . /app
# Ensure packages/ is present even if a future .dockerignore excludes it.
# V2.0 Modernization moved provider_router, brain_policy, admin_auth,
# social_auth, rbac, scheduler, storage, etc. into packages/ — the shims
# at the old paths import from packages/, so the image is broken without it.
COPY packages/ /app/packages/
COPY --from=webui /src/webui/frontend/dist /app/webui/frontend/dist

ENV PROXY_PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health', timeout=5)" || exit 1

CMD ["sh", "-lc", "UVICORN_LOG_LEVEL=$(printf '%s' \"${LOG_LEVEL:-INFO}\" | tr '[:upper:]' '[:lower:]') && uvicorn proxy:app --host 0.0.0.0 --port ${PORT:-8000} --log-level \"$UVICORN_LOG_LEVEL\""]

