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