ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       bash ca-certificates git build-essential util-linux ncurses-term procps jq coreutils \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 tester \
    && useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash tester

COPY allowlist_proxy.py /opt/product-test/allowlist_proxy.py

USER 1000:1000
WORKDIR /workspace
CMD ["sleep", "infinity"]
