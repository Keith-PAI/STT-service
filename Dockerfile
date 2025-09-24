# Simple CPU image for Faster-Whisper API
FROM python:3.11-slim

# ffmpeg for audio conversions
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py ./

# Model/env defaults
ENV FW_MODEL=base
ENV FW_COMPUTE=int8
# Set CORS for your WP origin (comma-separated list). For testing, "*" is okay.
ENV FW_CORS=*

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", 8000]
