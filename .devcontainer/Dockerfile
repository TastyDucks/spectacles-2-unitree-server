#
# Base stage for all images
#
FROM --platform=linux/amd64 ubuntu:noble AS base
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    apt-transport-https \
    curl \
    gnupg \
    lsb-release \
    python3.12 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL http://robotpkg.openrobots.org/packages/debian/robotpkg.asc | tee /etc/apt/keyrings/robotpkg.asc > /dev/null && \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/robotpkg.asc] http://robotpkg.openrobots.org/packages/debian/pub $(lsb_release -cs) robotpkg" \
    | tee /etc/apt/sources.list.d/robotpkg.list && \
    # pinocchio
    curl -fsSL https://neuro.debian.net/_static/neuro.debian.net.asc \
    | gpg --dearmor -o /etc/apt/trusted.gpg.d/neurodebian.gpg && \
    curl -fsSL http://neuro.debian.net/lists/bookworm.us-ca.full \
    | tee /etc/apt/sources.list.d/neurodebian.sources.list > /dev/null

RUN apt-get update && apt-get install -y --no-install-recommends \
    libboost-all-dev \
    libspdlog-dev \
    libeigen3-dev \
    robotpkg-py312-pinocchio \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/openrobots/bin:${PATH}" \
    PKG_CONFIG_PATH="/opt/openrobots/lib/pkgconfig" \
    LD_LIBRARY_PATH="/opt/openrobots/lib" \
    PYTHONPATH="/opt/openrobots/lib/python3.12/site-packages" \
    CMAKE_PREFIX_PATH="/opt/openrobots"

#
# Devcontainer
#
FROM --platform=linux/amd64 base AS dev

ARG UV_VERSION=0.6.2

# GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /usr/share/keyrings/githubcli.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list && \
    # docker
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list

# Additional dev packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    docker-buildx-plugin \
    docker-ce-cli \
    gcc-aarch64-linux-gnu \
    gh \
    git \
    htop \
    iputils-ping \
    jq \
    less \
    linux-tools-common \
    linux-tools-generic \
    micro \
    net-tools \
    openssl \
    pipx \
    python3-pip \
    ssh \
    unzip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pipx ensurepath && pipx install "uv==$UV_VERSION"

# Install act
RUN --mount=type=cache,target=/root/.cache/act \
    curl --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/nektos/act/master/install.sh | bash

# Build CycloneDDS
RUN git clone --depth 1 https://github.com/eclipse-cyclonedds/cyclonedds /tmp/cyclonedds \
    && cd /tmp/cyclonedds && mkdir build && cd build \
    && cmake -DCMAKE_INSTALL_PREFIX=/usr/local .. \
    && cmake --build . --target install \
    && cd / && rm -rf /tmp/cyclonedds