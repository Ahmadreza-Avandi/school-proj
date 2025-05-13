# سیستم حضور و غیاب با تشخیص چهره

این پروژه شامل یک سیستم حضور و غیاب با قابلیت تشخیص چهره است که از Next.js برای فرانت‌اند، Nest.js برای بک‌اند، Redis برای ذخیره‌سازی موقت و MySQL برای دیتابیس استفاده می‌کند. همچنین از Traefik برای reverse proxy و مدیریت مسیرها استفاده می‌شود.

## معماری پروژه

سیستم از چندین سرویس مستقل تشکیل شده است:

- **فرانت‌اند (Next.js)**: رابط کاربری وب سیستم
- **بک‌اند (Nest.js)**: API برای مدیریت کاربران، حضور و غیاب و گزارش‌گیری
- **سرویس تشخیص چهره (Python/Flask)**: پردازش تصاویر و تشخیص چهره‌ها
- **دیتابیس (MySQL)**: ذخیره‌سازی داده‌های کاربران، کلاس‌ها و سوابق حضور و غیاب
- **کش (Redis)**: ذخیره‌سازی موقت اطلاعات و جلسات کاربران
- **Traefik**: مدیریت درخواست‌ها و هدایت آنها به سرویس‌های مناسب

## نصب و راه‌اندازی

### پیش‌نیازها

- Docker و Docker Compose
- Git
- دسترسی به اینترنت برای دانلود ایمیج‌های Docker

### راه‌اندازی با Docker

1. ابتدا مخزن را Clone کنید:
```bash
git clone https://github.com/yourusername/attendance-system.git
cd attendance-system
```

2. سرویس‌ها را با Docker Compose راه‌اندازی کنید:
```bash
docker-compose up -d
```

3. منتظر بمانید تا همه سرویس‌ها اجرا شوند (ممکن است چند دقیقه طول بکشد):
```bash
docker-compose ps
```

4. تمام سرویس‌ها از طریق آدرس اصلی در دسترس خواهند بود:
   - فرانت‌اند: https://a.networklearnzero.shop
   - API بک‌اند: https://a.networklearnzero.shop/api
   - API تشخیص چهره: https://a.networklearnzero.shop/python-api
   - پنل مدیریت دیتابیس: https://a.networklearnzero.shop/phpmyadmin
   - پنل مدیریت Redis: https://a.networklearnzero.shop/redis-commander
   - پنل مدیریت Traefik: https://a.networklearnzero.shop/traefik

### دسترسی داخلی به سرویس‌ها (برای توسعه)

در محیط توسعه، می‌توانید مستقیماً به سرویس‌ها دسترسی داشته باشید:

- فرانت‌اند Next.js: http://localhost:3000
- API بک‌اند Nest.js: http://localhost:3001
- API تشخیص چهره: http://localhost:5000
- MySQL: localhost:3306
- phpMyAdmin: http://localhost:8081
- Redis Commander: http://localhost:8082
- داشبورد Traefik: http://localhost:8080

## ساختار پروژه

```
attendance-system/
├── docker-compose.yml       # تنظیمات Docker Compose
├── mysql-init.sql           # اسکریپت اولیه دیتابیس
├── nest/                    # کد بک‌اند (Nest.js)
│   ├── Dockerfile           # فایل Docker برای بک‌اند
│   ├── src/                 # کد منبع بک‌اند
│   ├── prisma/              # تنظیمات و مدل‌های Prisma
│   └── ...
├── next/                    # کد فرانت‌اند (Next.js)
│   ├── Dockerfile           # فایل Docker برای فرانت‌اند
│   ├── src/                 # کد منبع فرانت‌اند
│   └── ...
└── faceDetectionWithCamera/ # کد تشخیص چهره (Python/Flask)
    ├── Dockerfile           # فایل Docker برای سرویس تشخیص چهره
    ├── get-face-data.py     # اپلیکیشن Flask برای تشخیص چهره
    ├── requirements.txt     # وابستگی‌های Python
    └── ...
```

## نکات کاربردی و حل مشکلات متداول

### تنظیم Redis

Redis به صورت پیش‌فرض در حالت standalone تنظیم شده است. اگر با خطای زیر مواجه شدید:
```
Error condition on socket for SYNC: Connection refused
```

اطمینان حاصل کنید که در `docker-compose.yml` دستور زیر برای سرویس Redis تنظیم شده باشد:
```yaml
command: redis-server --replicaof no one
```

### مشکل ثبت کاربر جدید

اگر هنگام ثبت کاربر جدید با خطای زیر مواجه شدید:
```
Field 'id' doesn't have a default value
```

باید جدول `User` در دیتابیس را اصلاح کنید تا فیلد `id` به صورت AUTO_INCREMENT تنظیم شود:

```sql
SET FOREIGN_KEY_CHECKS = 0;
ALTER TABLE `User` MODIFY COLUMN `id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY;
SET FOREIGN_KEY_CHECKS = 1;
```

این دستور را می‌توانید از طریق phpMyAdmin اجرا کنید.

### بازسازی کانتینرها

برای بازسازی یک سرویس خاص (مثلاً پس از تغییر کد):

```bash
docker-compose build nestjs  # بازسازی فقط سرویس بک‌اند
docker-compose up -d nestjs  # راه‌اندازی مجدد سرویس
```

برای بازسازی همه سرویس‌ها:

```bash
docker-compose down
docker-compose build
docker-compose up -d
```

### مشاهده لاگ‌ها

برای مشاهده لاگ‌های یک سرویس خاص:

```bash
docker-compose logs -f nestjs  # مشاهده لاگ‌های بک‌اند
docker-compose logs -f nextjs  # مشاهده لاگ‌های فرانت‌اند
docker-compose logs -f redis   # مشاهده لاگ‌های Redis
```

## ویژگی‌های سیستم

- **احراز هویت کاربران**: ثبت‌نام، ورود و مدیریت سطوح دسترسی
- **مدیریت کلاس‌ها**: افزودن، ویرایش و حذف کلاس‌ها
- **مدیریت دانش‌آموزان**: افزودن، ویرایش و حذف اطلاعات دانش‌آموزان
- **تشخیص چهره**: ثبت حضور خودکار با استفاده از تشخیص چهره
- **گزارش‌گیری**: امکان گزارش‌گیری از وضعیت حضور و غیاب دانش‌آموزان

## نحوه توسعه (برای توسعه‌دهندگان)

### توسعه بک‌اند (Nest.js)

1. وارد دایرکتوری nest شوید:
```bash
cd nest
```

2. وابستگی‌ها را نصب کنید:
```bash
npm install
```

3. سرویس را در حالت توسعه اجرا کنید:
```bash
npm run start:dev
```

### توسعه فرانت‌اند (Next.js)

1. وارد دایرکتوری next شوید:
```bash
cd next
```

2. وابستگی‌ها را نصب کنید:
```bash
npm install
```

3. سرویس را در حالت توسعه اجرا کنید:
```bash
npm run dev
```

### توسعه سرویس تشخیص چهره (Python/Flask)

## راه‌اندازی و اجرای پروژه تشخیص چهره با دوربین

### پیش‌نیازها

- Python 3.6 یا بالاتر
- pip
- دسترسی به اینترنت برای نصب وابستگی‌ها

### مراحل نصب و راه‌اندازی

1. وارد دایرکتوری `faceDetectionWithCamera` شوید:
```bash
cd faceDetectionWithCamera
```

2. یک محیط مجازی ایجاد کنید:
```bash
python -m venv venv
```

3. محیط مجازی را فعال کنید:
- در ویندوز:
```bash
venv\Scripts\activate
```
- در لینوکس/مک:
```bash
source venv/bin/activate
```

4. وابستگی‌ها را نصب کنید:
```bash
pip install -r requirements.txt
```

5. سرویس را اجرا کنید:
```bash
flask run --debug
```

### نکات و پیکربندی‌ها

- اطمینان حاصل کنید که پورت 5000 در سیستم شما باز است.
- در صورت نیاز به تغییر پورت، فایل `get-face-data.py` را ویرایش کنید.
- برای اجرای صحیح، مطمئن شوید که تمام وابستگی‌ها به درستی نصب شده‌اند.