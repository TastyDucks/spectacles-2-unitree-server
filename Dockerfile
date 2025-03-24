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

RUN curl -fsSL http://robotpkg.openrobots.org/packages/debian/robotpkg.asc > /etc/apt/keyrings/robotpkg.asc \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/robotpkg.asc] http://robotpkg.openrobots.org/packages/debian/pub $(lsb_release -cs) robotpkg" > /etc/apt/sources.list.d/robotpkg.list \
    # pinocchio
    && curl -fsSL https://neuro.debian.net/_static/neuro.debian.net.asc \
        | gpg --dearmor -o /etc/apt/trusted.gpg.d/neurodebian.gpg \
    && curl -fsSL http://neuro.debian.net/lists/bookworm.us-ca.full > /etc/apt/sources.list.d/neurodebian.sources.list \
    # Git LFS
    && curl -fsSL https://packagecloud.io/github/git-lfs/gpgkey \
        | gpg --dearmor -o /etc/apt/keyrings/github_git-lfs-archive-keyring.gpg \
    && curl -fsSL https://packagecloud.io/install/repositories/github/git-lfs/config_file.list?os=${DISTRIB_ID}\&dist=${DISTRIB_CODENAME} > /etc/apt/sources.list.d/github_git-lfs.list

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
# Coordination server build stage
#
FROM --platform=linux/amd64 base AS build

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0

WORKDIR /app

ADD . .

RUN uv sync --no-install-project --no-dev

RUN uv sync --no-dev

#
# Coordination server runtime stage
#
FROM --platform=linux/amd64 base AS runtime

LABEL org.opencontainers.image.description="Spectacles-2-Unitree Coordination Server"
LABEL org.opencontainers.image.source="https://github.com/tastyducks/spectacles-2-unitree-server"

COPY --from=build /app /app
ENV PATH="/app/.venv/bin:${PATH}"
WORKDIR /app/src
EXPOSE 80
CMD ["python3.12", "main.py"]