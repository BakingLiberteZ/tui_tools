FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TERM=xterm-256color \
    SASSY_WALLET_DATA_DIR=/data

WORKDIR /app

RUN adduser --disabled-password --gecos "" --uid 10001 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data /app

COPY pyproject.toml setup.py README.md requirements.txt ./
COPY sassy_wallet ./sassy_wallet

RUN pip install --upgrade pip \
    && pip install .

USER appuser
VOLUME ["/data"]

ENTRYPOINT ["sassy-wallet"]
