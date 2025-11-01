#!/bin/bash

# 🚀 اسکریپت دیپلوی سریع
set -e

# رنگ‌ها
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🚀 شروع دیپلوی سریع...${NC}"

# توقف containers قبلی
echo -e "${YELLOW}⏹️  توقف containers قبلی...${NC}"
docker-compose down 2>/dev/null || true

# پاک‌سازی images قدیمی (اختیاری)
read -p "آیا می‌خواهید images قدیمی را پاک کنید؟ (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}🧹 پاک‌سازی images قدیمی...${NC}"
    docker system prune -f
fi

# بیلد و اجرا
echo -e "${YELLOW}🔨 بیلد containers...${NC}"
docker-compose build --parallel

echo -e "${YELLOW}▶️  اجرای containers...${NC}"
docker-compose up -d

# صبر برای آماده شدن سرویس‌ها
echo -e "${YELLOW}⏳ صبر برای آماده شدن سرویس‌ها...${NC}"
sleep 10

# نمایش وضعیت
echo -e "${GREEN}📊 وضعیت containers:${NC}"
docker-compose ps

echo -e "${GREEN}✅ دیپلوی انجام شد!${NC}"
echo ""
echo "🌐 سرویس‌ها در دسترس هستند:"
echo "  • Next.js:     http://localhost:3000"
echo "  • Nest.js:     http://localhost:3001"
echo "  • Python API:  http://localhost:5000"
echo "  • phpMyAdmin:  http://localhost:8081"
echo "  • Redis UI:    http://localhost:8082"
echo ""
echo "📝 برای مشاهده لاگ‌ها: docker-compose logs -f"