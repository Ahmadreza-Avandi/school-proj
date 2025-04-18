# سیستم حضور و غیاب با تشخیص چهره

این پروژه شامل یک سیستم حضور و غیاب با قابلیت تشخیص چهره است که از Next.js برای فرانت‌اند، Nest.js برای بک‌اند، Redis برای ذخیره‌سازی موقت و MySQL برای دیتابیس استفاده می‌کند.

## نصب و راه‌اندازی

### پیش‌نیازها

- Docker و Docker Compose
- Python 3.10 یا بالاتر
- Node.js 16 یا بالاتر (برای توسعه)

### راه‌اندازی سرویس‌های اصلی با Docker

سرویس‌های اصلی شامل MySQL، Redis، Nest.js (بک‌اند) و Next.js (فرانت‌اند) با Docker Compose راه‌اندازی می‌شوند:

```bash
docker-compose up -d
```

این دستور تمام سرویس‌های زیر را راه‌اندازی می‌کند:
- MySQL (پورت 3306)
- Redis (پورت 6379)
- Nest.js (پورت 3001)
- Next.js (پورت 3000)
- phpMyAdmin (پورت 8081)
- Redis Commander (پورت 8082)

### راه‌اندازی سرویس تشخیص چهره (خارج از Docker)

سرویس تشخیص چهره با Python باید به صورت جداگانه و خارج از Docker اجرا شود. برای راه‌اندازی این سرویس:

1. وارد دایرکتوری faceDetectionWithCamera شوید:
```bash
cd faceDetectionWithCamera
```

2. یک محیط مجازی Python ایجاد کنید (اختیاری اما توصیه می‌شود):
```bash
python -m venv venv
source venv/bin/activate  # در لینوکس/مک
# یا
venv\Scripts\activate  # در ویندوز
```

3. پکیج‌های مورد نیاز را نصب کنید:
```bash
pip install -r requirements.txt
```

4. سرویس تشخیص چهره را اجرا کنید:
```bash
python get-face-data.py
```

این سرویس روی پورت 5000 در دسترس خواهد بود.

## آدرس‌های دسترسی

- فرانت‌اند Next.js: http://localhost:3000
- API بک‌اند Nest.js: http://localhost:3001/api
- API تشخیص چهره: http://localhost:5000
- phpMyAdmin: http://localhost:8081
- Redis Commander: http://localhost:8082

## ساختار پروژه

- `next/`: کد فرانت‌اند (Next.js)
- `nest/`: کد بک‌اند (Nest.js)
- `faceDetectionWithCamera/`: کد تشخیص چهره (Python/Flask)
  - `get-face-data.py`: اپلیکیشن Flask برای تشخیص چهره
  - `assets/`: تصاویر و فایل‌های مورد نیاز
  - `requirements.txt`: وابستگی‌های Python

## نکات مهم

- سرویس Redis به صورت پیش‌فرض روی localhost:6379 در دسترس است.
- هنگام اجرای سرویس تشخیص چهره، اطمینان حاصل کنید که Redis از طریق Docker اجرا شده و در دسترس است.
- سرویس تشخیص چهره به دایرکتوری‌های `trainer` و `labels` برای ذخیره داده‌ها نیاز دارد که به صورت خودکار ایجاد می‌شوند.

## Docker Setup and Configuration

This project includes multiple services configured with Docker:

1. Frontend (Next.js)
2. Backend (Nest.js)
3. MySQL Database
4. Redis Cache
5. Face Detection (Python service)

### Running with Docker

1. Make sure Docker and Docker Compose are installed on your system
2. Clone this repository
3. Build and start all services:

```bash
docker-compose up -d
```

4. Check if all services are running:

```bash
docker-compose ps
```

### Troubleshooting

If you encounter issues:

1. Check container logs:

```bash
docker-compose logs -f [service_name]
```

2. Make sure all required ports are available
3. If database connection fails, you might need to wait for the database to initialize before starting the backend

### Accessing Services

- Frontend: http://localhost:3000
- Backend API: http://localhost:3001
- Face Detection API: http://localhost:5000 