# Base pinned directly: the Home Assistant builder no longer reads build.yaml's
# build_from, and otherwise injects its Alpine base (which has no pip/python) via
# the BUILD_FROM arg. python:3.12-slim is a multi-arch manifest, so each host
# builds its own architecture.
FROM python:3.12-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
RUN pip install --no-cache-dir uv

# Install dependencies from the lockfile (project itself is package=false).
COPY pyproject.toml uv.lock ./
COPY audioflow2mqtt ./audioflow2mqtt
RUN uv sync --frozen --no-dev

# python:3.12-slim has no curl/wget; use stdlib urllib instead.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8099/health')"

CMD ["python", "-m", "audioflow2mqtt"]
