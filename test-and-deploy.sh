#!/bin/bash

# 🚀 اسکریپت تست و دیپلوی کامل
set -e

# رنگ‌ها
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

DOMAIN="sch.ahmadreza-avandi.ir"

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_header "🚀 تست و دیپلوی پروژه روی $DOMAIN"

# ۱. بررسی فایل‌های ضروری
print_header "۱. بررسی فایل‌های ضروری"

required_files=(
    "docker-compose.yml"
    "nginx-config.conf"
    "nest/Dockerfile"
    "next/Dockerfile"
    "faceDetectionWithCamera/Dockerfile"
    "mydatabase (3).sql"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        print_success "فایل $file موجود است"
    else
        print_error "فایل $file موجود نیست!"
        exit 1
    fi
done

# ۲. بررسی syntax فایل‌ها
print_header "۲. بررسی syntax فایل‌ها"

print_info "بررسی docker-compose.yml..."
if docker-compose config > /dev/null 2>&1; then
    print_success "docker-compose.yml معتبر است"
else
    print_error "docker-compose.yml خطا دارد!"
    docker-compose config
    exit 1
fi

print_info "بررسی nginx config..."
if nginx -t -c $(pwd)/nginx-config.conf > /dev/null 2>&1; then
    print_success "nginx config معتبر است"
else
    print_warning "nginx config ممکن است مشکل داشته باشد (نادیده گرفته می‌شود)"
fi

# ۳. توقف سرویس‌های قبلی
print_header "۳. توقف سرویس‌های قبلی"
docker-compose down 2>/dev/null || true
print_success "سرویس‌های قبلی متوقف شدند"

# ۴. پاک‌سازی (اختیاری)
read -p "آیا می‌خواهید images و volumes قدیمی را پاک کنید؟ (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "پاک‌سازی images و volumes قدیمی..."
    docker system prune -af --volumes || true
    print_success "پاک‌سازی انجام شد"
fi

# ۵. بیلد containers
print_header "۴. بیلد containers"
print_info "شروع بیلد (ممکن است چند دقیقه طول بکشد)..."

# بیلد به صورت موازی
if docker-compose build --parallel; then
    print_success "همه containers با موفقیت build شدند"
else
    print_warning "بیلد موازی با خطا مواجه شد. تلاش مجدد به صورت تک به تک..."
    if docker-compose build; then
        print_success "containers با موفقیت build شدند"
    else
        print_error "بیلد با خطا مواجه شد!"
        exit 1
    fi
fi

# ۶. اجرای containers
print_header "۵. اجرای containers"
print_info "شروع اجرای containers..."

if docker-compose up -d; then
    print_success "همه containers اجرا شدند"
else
    print_error "اجرای containers با خطا مواجه شد!"
    exit 1
fi

# ۷. صبر برای آماده شدن سرویس‌ها
print_header "۶. صبر برای آماده شدن سرویس‌ها"
print_info "صبر برای آماده شدن سرویس‌ها (30 ثانیه)..."
sleep 30

# ۸. بررسی وضعیت containers
print_header "۷. بررسی وضعیت containers"
docker-compose ps

# ۹. تست سرویس‌ها
print_header "۸. تست سرویس‌ها"

test_service() {
    local service_name=$1
    local port=$2
    local path=${3:-""}
    local max_attempts=10
    local attempt=1
    
    print_info "تست $service_name..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$port$path" | grep -q "200\|302\|404"; then
            print_success "$service_name در حال اجراست ✓"
            return 0
        fi
        echo -n "."
        sleep 3
        attempt=$((attempt + 1))
    done
    
    print_warning "$service_name هنوز آماده نیست"
    return 1
}

# تست سرویس‌ها
test_service "Next.js" 3000
test_service "Nest.js API" 3001
test_service "Python API" 5000
test_service "phpMyAdmin" 8081
test_service "Redis Commander" 8082

# ۱۰. نمایش لاگ‌های اخیر
print_header "۹. لاگ‌های اخیر"
print_info "آخرین لاگ‌های هر سرویس:"
echo ""

services=("mysql" "redis" "nestjs" "nextjs" "pythonserver" "phpmyadmin" "redis-commander")

for service in "${services[@]}"; do
    echo -e "${YELLOW}=== $service ===${NC}"
    docker-compose logs --tail=5 "$service" 2>/dev/null || echo "سرویس $service در حال اجرا نیست"
    echo ""
done

# ۱۱. اطلاعات نهایی
print_header "✅ تست و دیپلوی با موفقیت انجام شد!"

echo ""
print_success "🌐 پروژه شما آماده است:"
echo ""
echo "  🏠 وب‌سایت اصلی:      https://$DOMAIN"
echo "  🔧 API Nest.js:        https://$DOMAIN/api"
echo "  🐍 API Python:         https://$DOMAIN/python-api"
echo "  💾 phpMyAdmin:         https://$DOMAIN/phpmyadmin"
echo "  📊 Redis Commander:    https://$DOMAIN/redis-commander"
echo ""
echo "  📍 تست محلی:"
echo "  🏠 Next.js:            http://localhost:3000"
echo "  🔧 Nest.js:            http://localhost:3001"
echo "  🐍 Python:             http://localhost:5000"
echo "  💾 phpMyAdmin:         http://localhost:8081"
echo "  📊 Redis:              http://localhost:8082"
echo ""

print_info "دستورات مفید:"
echo "  • مشاهده لاگ‌ها:       docker-compose logs -f"
echo "  • مشاهده لاگ سرویس:   docker-compose logs -f [service-name]"
echo "  • ری‌استارت:          docker-compose restart"
echo "  • توقف:               docker-compose down"
echo "  • وضعیت:              docker-compose ps"
echo ""

# ۱۲. پیشنهاد مشاهده لاگ‌ها
read -p "آیا می‌خواهید لاگ‌های زنده را مشاهده کنید؟ (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "نمایش لاگ‌های زنده (Ctrl+C برای خروج)..."
    docker-compose logs -f
fi

print_success "🎉 همه چیز آماده است!"