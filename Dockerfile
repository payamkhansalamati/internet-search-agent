FROM python:3.12-slim AS builder
WORKDIR /build
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Pin the package installer as well as application dependencies so local and
# container builds resolve the same environment.
RUN python -m pip install --no-cache-dir uv==0.11.26

COPY pyproject.toml uv.lock ./
COPY src src
RUN uv sync --frozen --no-dev --extra ui --no-editable

FROM python:3.12-slim
RUN useradd --create-home app
COPY --from=builder /opt/venv /opt/venv
COPY config /app/config
COPY frontend /app/frontend
WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH"
USER app
EXPOSE 8000
CMD ["uvicorn", "search_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
