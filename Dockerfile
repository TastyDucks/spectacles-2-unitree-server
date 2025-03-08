FROM python:3.12-slim-bookworm AS build

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0

WORKDIR /app

ADD . .

COPY src/static static
COPY src/templates templates

RUN uv sync --frozen --no-install-project --no-dev

RUN uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm AS runtime

COPY --from=build /app /app

ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 80

CMD ["python", "app/src/main.py"]