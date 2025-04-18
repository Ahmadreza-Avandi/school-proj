# استفاده از نود جدیدتر برای پشتیبانی بهتر از ماژول‌های ES
FROM node:latest AS builder

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

# مرحله دوم: اجرای برنامه در محیط تولید
FROM node:latest AS runner

# تنظیم محیط کار
WORKDIR /usr/src/app

# متغیرهای محیطی برای محیط تولید
ENV NODE_ENV=production

# کپی فایل‌های مورد نیاز از مرحله قبلی
COPY --from=builder /usr/src/app/next.config.js ./
COPY --from=builder /usr/src/app/public ./public
COPY --from=builder /usr/src/app/.next ./.next
COPY --from=builder /usr/src/app/node_modules ./node_modules
COPY --from=builder /usr/src/app/package.json ./package.json

# کپی کردن سرور TypeScript و تنظیمات آن
COPY --from=builder /usr/src/app/server.ts ./server.ts
COPY --from=builder /usr/src/app/tsconfig.json ./tsconfig.json

# کپی فایل‌های محیطی
COPY --from=builder /usr/src/app/.env.local ./.env.local

# ایجاد دایرکتوری برای گواهی‌نامه‌های SSL
RUN mkdir -p /certs

# نصب ts-node برای اجرای فایل‌های TypeScript
RUN npm install -g typescript ts-node

# ایجاد اسکریپت اجرایی
RUN echo '#!/bin/sh\nnode --loader ts-node/esm --experimental-specifier-resolution=node server.ts' > start.sh && chmod +x start.sh

# پورت‌ها
EXPOSE 80 443 3000

# دستور اجرای برنامه
CMD ["./start.sh"]
