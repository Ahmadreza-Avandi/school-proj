#!/bin/bash

# اسکریپت برای کانفیگ Nginx روی سرور

echo "🔧 Setting up Nginx configuration..."

# بکاپ از کانفیگ قبلی
sudo cp /etc/nginx/sites-enabled/default /etc/nginx/sites-enabled/default.backup

# کپی کانفیگ جدید
sudo cp nginx-config.conf /etc/nginx/sites-available/school-proj

# ایجاد symlink
sudo ln -sf /etc/nginx/sites-available/school-proj /etc/nginx/sites-enabled/school-proj

# حذف کانفیگ default قدیمی
sudo rm -f /etc/nginx/sites-enabled/default

# تست کانفیگ Nginx
echo "🧪 Testing Nginx configuration..."
sudo nginx -t

if [ $? -eq 0 ]; then
    echo "✅ Nginx configuration is valid"
    echo "🔄 Reloading Nginx..."
    sudo systemctl reload nginx
    echo "✅ Nginx reloaded successfully!"
    echo ""
    echo "📋 Next steps:"
    echo "1. Run: docker-compose up -d"
    echo "2. Check logs: docker-compose logs -f"
    echo "3. Visit: https://sch.ahmadreza-avandi.ir"
else
    echo "❌ Nginx configuration has errors!"
    echo "Restoring backup..."
    sudo cp /etc/nginx/sites-enabled/default.backup /etc/nginx/sites-enabled/default
    exit 1
fi
