# استفاده از نود جدیدترین نسخه برای پشتیبانی بهتر از ماژول‌های ES
FROM node:latest

# تنظیم محیط کار
WORKDIR /usr/src/app

# کپی کردن فایل‌های package.json و package-lock.json
COPY package*.json ./

# نصب وابستگی‌ها
RUN npm install --force

# کپی کردن کدها و فایل‌های پروژه
COPY . .

# ساخت برنامه Next.js
RUN npm run build

# ایجاد دایرکتوری برای گواهی‌نامه‌های SSL
RUN mkdir -p /certs

# پورت‌ها
EXPOSE 80 443 3000

# دستور اجرای برنامه با استفاده از اسکریپت سفارشی
CMD ["npm", "run", "server"]
