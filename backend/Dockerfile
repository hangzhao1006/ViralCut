FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps: backend + main project (stage1/2/3)
COPY backend/requirements.txt /tmp/backend-req.txt
COPY requirements.txt /tmp/main-req.txt
RUN pip install --no-cache-dir -r /tmp/backend-req.txt && \
    pip install --no-cache-dir -r /tmp/main-req.txt

COPY src/ ./src/
COPY backend/ ./backend/

RUN mkdir -p backend/static output

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
