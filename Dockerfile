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

# App code.
COPY app ./app
COPY scripts ./scripts

EXPOSE 8000

# Container talks to the "qdrant" service, not localhost (see docker-compose.yml).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
