FROM nvcr.io/nvidia/l4t-cuda:11.4.19-runtime AS base

ARG UV_VERSION=0.6.2

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y \
    software-properties-common \
    bzip2 \
    curl \
    git \
    cmake \
    ca-certificates \
    libgl1 \
    libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y \
    python3.10 \
    libpython3.10-dev \
    python3.10-dev \
    python3.10-venv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://neuro.debian.net/_static/neuro.debian.net.asc \
    | gpg --dearmor -o /etc/apt/trusted.gpg.d/neurodebian.gpg \
    && curl -fsSL http://neuro.debian.net/lists/bookworm.us-ca.full > /etc/apt/sources.list.d/neurodebian.sources.list

FROM base AS builder

# Build CycloneDDS: the unitree-sdk2py depends on CycloneDDS 0.10.2
RUN git clone --branch=0.10.2 https://github.com/eclipse-cyclonedds/cyclonedds /tmp/cyclonedds \
    && cd /tmp/cyclonedds \
    && mkdir build && cd build \
    && cmake ..\
    -DCMAKE_INSTALL_PREFIX=/usr/local \
    -DENABLE_PACKAGING=ON \
    -DENABLE_TYPELIB=ON \
    && cmake --build . -j$(nproc) --target install \
    && cd / \
    && rm -rf /tmp/cyclonedds
RUN ln -s /usr/local/lib/pkgconfig/CycloneDDS.pc /usr/local/lib/pkgconfig/cyclonedds.pc

RUN curl -fsSL https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh -o /tmp/miniforge.sh \
    && chmod +x /tmp/miniforge.sh \
    && /tmp/miniforge.sh -b -p /opt/conda \
    && rm /tmp/miniforge.sh

RUN source /opt/conda/etc/profile.d/conda.sh \
    && conda config --set auto_activate_base false \
    && conda create -n unitree-client python=3.10 \
    && conda clean -afy

RUN conda install pinocchio -c conda-forge \
    && conda install casadi -c conda-forge \
    && conda clean -afy

FROM base AS runtime

LABEL org.opencontainers.image.description="Spectacles-2-Unitree Robot Client"
LABEL org.opencontainers.image.source="https://github.com/tastyducks/spectacles-2-unitree-server"

ENV LD_LIBRARY_PATH="/app/.venv/lib64/python3.10/site-packages/casadi:$LD_LIBRARY_PATH"

COPY --from=builder /usr/local/ /usr/local

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY . .

RUN uv sync --no-dev

WORKDIR /app/src
CMD ["/app/.venv/bin/python", "main.py"]