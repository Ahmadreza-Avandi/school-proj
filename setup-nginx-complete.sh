#!/bin/bash

# اسکریپت کامل نصب و کانفیگ Nginx

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

print_header "🔧 نصب و کانفیگ Nginx برای $DOMAIN"

# ۱. بررسی وجود Nginx
print_header "۱. بررسی و نصب Nginx"

if ! command -v nginx &> /dev/null; then
    print_warning "Nginx نصب نیست. در حال نصب..."
    sudo apt-get update
    sudo apt-get install -y nginx
    print_success "Nginx نصب شد"
else
    print_success "Nginx قبلاً نصب شده است"
fi

# ۲. بررسی وجود فایل کانفیگ
if [ ! -f "nginx-config.conf" ]; then
    print_error "فایل nginx-config.conf یافت نشد!"
    exit 1
fi

print_success "فایل nginx-config.conf موجود است"

# ۳. بکاپ از کانفیگ قبلی
print_header "۲. بکاپ از کانفیگ قبلی"

if [ -f "/etc/nginx/sites-enabled/default" ]; then
    backup_file="/etc/nginx/sites-enabled/default.backup.$(date +%Y%m%d_%H%M%S)"
    sudo cp /etc/nginx/sites-enabled/default "$backup_file"
    print_success "بکاپ ایجاد شد: $backup_file"
fi

# ۴. کپی کانفیگ جدید
print_header "۳. کپی کانفیگ جدید"

sudo cp nginx-config.conf /etc/nginx/sites-available/school-proj
print_success "کانفیگ کپی شد"

# ۵. ایجاد symlink
sudo ln -sf /etc/nginx/sites-available/school-proj /etc/nginx/sites-enabled/school-proj
print_success "Symlink ایجاد شد"

# ۶. حذف کانفیگ default
sudo rm -f /etc/nginx/sites-enabled/default
print_success "کانفیگ default حذف شد"

# ۷. تست کانفیگ
print_header "۴. تست کانفیگ Nginx"

if sudo nginx -t; then
    print_success "کانفیگ Nginx معتبر است"
else
    print_error "کانفیگ Nginx خطا دارد!"
    exit 1
fi

# ۸. ری‌لود Nginx
print_header "۵. ری‌لود Nginx"

if sudo systemctl reload nginx; then
    print_success "Nginx reload شد"
else
    print_error "خطا در reload کردن Nginx"
    exit 1
fi

# ۹. بررسی وضعیت Nginx
print_header "۶. بررسی وضعیت Nginx"

if sudo systemctl is-active --quiet nginx; then
    print_success "Nginx در حال اجراست"
else
    print_warning "Nginx در حال اجرا نیست. تلاش برای شروع..."
    sudo systemctl start nginx
    if sudo systemctl is-active --quiet nginx; then
        print_success "Nginx شروع شد"
    else
        print_error "خطا در شروع Nginx"
        exit 1
    fi
fi

# ۱۰. بررسی SSL
print_header "۷. بررسی SSL"

if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    print_success "گواهی SSL برای $DOMAIN موجود است"
    
    # بررسی تاریخ انقضا
    expiry_date=$(sudo openssl x509 -enddate -noout -in "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" | cut -d= -f2)
    print_info "تاریخ انقضا SSL: $expiry_date"
else
    print_warning "گواهی SSL برای $DOMAIN موجود نیست"
    print_info "برای دریافت گواهی SSL دستور زیر را اجرا کنید:"
    print_info "sudo certbot --nginx -d $DOMAIN"
    
    read -p "آیا می‌خواهید الان گواهی SSL دریافت کنید؟ (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if command -v certbot &> /dev/null; then
            sudo certbot --nginx -d $DOMAIN
        else
            print_error "Certbot نصب نیست. ابتدا آن را نصب کنید:"
            print_info "sudo apt-get install certbot python3-certbot-nginx"
        fi
    fi
fi

print_header "✅ نصب و کانفیگ Nginx تکمیل شد!"

echo ""
print_success "🌐 Nginx آماده است:"
echo "  • دامنه: https://$DOMAIN"
echo "  • کانفیگ: /etc/nginx/sites-available/school-proj"
echo "  • لاگ‌ها: /var/log/nginx/"
echo ""

print_info "دستورات مفید:"
echo "  • تست کانفیگ:        sudo nginx -t"
echo "  • ری‌لود:             sudo systemctl reload nginx"
echo "  • ری‌استارت:          sudo systemctl restart nginx"
echo "  • وضعیت:              sudo systemctl status nginx"
echo "  • مشاهده لاگ خطا:     sudo tail -f /var/log/nginx/error.log"
echo ""