# FinQuery backend — FastAPI app image.
FROM python:3.13-slim

# Keep Python lean and unbuffered (logs flush immediately in containers).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first so this layer caches unless requirements.txt changes.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# App code (data/ and tests/ are excluded via .dockerignore; data is mounted at runtime).
COPY app ./app
COPY scripts ./scripts

# Run as a non-root user; pre-create the writable data dir uploads land in.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/data/raw \
    && chown -R appuser /app
USER appuser

EXPOSE 8000

# Liveness: hit /health with the stdlib (no curl needed in the slim image).
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

# Container talks to the "qdrant" service, not localhost (see docker-compose.yml).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
