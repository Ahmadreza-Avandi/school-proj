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

# ایجاد پوشه‌های مورد نیاز
RUN mkdir -p trainer labels assets/face_detection data

# کپی requirements و نصب پکیج‌ها (برای استفاده از cache بهتر)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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
