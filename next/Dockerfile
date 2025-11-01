# مرحله اول: ساخت برنامه
FROM node:18-alpine AS builder

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

# ------------------------------
# مرحله نهایی: اجرای برنامه
# ------------------------------
FROM node:18-alpine

# تنظیم محیط کار
WORKDIR /usr/src/app

# کپی فایل‌های package.json
COPY package*.json ./

# نصب فقط production dependencies
RUN npm install --production --force

# کپی فایل‌های build از مرحله قبلی
COPY --from=builder /usr/src/app/.next ./.next
COPY --from=builder /usr/src/app/public ./public
COPY --from=builder /usr/src/app/next.config.js ./

# کپی server.ts برای اجرا
COPY server.ts ./

# نصب tsx برای اجرای TypeScript
RUN npm install -g tsx

# پورت 3000 - Nginx مدیریت SSL رو انجام می‌ده
EXPOSE 3000

# دستور اجرای برنامه
CMD ["npm", "start"]
