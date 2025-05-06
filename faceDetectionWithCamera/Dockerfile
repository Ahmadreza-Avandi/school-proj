FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    curl \
    git \
    wget \
    python3-dev \
    pkg-config \
    libopenblas-dev \
    liblapack-dev \
    gfortran \
    libjpeg-dev \
    libpng-dev \
    libgtk2.0-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p trainer labels assets/face_detection data && \
    chmod 777 trainer labels

COPY get-face-data.py .
COPY assets/face_detection/*.xml assets/face_detection/

ENV PYTHONUNBUFFERED=1
ENV REDIS_HOST=redis

EXPOSE 5000

CMD ["python", "get-face-data.py"]