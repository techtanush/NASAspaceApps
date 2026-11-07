FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgdal32 libgeos-c1v5 libproj25 curl \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-install-project --extra extra-tanush
COPY src/ ./src/
COPY config/ ./config/
RUN uv sync --frozen --extra extra-tanush && useradd --system --uid 10001 analogforge \
    && mkdir -p /app/data && chown -R analogforge /app/data
USER analogforge
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "analogforge.main:app", "--host", "0.0.0.0", "--port", "8000"]
