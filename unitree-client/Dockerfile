FROM nvcr.io/nvidia/l4t-cuda:12.6.11-runtime AS base

ARG UV_VERSION=0.6.2

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y \
    build-essential \
    cmake \
    curl \
    git \
    libgl1 \
    libglib2.0-0 \
    liburdfdom-dev \
    liburdfdom-headers-dev \
    lsb-release \
    software-properties-common \
    && apt-get clean

RUN curl -fsSL https://neuro.debian.net/_static/neuro.debian.net.asc \
    | gpg --dearmor -o /etc/apt/trusted.gpg.d/neurodebian.gpg \
    && curl -fsSL http://neuro.debian.net/lists/bookworm.us-ca.full > /etc/apt/sources.list.d/neurodebian.sources.list

RUN apt-get update \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get install -y \
    libboost-all-dev \
    libeigen3-dev \
    libspdlog-dev \
    python3.10 \
    python3.10-dev \
    python3.10-venv \
    && apt-get clean

FROM base AS builder

ENV PATH="/opt/openrobots/bin:/usr/local/bin:/app/.venv/bin:${PATH}" \
    PKG_CONFIG_PATH="/opt/openrobots/lib/pkgconfig:/usr/local/lib/pkgconfig" \
    LD_LIBRARY_PATH="/opt/openrobots/lib:/usr/local/lib" \
    PYTHONPATH="/opt/openrobots/lib/python3.10/site-packages:/usr/local/lib:/usr/lib/python3.10:/usr/local/include" \
    CMAKE_PREFIX_PATH="/usr/share:/usr/local:/opt/openrobots" \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Numpy needed for eigenpy
RUN python3.10 -m venv /app/.venv && \
    /app/.venv/bin/pip install --no-cache-dir --upgrade pip && \
    /app/.venv/bin/pip install --no-cache-dir numpy scipy

# Build CycloneDDS: the unitree-sdk2py depends on CycloneDDS 0.10.2
RUN git clone --branch=0.10.2 https://github.com/eclipse-cyclonedds/cyclonedds /tmp/cyclonedds \
    && cd /tmp/cyclonedds \
    && mkdir build && cd build \
    && cmake ..\
    -DCMAKE_INSTALL_PREFIX=/usr/local \
    -DENABLE_PACKAGING=ON \
    && cmake --build . -j$(nproc) --target install \
    && cd / \
    && rm -rf /tmp/cyclonedds

RUN ln -s /usr/local/lib/pkgconfig/CycloneDDS.pc /usr/local/lib/pkgconfig/cyclonedds.pc

# Eigenpy
RUN git clone https://github.com/stack-of-tasks/eigenpy /tmp/eigenpy \
    && cd /tmp/eigenpy \
    && mkdir build \
    && cd build \
    && cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr/local \
    -DPYTHON_EXECUTABLE=/app/.venv/bin/python \
    -DPYTHON_LIBRARY=/usr/lib/aarch64-linux-gnu/libpython3.10.so \
    -DPYTHON_NUMPY_INCLUDE_DIRS=/app/.venv/lib/python3.10/site-packages/numpy/core/include \
    && make -j$(nproc) \
    && make install \
    && cd / \
    && rm -rf /tmp/eigenpy

# Pinocchio
RUN git clone --branch=v3.5.0 https://github.com/stack-of-tasks/pinocchio /tmp/pinocchio \
    && cd /tmp/pinocchio \
    && mkdir build \
    && cd build \
    && cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr/local \
    -DPYTHON_EXECUTABLE=/app/.venv/bin/python \
    -DPYTHON_LIBRARY=/usr/lib/aarch64-linux-gnu/libpython3.10.so \
    -DPYTHON_NUMPY_INCLUDE_DIRS=/app/.venv/lib/python3.10/site-packages/numpy/core/include \
    && make -j$(nproc) \
    && make install \
    && cd / \
    && rm -rf /tmp/pinocchio

FROM base AS runtime

LABEL org.opencontainers.image.description="Spectacles-2-Unitree Robot Client"
LABEL org.opencontainers.image.source="https://github.com/tastyducks/spectacles-2-unitree-server"

COPY --from=builder /usr/local/ /usr/local
COPY --from=builder /app /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY . .

RUN uv sync --no-dev

WORKDIR /app/src
CMD ["/app/.venv/bin/python", "main.py"]