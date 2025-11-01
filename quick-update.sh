#!/bin/bash

# 🔄 اسکریپت آپدیت سریع - برای زمانی که فقط کد تغییر کرده

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔄 شروع آپدیت سریع...${NC}"

# توقف containers
echo "⏸️  توقف containers..."
docker-compose down

# بیلد مجدد (فقط چیزهایی که تغییر کردن)
echo "🔨 بیلد مجدد..."
docker-compose build --parallel

# اجرای مجدد
echo "▶️  اجرای مجدد..."
docker-compose up -d

# نمایش وضعیت
echo ""
echo -e "${GREEN}✅ آپدیت انجام شد!${NC}"
echo ""
docker-compose ps

echo ""
echo "برای مشاهده لاگ‌ها: docker-compose logs -f"
