# Hugging Face Spaces Docker configuration for XTTS Voice Cloning
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    python3.10-dev \
    libssl-dev \
    libffi-dev \
    libsndfile1 \
    libsndfile1-dev \
    ffmpeg \
    espeak-ng \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY api.py .
COPY core.py .
COPY static ./static
COPY audio ./audio

# Create necessary directories
RUN mkdir -p temp_audio outputs

# Expose port 7860 (Hugging Face Spaces default)
EXPOSE 7860

# Set environment variables
ENV COQUI_TOS_AGREED=1
ENV PYTHONUNBUFFERED=1

# Run the FastAPI app on port 7860
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "7860"]
