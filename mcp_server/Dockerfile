FROM python:3.12-slim

# Install git and essential build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
# PyYAML is here for the governance policy file. Without it the policy engine
# still runs, but it falls back to its embedded default and the operator's
# config/agent_policy.yaml would be silently ignored — a policy that does not
# apply is worse than a missing one, because it looks applied.
RUN pip install --no-cache-dir \
    fastapi==0.136.1 \
    uvicorn[standard]==0.46.0 \
    httpx==0.28.1 \
    PyYAML==6.0.2

# Copy the mcp_server package
COPY mcp_server/ ./mcp_server/

# Governance layer (threat-model T11). This server exposes clone/write/
# run_command/git_push over HTTP, so it must evaluate policy and write audit
# rows exactly like the in-process agent path. Only the three packages the
# adapter actually imports are vendored — governance, its config reader, and
# the shared redactor — rather than all of packages/, to keep this image small
# and its dependency surface honest.
COPY packages/__init__.py ./packages/__init__.py
COPY packages/config/ ./packages/config/
COPY packages/governance/ ./packages/governance/
COPY packages/security/ ./packages/security/

# The policy document itself. Without it the engine uses its embedded default,
# which is a real policy but not necessarily *your* policy.
COPY config/agent_policy.yaml ./config/agent_policy.yaml

# Workspace directory (mounted from host or created fresh)
RUN mkdir -p /workspaces

# Create a non-root user and transfer ownership
RUN useradd -m -u 1000 -s /bin/bash mcpuser \
 && chown -R mcpuser:mcpuser /app /workspaces

USER mcpuser

# Configure git identity for commits made by the agent (runs as mcpuser)
RUN git config --global user.email "mcp-agent@local-llm-server" \
 && git config --global user.name "MCP Agent" \
 && git config --global credential.helper "" \
 && git config --global safe.directory "/workspaces/*"

EXPOSE 8008

ENV MCP_WORKSPACE_BASE=/workspaces
ENV PORT=8008
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "mcp_server.server"]
