#!/usr/bin/env python3
# faceDetectionWithCamera.py

import cv2
import numpy as np
import mysql.connector
import redis
from datetime import datetime
from persiantools.jdatetime import JalaliDateTime
import schedule
import logging
import os
import json
import requests
import tempfile
import time
from urllib.parse import urljoin
import re

# تنظیمات لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --------------------- کلاس مدیریت دوربین‌ها ---------------------
class CameraManager:
    def __init__(self):
        self.cameras = []  # لیست دوربین‌ها
        self.grid_size = (2, 2)  # تعداد ردیف و ستون در نمایش گرید
        self.active_cam = -1     # -1 یعنی نمایش گرید، غیر از -1 یعنی نمایش تمام صفحه یک دوربین
        self.window_name = "Face Recognition System"
        self.last_click = 0
        self.click_delay = 500   # میلی‌ثانیه
        
        # آدرس API - استفاده از متغیر محیطی یا آدرس پیش‌فرض
        self.api_base_url = os.environ.get('PYTHON_API_URL', 'https://a.networklearnzero.shop/python-api')
        logger.info(f"استفاده از API: {self.api_base_url}")
        
        # مسیرهای موقت برای ذخیره مدل و لیبل‌ها
        self.temp_dir = tempfile.mkdtemp()
        self.model_path = os.path.join(self.temp_dir, "model.xml")
        self.labels_path = os.path.join(self.temp_dir, "labels.json")
        self.mapping_path = os.path.join(self.temp_dir, "mapping.json")
        
        # ایجاد پوشه‌های مورد نیاز
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # دیکشنری روزهای هفته فارسی
        self.persian_days = {
            0: "شنبه",
            1: "یکشنبه",
            2: "دوشنبه",
            3: "سه‌شنبه",
            4: "چهارشنبه",
            5: "پنج‌شنبه",
            6: "جمعه"
        }

        # بارگذاری Haar Cascade جهت تشخیص چهره
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

        # تلاش برای دانلود و بارگذاری مدل از API
        self.api_available = self.check_api_connectivity()
        if self.api_available:
            logger.info("اتصال به API برقرار است. در حال دانلود مدل و فایل‌های مرتبط...")
            if self.download_model_and_labels():
                logger.info("دانلود مدل و فایل‌های مرتبط با موفقیت انجام شد.")
                self.load_face_recognizer()
            else:
                logger.warning("دانلود از API ناموفق بود. تلاش برای بارگذاری فایل‌های محلی...")
                self.load_face_recognizer_local()
        else:
            logger.warning("اتصال به API برقرار نیست. در حال بارگذاری فایل‌های محلی...")
            self.load_face_recognizer_local()

        # اتصال به دیتابیس MySQL - استفاده از متغیرهای محیطی (برای محیط سرور و داکر)
        try:
            # دریافت مقادیر از متغیرهای محیطی با مقادیر پیش‌فرض
            database_url = os.environ.get('DATABASE_URL', 'mysql://root:rootpassword@mysql:3306/mydatabase')
            
            # پارس کردن DATABASE_URL
            # فرمت: mysql://username:password@host:port/database
            db_pattern = r'mysql://([^:]+):([^@]+)@([^:/]+):?(\d*)/?(.+)?'
            match = re.match(db_pattern, database_url)
            
            if match:
                mysql_user = match.group(1)
                mysql_password = match.group(2)
                mysql_host = match.group(3)
                mysql_port = int(match.group(4) or 3306)
                mysql_database = match.group(5) or 'mydatabase'
                
                logger.info(f"اتصال به دیتابیس: {mysql_host}:{mysql_port}/{mysql_database} با کاربر {mysql_user}")
                
                self.db = mysql.connector.connect(
                    host=mysql_host,
                    user=mysql_user,
                    password=mysql_password,
                    database=mysql_database,
                    port=mysql_port
                )
                logger.info(f"اتصال به دیتابیس MySQL در {mysql_host} برقرار شد.")
            else:
                logger.error(f"فرمت DATABASE_URL نامعتبر است: {database_url}")
                self.db = None
        except mysql.connector.Error as err:
            logger.error("خطا در اتصال به دیتابیس: %s", err)
            self.db = None

        # اتصال به Redis (اختیاری) - استفاده از متغیرهای محیطی
        try:
            redis_host = os.environ.get('REDIS_HOST', 'localhost')
            redis_port = int(os.environ.get('REDIS_PORT', 6379))
            self.redis_db = redis.StrictRedis(
                host=redis_host, 
                port=redis_port, 
                db=0, 
                decode_responses=True
            )
            self.redis_db.ping()
            logger.info(f"اتصال به Redis در {redis_host}:{redis_port} برقرار شد.")
        except Exception as e:
            logger.error("خطا در اتصال به Redis: %s", e)
            self.redis_db = None

        # دیکشنری جهت جلوگیری از ثبت مکرر حضور (به مدت 2 ساعت)
        self.last_checkin = {}
        
        # تنظیم زمان‌بندی برای به‌روزرسانی مدل از API هر 30 دقیقه
        if self.api_available:
            schedule.every(30).minutes.do(self.update_model_from_api)
            logger.info("زمان‌بندی به‌روزرسانی مدل از API هر 30 دقیقه تنظیم شد.")

    def check_api_connectivity(self):
        """
        بررسی اتصال به API
        """
        try:
            response = requests.get(self.api_base_url, timeout=5)
            if response.status_code == 200:
                logger.info("اتصال به API برقرار است.")
                return True
            else:
                logger.error(f"خطا در اتصال به API: کد وضعیت {response.status_code}, پاسخ: {response.text}")
                return False
        except Exception as e:
            logger.error(f"خطا در اتصال به API: {e}")
            return False

    def download_model_and_labels(self):
        """
        دانلود مدل و فایل‌های لیبل از API
        """
        if not self.api_available:
            logger.warning("اتصال به API برقرار نیست. دانلود مدل و لیبل‌ها امکان‌پذیر نیست.")
            return False
            
        try:
            # دانلود مدل XML
            model_url = urljoin(self.api_base_url + "/", "model")
            logger.info(f"در حال دانلود مدل از {model_url}...")
            model_response = requests.get(model_url, timeout=10)
            if model_response.status_code == 200:
                with open(self.model_path, 'wb') as f:
                    f.write(model_response.content)
                logger.info("مدل XML از API دانلود شد.")
            else:
                logger.error(f"خطا در دانلود مدل از API: {model_response.status_code}, {model_response.text}")
                return False
                
            # دانلود فایل لیبل‌ها
            labels_url = urljoin(self.api_base_url + "/", "labels")
            logger.info(f"در حال دانلود لیبل‌ها از {labels_url}...")
            labels_response = requests.get(labels_url, timeout=10)
            if labels_response.status_code == 200:
                labels_data = labels_response.json()
                with open(self.labels_path, 'w', encoding='utf-8') as f:
                    json.dump(labels_data.get('labels', {}), f, ensure_ascii=False, indent=4)
                logger.info("فایل لیبل‌ها از API دانلود شد.")
            else:
                logger.error(f"خطا در دانلود لیبل‌ها از API: {labels_response.status_code}, {labels_response.text}")
                return False
                
            # دانلود فایل نگاشت برچسب‌ها
            mapping_url = urljoin(self.api_base_url + "/", "label-mapping")
            logger.info(f"در حال دانلود نگاشت برچسب‌ها از {mapping_url}...")
            mapping_response = requests.get(mapping_url, timeout=10)
            if mapping_response.status_code == 200:
                mapping_data = mapping_response.json()
                with open(self.mapping_path, 'w', encoding='utf-8') as f:
                    json.dump(mapping_data.get('mapping', {}), f, ensure_ascii=False, indent=4)
                logger.info("فایل نگاشت برچسب‌ها از API دانلود شد.")
                return True
            else:
                logger.error(f"خطا در دانلود نگاشت برچسب‌ها از API: {mapping_response.status_code}, {mapping_response.text}")
                return False
                
        except Exception as e:
            logger.error(f"خطا در دانلود فایل‌ها از API: {e}")
            return False
            
    def update_model_from_api(self):
        """
        به‌روزرسانی مدل و لیبل‌ها از API
        """
        if not self.check_api_connectivity():
            logger.warning("اتصال به API برقرار نیست. به‌روزرسانی مدل و لیبل‌ها امکان‌پذیر نیست.")
            return
            
        try:
            logger.info("در حال به‌روزرسانی مدل و لیبل‌ها از API...")
            success = self.download_model_and_labels()
            if success:
                self.load_face_recognizer()
                logger.info("مدل و لیبل‌ها با موفقیت به‌روز شدند.")
            else:
                logger.error("خطا در به‌روزرسانی مدل و لیبل‌ها از API.")
        except Exception as e:
            logger.error(f"خطا در به‌روزرسانی مدل از API: {e}")
            
    def load_face_recognizer(self):
        """
        بارگذاری مدل تشخیص چهره از فایل‌های دانلود شده از API
        """
        try:
            if not hasattr(cv2, 'face'):
                raise AttributeError("ماژول cv2.face موجود نیست. لطفاً opencv-contrib-python را نصب کنید.")
                
            self.face_recognizer = cv2.face.LBPHFaceRecognizer_create()
            
            # بررسی وجود فایل مدل
            if os.path.exists(self.model_path):
                self.face_recognizer.read(self.model_path)
                logger.info(f"مدل تشخیص چهره از {self.model_path} بارگذاری شد.")
            else:
                logger.error(f"فایل مدل در مسیر {self.model_path} یافت نشد.")
                self.face_recognizer = None
        except Exception as e:
            logger.error(f"خطا در بارگذاری مدل تشخیص چهره: {e}")
            self.face_recognizer = None
            
    def load_face_recognizer_local(self):
        """
        تلاش برای بارگذاری مدل تشخیص چهره از فایل‌های محلی
        """
        try:
            if not hasattr(cv2, 'face'):
                raise AttributeError("ماژول cv2.face موجود نیست. لطفاً opencv-contrib-python را نصب کنید.")
                
            self.face_recognizer = cv2.face.LBPHFaceRecognizer_create()
            local_model_path = "trainer/model.xml"
            
            if os.path.exists(local_model_path):
                self.face_recognizer.read(local_model_path)
                logger.info(f"مدل تشخیص چهره از فایل محلی {local_model_path} بارگذاری شد.")
                
                # بررسی وجود فایل‌های لیبل محلی
                local_labels_path = "labels/labels_to_name.json"
                local_mapping_path = "labels/label_mapping.json"
                
                if os.path.exists(local_labels_path):
                    with open(local_labels_path, 'r', encoding='utf-8') as f:
                        labels_data = json.load(f)
                    with open(self.labels_path, 'w', encoding='utf-8') as f:
                        json.dump(labels_data, f, ensure_ascii=False, indent=4)
                        
                if os.path.exists(local_mapping_path):
                    with open(local_mapping_path, 'r', encoding='utf-8') as f:
                        mapping_data = json.load(f)
                    with open(self.mapping_path, 'w', encoding='utf-8') as f:
                        json.dump(mapping_data, f, ensure_ascii=False, indent=4)
            else:
                logger.error(f"فایل مدل محلی در مسیر {local_model_path} یافت نشد.")
                self.face_recognizer = None
        except Exception as e:
            logger.error(f"خطا در بارگذاری مدل تشخیص چهره از فایل محلی: {e}")
            self.face_recognizer = None
            
    def process_faces(self, frame, location):
        """
        پردازش فریم:
          - تبدیل به تصویر خاکستری.
          - تشخیص چهره‌ها.
          - در صورت کوچک بودن چهره (به علت فاصله از لنز) تصویر چهره بزرگ‌نمایی می‌شود.
          - پیش‌بینی برچسب با استفاده از مدل آموزش‌دیده.
          - ثبت حضور در صورت تشخیص با اطمینان کافی.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # استفاده از minSize کوچکتر جهت تشخیص چهره‌های دور
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5, minSize=(20, 20))
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            face_roi = gray[y:y+h, x:x+w]

            # اگر چهره کوچک باشد، بزرگ‌نمایی می‌شود
            if w < 100 or h < 100:
                try:
                    face_roi = cv2.resize(face_roi, (w*2, h*2), interpolation=cv2.INTER_CUBIC)
                except Exception as e:
                    logger.error(f"خطا در بزرگنمایی تصویر چهره: {e}")

            if self.face_recognizer is not None:
                try:
                    # استاندارد‌سازی اندازه تصویر چهره برای تشخیص
                    face_for_recognition = cv2.resize(face_roi, (100, 100))
                    
                    # بررسی وجود فایل نگاشت برچسب‌ها
                    if not os.path.exists(self.mapping_path):
                        logger.error("فایل نگاشت برچسب‌ها یافت نشد")
                        continue
                        
                    # خواندن نگاشت برچسب‌ها
                    with open(self.mapping_path, 'r', encoding='utf-8') as f:
                        mapping_data = json.load(f)
                    
                    # پیش‌بینی چهره
                    label, confidence = self.face_recognizer.predict(face_for_recognition)
                    
                    # تنظیم آستانه دقت (مثلاً confidence کمتر از 100)
                    if confidence < 100:
                        # تبدیل برچسب عددی به کد ملی با استفاده از نگاشت
                        for national_code, label_id in mapping_data.items():
                            if int(label_id) == label:
                                self.log_attendance(national_code, location)
                                logger.info(f"تشخیص چهره با دقت {confidence}: کد ملی {national_code}")
                                # نمایش اطلاعات تشخیص روی تصویر
                                cv2.putText(frame, f"ID: {national_code}", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                                cv2.putText(frame, f"Conf: {confidence:.1f}", (x, y+h+20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                                break
                    else:
                        logger.debug(f"چهره با دقت کافی شناسایی نشد (confidence: {confidence}).")
                        cv2.putText(frame, "Unknown", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                except Exception as e:
                    logger.error(f"خطا در پیش‌بینی چهره: {e}")
        return cv2.resize(frame, (640, 480))

    def add_camera(self, name, source, location):
        """
        اضافه کردن دوربین به سیستم.
        پارامتر source می‌تواند عدد (مثلاً 0 برای وبکم) یا آدرس استریم (RTSP) باشد.
        """
        cap = cv2.VideoCapture(source)
        if cap.isOpened():
            # تشخیص اینکه آیا منبع، دوربین داخلی است یا خارجی
            is_external = not (isinstance(source, int) and source == 0)
            self.cameras.append({
                'cap': cap,
                'name': name,
                'location': location,
                'frame': None,
                'is_external': is_external
            })
            logger.info("دوربین '%s' در '%s' فعال شد.", name, location)
        else:
            logger.error("خطا در باز کردن دوربین '%s'.", name)
            cap.release()

    def adjust_focal_distance(self, frame, zoom_factor=1.5):
        """
        شبیه‌سازی زوم دیجیتال برای دوربین‌های خارجی با بریدن مرکز تصویر.
        """
        h, w = frame.shape[:2]
        new_w = int(w / zoom_factor)
        new_h = int(h / zoom_factor)
        x1 = (w - new_w) // 2
        y1 = (h - new_h) // 2
        cropped = frame[y1:y1+new_h, x1:x1+new_w]
        adjusted = cv2.resize(cropped, (640, 480))
        return adjusted

    def update_frames(self):
        """
        به‌روز رسانی فریم‌های هر دوربین:
          - دریافت فریم از دوربین.
          - اعمال تنظیم فاصله کانونی برای دوربین‌های خارجی.
          - پردازش فریم جهت تشخیص چهره.
          - در صورت عدم دریافت فریم، استفاده از یک فریم سیاه.
        """
        for cam in self.cameras:
            ret, frame = cam['cap'].read()
            if ret:
                if cam.get('is_external', False):
                    frame = self.adjust_focal_distance(frame, zoom_factor=1.5)
                cam['frame'] = self.process_faces(frame, cam['location'])
            else:
                cam['frame'] = np.zeros((480, 640, 3), dtype=np.uint8)

    def toggle_fullscreen(self, x, y):
        """
        تغییر حالت نمایش از گرید به تمام صفحه و بالعکس با دابل کلیک ماوس.
        """
        current_time = cv2.getTickCount()
        if (current_time - self.last_click) * 1000 / cv2.getTickFrequency() < self.click_delay:
            return

        if self.active_cam == -1:
            # تعیین دوربین کلیک‌شده بر اساس مختصات (با فرض ابعاد ثابت هر فریم 640x480 و فاصله 10 پیکسل)
            col = x // (640 + 10)
            row = y // (480 + 10)
            idx = row * self.grid_size[1] + col
            if idx < len(self.cameras):
                self.active_cam = idx
        else:
            self.active_cam = -1
        self.last_click = current_time

    def show_interface(self):
        """
        نمایش رابط کاربری:
          - در حالت تمام صفحه، فریم یک دوربین نمایش داده می‌شود.
          - در حالت گرید، فریم‌های تمام دوربین‌ها به صورت شبکه‌ای نمایش داده می‌شود.
        """
        if self.active_cam != -1:
            frame = self.cameras[self.active_cam]['frame']
            cv2.imshow(self.window_name, frame)
        else:
            if not self.cameras:
                black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.imshow(self.window_name, black_frame)
                return

            grid_frames = []
            for i in range(0, len(self.cameras), self.grid_size[1]):
                row_frames = [cam['frame'] if cam['frame'] is not None
                              else np.zeros((480, 640, 3), dtype=np.uint8)
                              for cam in self.cameras[i:i+self.grid_size[1]]]
                while len(row_frames) < self.grid_size[1]:
                    row_frames.append(np.zeros((480, 640, 3), dtype=np.uint8))
                grid_frames.append(np.hstack(row_frames))
            final_grid = np.vstack(grid_frames[:self.grid_size[0]])
            cv2.imshow(self.window_name, final_grid)

    def log_attendance(self, national_code, location):
        """ثبت حضور دانش آموز در دیتابیس"""
        if self.db is None:
            logger.error("اتصال به دیتابیس برقرار نیست")
            return
        
        now = datetime.now()
        jalali_date = JalaliDateTime.now()
        
        try:
            with self.db.cursor() as cursor:
                # ابتدا بررسی کنیم که جدول مورد نظر در دیتابیس وجود دارد یا نه
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = DATABASE()
                    AND table_name = 'user'
                """)
                if cursor.fetchone()[0] == 0:
                    logger.warning("جدول user در دیتابیس وجود ندارد. در حال ساخت جدول...")
                    # ایجاد جدول user در صورت عدم وجود
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS user (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            nationalCode VARCHAR(20) UNIQUE,
                            fullName VARCHAR(100),
                            classId INT,
                            INDEX (nationalCode)
                        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                    """)
                    
                    # ایجاد جدول class در صورت عدم وجود
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS class (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            name VARCHAR(100)
                        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                    """)
                    
                    # ایجاد جدول attendance در صورت عدم وجود
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS attendance (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            nationalCode VARCHAR(20),
                            fullName VARCHAR(100),
                            classId INT,
                            className VARCHAR(100),
                            jalali_date VARCHAR(20),
                            gregorian_date DATE,
                            checkin_time TIME,
                            location VARCHAR(100),
                            dayOfWeek VARCHAR(20),
                            status VARCHAR(20),
                            INDEX (nationalCode),
                            INDEX (gregorian_date)
                        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                    """)
                    
                    # ایجاد جدول last_seen در صورت عدم وجود
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS last_seen (
                            nationalCode VARCHAR(20) PRIMARY KEY,
                            fullName VARCHAR(100),
                            checkin_time VARCHAR(30),
                            location VARCHAR(100)
                        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                    """)
                    
                    self.db.commit()
                    logger.info("جداول مورد نیاز در دیتابیس ایجاد شدند.")
                
                # دریافت اطلاعات کاربر و کلاس
                cursor.execute("""
                    SELECT u.fullName, u.classId, c.name as className 
                    FROM user u 
                    LEFT JOIN class c ON u.classId = c.id 
                    WHERE u.nationalCode = %s
                """, (national_code,))
                
                user_info = cursor.fetchone()
                if not user_info:
                    logger.warning(f"کاربر با کد ملی {national_code} یافت نشد. در حال ثبت اطلاعات اولیه...")
                    # اگر کاربر وجود نداشت، اطلاعات اولیه را ثبت می‌کنیم
                    cursor.execute("""
                        INSERT INTO user (nationalCode, fullName) 
                        VALUES (%s, %s)
                    """, (national_code, f"کاربر {national_code}"))
                    self.db.commit()
                    
                    full_name = f"کاربر {national_code}"
                    class_id = None
                    class_name = None
                else:
                    full_name, class_id, class_name = user_info
                
                # تعیین روز هفته به فارسی
                day_of_week = self.persian_days[jalali_date.weekday()]
                
                # تبدیل تاریخ جلالی به فرمت مورد نیاز
                jalali_date_str = jalali_date.strftime("%Y/%m/%d")  # مثال: 1402/01/15
                
                # بررسی تکراری نبودن حضور در روز جاری
                cursor.execute("""
                    SELECT id FROM attendance 
                    WHERE nationalCode = %s 
                    AND gregorian_date = CURDATE()
                """, (national_code,))
                
                attendance_record = cursor.fetchone()
                if attendance_record:
                    # آپدیت رکورد موجود
                    cursor.execute("""
                        UPDATE attendance 
                        SET checkin_time = %s, 
                            location = %s,
                            status = 'present'
                        WHERE id = %s
                    """, (
                        now.strftime('%H:%M:%S'),
                        class_name or location,
                        attendance_record[0]
                    ))
                    self.db.commit()
                    logger.info(f"رکورد حضور برای {full_name} به‌روزرسانی شد")
                else:
                    # استفاده از نام کلاس به عنوان لوکیشن اگر موجود باشد
                    actual_location = class_name if class_name else location
                        
                    # ثبت حضور جدید
                    cursor.execute("""
                        INSERT INTO attendance (
                            nationalCode, 
                            fullName,
                            classId,
                            className, 
                            jalali_date,           -- تاریخ جلالی
                            gregorian_date,        -- تاریخ میلادی
                            checkin_time,
                            location,
                            dayOfWeek,
                            status
                        ) VALUES (%s, %s, %s, %s, %s, CURDATE(), %s, %s, %s, 'present')
                    """, (
                        national_code,
                        full_name,
                        class_id,
                        class_name,
                        jalali_date_str,          # تاریخ جلالی
                        now.strftime('%H:%M:%S'), # زمان ورود
                        actual_location,
                        day_of_week
                    ))
                    
                    self.db.commit()
                    logger.info(f"حضور برای {full_name} در {actual_location} ثبت شد")
                
                # آپدیت last_seen
                self.update_last_seen(national_code, full_name, now, class_name or location)
                
        except mysql.connector.Error as err:
            logger.error(f"خطای دیتابیس: {err}")
            self.db.rollback()

    def update_last_seen(self, national_code, full_name, timestamp, location):
        """به‌روزرسانی آخرین وضعیت مشاهده کاربر"""
        try:
            jalali_datetime = JalaliDateTime.now().strftime("%Y/%m/%d %H:%M:%S")
            
            with self.db.cursor() as cursor:
                # بررسی وجود جدول
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = DATABASE()
                    AND table_name = 'last_seen'
                """)
                if cursor.fetchone()[0] == 0:
                    # ایجاد جدول last_seen در صورت عدم وجود
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS last_seen (
                            nationalCode VARCHAR(20) PRIMARY KEY,
                            fullName VARCHAR(100),
                            checkin_time VARCHAR(30),
                            location VARCHAR(100)
                        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                    """)
                    self.db.commit()
                    
                cursor.execute("""
                    INSERT INTO last_seen 
                    (nationalCode, fullName, checkin_time, location)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    fullName = VALUES(fullName),
                    checkin_time = VALUES(checkin_time),
                    location = VALUES(location)
                """, (
                    national_code,
                    full_name,
                    jalali_datetime,
                    location
                ))
                self.db.commit()
                logger.info(f"last_seen برای {full_name} به‌روزرسانی شد")
        except mysql.connector.Error as err:
            logger.error(f"خطا در به‌روزرسانی last_seen: {err}")
            self.db.rollback()

# --------------------- تابع اصلی ---------------------
def main():
    manager = CameraManager()

    # اضافه کردن دوربین‌ها:
    manager.add_camera("دوربین لپتاپ", 0, "لپتاپ")
    # مثال اضافه کردن دوربین خارجی (در صورت وجود):
    #manager.add_camera(" 12 مکا", "rtsp://admin:@192.168.1.168:80/ch0_0.264", "12 مکا")

    # زمان‌بندی پاکسازی دیکشنری حضور (هر 2 ساعت) جهت جلوگیری از ثبت مکرر
    schedule.every(2).hours.do(manager.last_checkin.clear)

    # تنظیم رویداد ماوس برای تغییر حالت نمایش (دابل کلیک)
    def mouse_handler(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDBLCLK:
            manager.toggle_fullscreen(x, y)

    cv2.namedWindow(manager.window_name, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(manager.window_name, mouse_handler)

    try:
        while True:
            manager.update_frames()
            manager.show_interface()
            schedule.run_pending()
            if cv2.waitKey(1) == 27:  # خروج با کلید ESC
                break
    finally:
        for cam in manager.cameras:
            cam['cap'].release()
        cv2.destroyAllWindows()
        if manager.db:
            manager.db.close()

if __name__ == '__main__':
    main()
