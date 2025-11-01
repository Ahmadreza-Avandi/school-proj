#!/bin/bash

# 🚀 اسکریپت دیپلوی کامل پروژه
# این اسکریپت همه چیز رو از صفر تا صد مدیریت می‌کنه

set -e  # در صورت خطا متوقف شو

# رنگ‌ها برای خروجی
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# تابع برای چاپ پیام‌ها
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

# متغیرهای پروژه
DOMAIN="sch.ahmadreza-avandi.ir"
PROJECT_DIR="$(pwd)"

print_header "🚀 شروع دیپلوی پروژه"

# ۱. بررسی وجود Docker و Docker Compose
print_header "۱. بررسی پیش‌نیازها"

if ! command -v docker &> /dev/null; then
    print_error "Docker نصب نیست!"
    exit 1
fi
print_success "Docker نصب شده است"

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose نصب نیست!"
    exit 1
fi
print_success "Docker Compose نصب شده است"

# ۲. بررسی وجود Nginx
if ! command -v nginx &> /dev/null; then
    print_warning "Nginx نصب نیست. در حال نصب..."
    sudo apt-get update
    sudo apt-get install -y nginx
    print_success "Nginx نصب شد"
else
    print_success "Nginx نصب شده است"
fi

# ۳. بررسی SSL Certificate
print_header "۲. بررسی گواهی SSL"

if [ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    print_warning "گواهی SSL برای $DOMAIN وجود ندارد"
    print_info "برای دریافت گواهی SSL دستور زیر را اجرا کنید:"
    print_info "sudo certbot --nginx -d $DOMAIN"
    read -p "آیا می‌خواهید الان گواهی SSL دریافت کنید؟ (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo certbot --nginx -d $DOMAIN
    else
        print_error "بدون SSL نمی‌توان ادامه داد"
        exit 1
    fi
else
    print_success "گواهی SSL موجود است"
fi

# ۴. توقف سرویس‌های قبلی
print_header "۳. توقف سرویس‌های قبلی"

if [ -f "docker-compose.yml" ]; then
    print_info "در حال توقف containers قبلی..."
    docker-compose down 2>/dev/null || true
    print_success "Containers قبلی متوقف شدند"
fi

# ۵. پاک‌سازی (اختیاری)
read -p "آیا می‌خواهید images قدیمی را پاک کنید؟ (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "در حال پاک‌سازی images قدیمی..."
    docker system prune -af --volumes || true
    print_success "پاک‌سازی انجام شد"
fi

# ۶. کانفیگ Nginx
print_header "۴. کانفیگ Nginx"

if [ -f "nginx-config.conf" ]; then
    print_info "در حال کپی کانفیگ Nginx..."
    
    # بکاپ از کانفیگ قبلی
    if [ -f "/etc/nginx/sites-enabled/default" ]; then
        sudo cp /etc/nginx/sites-enabled/default /etc/nginx/sites-enabled/default.backup.$(date +%Y%m%d_%H%M%S)
    fi
    
    # کپی کانفیگ جدید
    sudo cp nginx-config.conf /etc/nginx/sites-available/school-proj
    
    # ایجاد symlink
    sudo ln -sf /etc/nginx/sites-available/school-proj /etc/nginx/sites-enabled/school-proj
    
    # حذف کانفیگ default
    sudo rm -f /etc/nginx/sites-enabled/default
    
    # تست کانفیگ
    print_info "در حال تست کانفیگ Nginx..."
    if sudo nginx -t; then
        print_success "کانفیگ Nginx معتبر است"
        sudo systemctl reload nginx
        print_success "Nginx reload شد"
    else
        print_error "کانفیگ Nginx خطا دارد!"
        exit 1
    fi
else
    print_warning "فایل nginx-config.conf یافت نشد"
fi

# ۷. بیلد و اجرای Docker Containers
print_header "۵. بیلد و اجرای Docker Containers"

print_info "در حال بیلد containers (ممکن است چند دقیقه طول بکشد)..."
docker-compose build --parallel

print_success "بیلد با موفقیت انجام شد"

print_info "در حال اجرای containers..."
docker-compose up -d

print_success "Containers اجرا شدند"

# ۸. بررسی وضعیت سرویس‌ها
print_header "۶. بررسی وضعیت سرویس‌ها"

sleep 5  # صبر برای اجرای کامل سرویس‌ها

print_info "وضعیت containers:"
docker-compose ps

# ۹. بررسی سلامت سرویس‌ها
print_header "۷. بررسی سلامت سرویس‌ها"

check_service() {
    local service_name=$1
    local port=$2
    local max_attempts=30
    local attempt=1
    
    print_info "در حال بررسی $service_name..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -o /dev/null -w "%{http_code}" http://localhost:$port > /dev/null 2>&1; then
            print_success "$service_name در حال اجراست (پورت $port)"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_warning "$service_name هنوز آماده نیست (پورت $port)"
    return 1
}

check_service "Next.js" 3000
check_service "Nest.js" 3001
check_service "Python API" 5000
check_service "phpMyAdmin" 8081

# ۱۰. نمایش لاگ‌ها
print_header "۸. لاگ‌های اخیر"

print_info "لاگ‌های 20 خط آخر هر سرویس:"
echo ""
docker-compose logs --tail=20

# ۱۱. اطلاعات نهایی
print_header "✅ دیپلوی با موفقیت انجام شد!"

echo ""
print_success "پروژه شما در حال اجراست:"
echo ""
echo "  🌐 وب‌سایت اصلی:      https://$DOMAIN"
echo "  🔧 API Nest.js:        https://$DOMAIN/api"
echo "  🐍 API Python:         https://$DOMAIN/python-api"
echo "  💾 phpMyAdmin:         https://$DOMAIN/phpmyadmin"
echo "  📊 Redis Commander:    https://$DOMAIN/redis-commander"
echo ""
print_info "دستورات مفید:"
echo "  • مشاهده لاگ‌ها:       docker-compose logs -f"
echo "  • مشاهده لاگ سرویس:   docker-compose logs -f [service-name]"
echo "  • ری‌استارت:          docker-compose restart"
echo "  • توقف:               docker-compose down"
echo "  • وضعیت:              docker-compose ps"
echo ""
print_info "برای مشاهده لاگ‌های زنده:"
echo "  docker-compose logs -f"
echo ""

# ۱۲. پیشنهاد مشاهده لاگ‌ها
read -p "آیا می‌خواهید لاگ‌های زنده را مشاهده کنید؟ (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker-compose logs -f
fi
