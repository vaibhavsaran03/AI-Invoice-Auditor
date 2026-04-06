# 1. Start with Python 3.11
FROM python:3.11-slim

# 2. Install Linux System Tools (Tesseract + Magic)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libmagic1 \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 3. Set work directory
WORKDIR /app

# 4. Install Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. Copy ONLY the Backend Folders
COPY agents/ ./agents/
COPY langgraph_workflow/ ./langgraph_workflow/
COPY mock_erp/ ./mock_erp/
COPY data/ ./data/
COPY config/ ./config/

# 6. Set Path
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

# 7. Start Command (Dynamic Port for Render)
CMD ["sh", "-c", "uvicorn mock_erp.app:app --host 0.0.0.0 --port ${PORT:-10000}"]