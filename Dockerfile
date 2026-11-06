# The Hushmark GitHub App webhook server (ADR-0010). Secrets come from the host's environment,
# never from this image: see docs/github-app/README.md.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock README.md ./
COPY hushmark ./hushmark
COPY prompts ./prompts
RUN uv sync --locked --no-dev

RUN useradd --system --no-create-home hushmark
USER hushmark

EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s CMD ["/app/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"]
CMD ["/app/.venv/bin/python", "-m", "hushmark.server"]
