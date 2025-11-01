FROM python:3.10-slim

WORKDIR /app

# فقط کتابخانه‌های runtime موردنیاز OpenCV (بدون build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# نصب پکیج‌ها با نسخه‌های سازگار (از wheel های از پیش کامپایل شده استفاده می‌شود)
RUN pip install --no-cache-dir \
    flask==3.0.0 \
    flask-cors==4.0.0 \
    redis==5.0.1 \
    numpy==1.26.2 \
    opencv-contrib-python-headless==4.8.1.78 \
    persiantools==4.1.1 \
    pytz==2024.1 \
    requests==2.31.0 \
    pillow==10.1.0 \
    boto3==1.34.0 \
    cryptography==41.0.7

# ایجاد پوشه‌های مورد نیاز
RUN mkdir -p trainer labels assets/face_detection data

# کپی فایل‌های موردنیاز
COPY get-face-data.py .
COPY assets/face_detection/*.xml assets/face_detection/

# تنظیم متغیرهای محیطی
ENV FLASK_APP=get-face-data.py
ENV FLASK_ENV=production
ENV REDIS_HOST=redis
ENV PYTHONUNBUFFERED=1

# باز کردن پورت پیش‌فرض Flask
EXPOSE 5000

# اجرای اپلیکیشن
CMD ["flask", "run", "--host=0.0.0.0"]
