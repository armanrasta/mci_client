FROM docker.arvancloud.ir/python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

# install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./

COPY ./src/ src/

RUN uv sync --frozen --no-dev

ENV PYTHONPATH=/app/src

ENV MCI_LOG_LEVEL=INFO

RUN useradd -m -u 1000 app && chown -R app:app /app
USER app

ENTRYPOINT ["uv", "run", "python", "-m", "mci_client"]