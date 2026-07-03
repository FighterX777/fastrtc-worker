FROM python:3.11.0-slim

WORKDIR /app

# System deps for aiortc, librosa, pydub
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libavdevice-dev \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir \
        "gradio>=5.0,<6.0" \
        "huggingface_hub>=0.24.0" \
        "typer>=0.12,<1.0"

# Copy app
COPY server.py .
COPY test.html .
COPY fastrtc/ ./fastrtc/

# Pre-download Silero VAD model at build time so container starts instantly
RUN python -c "from fastrtc.pause_detection import get_silero_model; get_silero_model()"

EXPOSE 8000

CMD ["python", "server.py"]
