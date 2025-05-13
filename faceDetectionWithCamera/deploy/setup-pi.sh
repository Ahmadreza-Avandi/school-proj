#!/bin/bash

# به روزرسانی سیستم
sudo apt-get update && sudo apt-get upgrade -y

# نصب پیش نیازهای سیستمی
sudo apt-get install -y \
    python3-pip \
    libatlas-base-dev \
    libjasper-dev \
    libqtgui4 \
    libqt4-test \
    libhdf5-dev \
    libhdf5-serial-dev \
    libatlas-base-dev \
    libjasper-dev \
    libopenblas-dev \
    libopenmpi-dev \
    libgtk-3-dev

# ایجاد پوشه‌های ضروری
mkdir -p ../trainer ../assets ../logs
chmod 775 ../trainer ../assets ../logs

# نصب وابستگی‌های پایتون با بهینه‌سازی برای ARM
pip3 install --no-cache-dir --break-system-packages \
    numpy==1.23.5 \
    opencv-contrib-python-headless==4.8.0.76 \
    imutils==0.5.4 \
    pyzmq==25.1.2 \
    protobuf==3.20.3

# تنظیم مجوزهای پیشرفته
sudo usermod -a -G video,gpio,i2c $USER
sudo chmod 775 /var/run/dbus \
    /sys/class/gpio \
    /dev/i2c-* \
    /dev/vchiq

# نصب وابستگی‌های پایتون
pip3 install -r ../requirements.txt

# تنظیم مجوزهای لازم
sudo usermod -a -G video $USER
chmod +x ../face_detection.py

echo 'نصب با موفقیت انجام شد! سرویس سیستم با دستور زیر قابل فعال سازی است:\nsudo systemctl enable face-detection.service'