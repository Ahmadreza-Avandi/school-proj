#!/bin/bash

# 🔧 حل مشکل Docker Hub rate limit

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔧 حل مشکل Docker Hub...${NC}"

# روش ۱: استفاده از mirror ایرانی
echo ""
echo -e "${YELLOW}روش ۱: استفاده از Docker Registry ایرانی${NC}"
echo ""

# ایجاد یا ویرایش daemon.json
DAEMON_FILE="/etc/docker/daemon.json"

if [ -f "$DAEMON_FILE" ]; then
    echo "بکاپ از فایل قبلی..."
    sudo cp $DAEMON_FILE ${DAEMON_FILE}.backup.$(date +%Y%m%d_%H%M%S)
fi

# ایجاد کانفیگ جدید با mirror های ایرانی
echo "ایجاد کانفیگ جدید..."
sudo tee $DAEMON_FILE > /dev/null <<EOF
{
  "registry-mirrors": [
    "https://registry.docker.ir",
    "https://docker.arvancloud.ir"
  ],
  "insecure-registries": [],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

echo -e "${GREEN}✅ کانفیگ Docker ایجاد شد${NC}"

# ری‌استارت Docker
echo ""
echo "ری‌استارت Docker daemon..."
sudo systemctl restart docker

echo "صبر برای آماده شدن Docker..."
sleep 5

# بررسی وضعیت
if sudo systemctl is-active --quiet docker; then
    echo -e "${GREEN}✅ Docker با موفقیت ری‌استارت شد${NC}"
else
    echo -e "${RED}❌ مشکل در ری‌استارت Docker${NC}"
    exit 1
fi

# تست
echo ""
echo "تست دانلود image..."
if docker pull hello-world; then
    echo -e "${GREEN}✅ اتصال به Docker Registry برقرار است${NC}"
else
    echo -e "${YELLOW}⚠️  هنوز مشکل وجود دارد${NC}"
    echo ""
    echo "روش‌های جایگزین:"
    echo "1. استفاده از VPN"
    echo "2. استفاده از Shecan DNS: 178.22.122.100"
    echo "3. صبر چند دقیقه و دوباره تلاش"
fi

echo ""
echo -e "${BLUE}حالا می‌توانید deploy.sh را اجرا کنید${NC}"
