ARG BUILD_FROM=python:3.12-slim
FROM ${BUILD_FROM}

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

CMD ["python", "-m", "audioflow2mqtt"]
