FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable && useradd --uid 10001 --create-home app
USER app
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 CMD ["/app/.venv/bin/uzex", "health"]
CMD ["/app/.venv/bin/uzex", "bot"]
