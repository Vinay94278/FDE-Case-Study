# Solstice Docs Q&A - production image
FROM python:3.11-slim

# Set INSTALL_EMBEDDINGS=false to omit semantic search.
ARG INSTALL_EMBEDDINGS=true

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    LOG_FORMAT=json \
    EXPOSE_TECHNICAL_MESSAGES=false

WORKDIR /app

COPY requirements.txt requirements-embeddings.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$INSTALL_EMBEDDINGS" = "true" ]; then \
        pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch \
        && pip install --no-cache-dir -r requirements-embeddings.txt; \
    fi

COPY app ./app
COPY data ./data

# Run as a non-root user
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/logs \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/api/v1/health', timeout=4)"

# Railway and similar platforms set $PORT; default is 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
