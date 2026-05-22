FROM ghcr.io/astral-sh/uv:0.11.7 AS uv

# -----------------------------------
# STAGE 1: prod stage
# -----------------------------------
FROM python:3.13-slim-trixie AS prod

# Copy uv binary from the uv stage
COPY --from=uv /uv /usr/local/bin/uv

RUN apt-get update && apt-get install -y \
  gcc \
  && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_MANAGED_PYTHON=1

WORKDIR /app/src

# Install dependencies first — cached unless lockfile changes
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

# Copy app source and install the project itself
COPY . .
RUN uv sync --locked --no-dev

CMD ["python", "-m", "api"]

# -----------------------------------
# STAGE 2: development build
# Includes dev dependencies
# -----------------------------------
FROM prod AS dev

RUN uv sync --locked --all-groups
