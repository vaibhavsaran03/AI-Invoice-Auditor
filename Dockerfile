FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libmagic1 \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY agents/ ./agents/
COPY langgraph_workflow/ ./langgraph_workflow/
COPY mock_erp/ ./mock_erp/
COPY data/ ./data/
COPY config/ ./config/

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

CMD ["sh", "-c", "uvicorn mock_erp.app:app --host 0.0.0.0 --port ${PORT:-10000}"]