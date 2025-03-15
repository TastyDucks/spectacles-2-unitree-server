FROM ubuntu:latest AS dev

ARG TARGETARCH
ARG UV_VERSION=0.6.2

ENV DEBIAN_FRONTEND=noninteractive

# Install certificates and https transport first
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    apt-transport-https \
    curl \
    gnupg

# GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /usr/share/keyrings/githubcli.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list && \
    # docker
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list

# Useful stuff
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    docker-ce-cli \
    gcc-aarch64-linux-gnu \
    gh \
    git \
    htop \
    iputils-ping \
    jq \
    less \
    libssl-dev \
    linux-tools-common \
    linux-tools-generic \
    micro \
    net-tools \
    openssl \
    pipx \
    python3-pip \
    python3.12 \
    ssh \
    unzip

RUN pipx ensurepath && pipx install "uv==$UV_VERSION"

# Install act
RUN --mount=type=cache,target=/root/.cache/act \
    curl --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/nektos/act/master/install.sh | bash

# Robot client deps

RUN git clone https://github.com/eclipse-cyclonedds/cyclonedds \
    && cd cyclonedds && mkdir build && cd build && cmake -DCMAKE_INSTALL_PREFIX=/usr/local .. && make install \
    && cd ../../ && rm -rf cyclonedds
ENV CYCLONEDDS_HOME=/usr/local
ENV CMAKE_PREFIX_PATH=/usr/local