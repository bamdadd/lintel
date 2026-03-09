FROM mcr.microsoft.com/devcontainers/base:ubuntu

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install Python, Node, and common build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    nodejs \
    npm \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:/home/vscode/.local/bin:$PATH"

# Install Rust toolchain (for cargo test)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:$PATH"

# Install Go (auto-detect architecture)
RUN ARCH=$(dpkg --print-architecture) && \
    curl -fsSL "https://go.dev/dl/go1.22.5.linux-${ARCH}.tar.gz" | tar -C /usr/local -xzf -
ENV PATH="/usr/local/go/bin:$PATH"

# Pre-install spacy small English model (needed for PII tests at import time)
RUN rm -f /usr/lib/python3.*/EXTERNALLY-MANAGED && \
    uv pip install --system spacy && \
    python3 -m spacy download en_core_web_sm

# Pre-install project dependencies so sandbox starts warm
# uv caches downloaded wheels in ~/.cache/uv — subsequent `uv sync` in the
# workspace reuses these cached packages instead of downloading from PyPI.
COPY pyproject.toml uv.lock /opt/lintel-deps/
RUN cd /opt/lintel-deps && uv sync --all-extras --no-install-project 2>&1 | tail -5

WORKDIR /workspace
