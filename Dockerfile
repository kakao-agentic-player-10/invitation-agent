FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml README.md ./
RUN uv sync --no-dev --no-install-project

COPY src/ src/
RUN uv sync --no-dev

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN uv run playwright install --with-deps chromium

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "invitation_agent.server", "--http"]
