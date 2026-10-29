FROM ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff AS uv

FROM python:3.12.16-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
COPY bot/pyproject.toml bot/uv.lock bot/.python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY bot/src ./src
RUN uv sync --frozen --no-dev
COPY knowledge ./knowledge
RUN useradd --system --uid 10001 bot && mkdir /data /relay && chown bot /data /relay
USER bot
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s CMD ["/app/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"]
ENTRYPOINT ["/app/.venv/bin/python", "-m", "support_bot"]
