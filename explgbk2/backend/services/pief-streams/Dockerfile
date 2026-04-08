FROM ghcr.io/astral-sh/uv:0.10.11-python3.14-trixie-slim

ENV PYTHONUNBUFFERED=1

# Compile bytecode
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1

# uv Cache
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#caching
ENV UV_LINK_MODE=copy

WORKDIR /app/

# Place executables in the environment at the front of the path
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#using-the-environment
ENV PATH="/app/.venv/bin:$PATH"

# Layer 1: install all external deps from lockfile; workspace members excluded.
# uv.lock + root pyproject.toml are enough — workspace source not needed yet.
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-workspace

# Copy only the workspace members that pief-streams needs.
# Omitting pief-api keeps this image lean.
COPY ./backend/libs/pief-models /app/backend/libs/pief-models
COPY ./backend/libs/pief-logdb /app/backend/libs/pief-logdb
COPY ./backend/services/pief-streams /app/backend/services/pief-streams

# Layer 2: install only pief-streams and its workspace deps (pief-models, pief-logdb).
# --frozen because not all workspace members are present (pief-api is absent).
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --package pief-streams

WORKDIR /app/

CMD ["faststream", "run", "pief.streams.cdc:app"]
