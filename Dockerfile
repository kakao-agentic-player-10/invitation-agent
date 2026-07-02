FROM python:3.13-slim

ARG KAKAO_LOCAL_PROXY_BASE_URL=https://playmcp-embedding-proxy.onrender.com/v1/kakao/local

ENV KAKAO_LOCAL_PROXY_BASE_URL=${KAKAO_LOCAL_PROXY_BASE_URL}

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml README.md ./
RUN uv sync --no-dev --no-install-project

COPY src/ src/
RUN uv sync --no-dev

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "invitation_agent.server", "--http"]
