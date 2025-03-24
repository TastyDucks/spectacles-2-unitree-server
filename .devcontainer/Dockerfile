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
    # Needed for some Python dependencies that want the full non-headless version of OpenCV.
    libgl1 \
    lsb-release \
    python3.12 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN . /etc/lsb-release && \
    curl -fsSL http://robotpkg.openrobots.org/packages/debian/robotpkg.asc > /etc/apt/keyrings/robotpkg.asc \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/robotpkg.asc] http://robotpkg.openrobots.org/packages/debian/pub $(lsb_release -cs) robotpkg" > /etc/apt/sources.list.d/robotpkg.list \
    # pinocchio
    && curl -fsSL https://neuro.debian.net/_static/neuro.debian.net.asc \
        | gpg --dearmor -o /etc/apt/trusted.gpg.d/neurodebian.gpg \
    && curl -fsSL http://neuro.debian.net/lists/bookworm.us-ca.full > /etc/apt/sources.list.d/neurodebian.sources.list \
    # Git LFS
    && curl -fsSL https://packagecloud.io/github/git-lfs/gpgkey \
        | gpg --dearmor -o /etc/apt/keyrings/github_git-lfs-archive-keyring.gpg \
    && curl -fsSL "https://packagecloud.io/install/repositories/github/git-lfs/config_file.list?os=${DISTRIB_ID}&dist=${DISTRIB_CODENAME}" > /etc/apt/sources.list.d/github_git-lfs.list

RUN apt-get update && apt-get install -y --no-install-recommends \
    libboost-all-dev \
    libspdlog-dev \
    libeigen3-dev \
    robotpkg-py312-pinocchio \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/openrobots/bin:/usr/local/bin:${PATH}" \
    PKG_CONFIG_PATH="/opt/openrobots/lib/pkgconfig:/usr/local/lib/pkgconfig" \
    LD_LIBRARY_PATH="/opt/openrobots/lib:/usr/local/lib" \
    PYTHONPATH="/opt/openrobots/lib/python3.12/site-packages:/usr/local/lib/python3.12/site-packages" \
    CMAKE_PREFIX_PATH="/opt/openrobots:/usr/local"

#
# Devcontainer
#
FROM --platform=linux/amd64 base AS dev

LABEL org.opencontainers.image.description="Spectacles-2-Unitree Coordination Server dev container"
LABEL org.opencontainers.image.source="https://github.com/tastyducks/spectacles-2-unitree-server"

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
RUN git clone https://github.com/eclipse-cyclonedds/cyclonedds /tmp/cyclonedds \
    && cd /tmp/cyclonedds \
    # The unitree-sdk2py depends on CycloneDDS 0.10.2
    && git checkout 0.10.2 \
    && mkdir build && cd build \
    && cmake -DCMAKE_INSTALL_PREFIX=/usr/local .. \
    && cmake --build . --target install \
    && cd / && rm -rf /tmp/cyclonedds

ENV CMAKE_PREFIX_PATH="/usr/local/include/"