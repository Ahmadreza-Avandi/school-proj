FROM python:3.10-slim

# تنظیم دایرکتوری کاری
WORKDIR /app

# نصب ابزارهای موردنیاز برای OpenCV و ابزارهای بیلد dlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    curl \
    && rm -rf /var/lib/apt/lists/*

# کپی فایل requirements.txt
COPY requirements.txt .

# نصب کتابخانه‌ها از روی requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# ایجاد پوشه‌های مورد نیاز با دسترسی مناسب
RUN mkdir -p trainer labels assets/face_detection data && \
    chmod 777 trainer labels

# کپی فایل‌های موردنیاز
COPY get-face-data.py .
COPY assets/face_detection/*.xml assets/face_detection/

# تنظیم متغیرهای محیطی
ENV PYTHONUNBUFFERED=1
ENV REDIS_HOST=redis

# باز کردن پورت پیش‌فرض Flask
EXPOSE 5000

# اجرای اپلیکیشن
CMD ["python", "get-face-data.py"]