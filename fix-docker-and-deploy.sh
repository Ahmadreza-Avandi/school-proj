#!/bin/bash

# 🔧 حل مشکل Docker rate limit و دیپلوی

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  🔧 حل مشکل Docker و دیپلوی پروژه${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ۱. پاک کردن کانفیگ‌های Nginx تکراری
echo -e "${YELLOW}⚠️  حذف کانفیگ‌های تکراری Nginx...${NC}"

# حذف کانفیگ certbot قدیمی که conflict داره
if [ -f "/etc/nginx/sites-enabled/default" ]; then
    sudo rm -f /etc/nginx/sites-enabled/default
    echo -e "${GREEN}✅ کانفیگ default حذف شد${NC}"
fi

# فقط کانفیگ جدید رو نگه دار
if [ -f "nginx-config.conf" ]; then
    sudo cp nginx-config.conf /etc/nginx/sites-available/school-proj
    sudo ln -sf /etc/nginx/sites-available/school-proj /etc/nginx/sites-enabled/school-proj
    echo -e "${GREEN}✅ کانفیگ جدید اعمال شد${NC}"
fi

# تست و reload
sudo nginx -t && sudo systemctl reload nginx
echo -e "${GREEN}✅ Ngin