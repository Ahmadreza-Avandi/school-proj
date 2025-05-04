#!/usr/bin/env python3
# faceDetectionWithCamera.py

import cv2
import numpy as np
import mysql.connector
import redis
import os
import json
import requests
import tempfile
import paramiko
import time
import shutil
from datetime import datetime
from persiantools.jdatetime import JalaliDateTime
import schedule
import logging

# تنظیمات لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# آدرس API سرور
API_BASE_URL = os.environ.get("PYTHON_API_URL", "https://a.networklearnzero.shop/python-api")

# تنظیمات دیتابیس
DB_CONFIG = {
    'host': '91.107.165.2',
    'database': os.environ.get("MYSQL_DATABASE", "mydatabase"),
    'user': os.environ.get("MYSQL_USER", "user"),
    'password': os.environ.get("MYSQL_PASSWORD", "userpassword"),
}

# --------------------- تنظیمات دسترسی به سرور و داکر ---------------------
VPS_CONFIG = {
    'host': '91.107.165.2',
    'username': 'root',
    'password': 'zerok1385',
    'docker_container': 'school-proj_pythonserver_1',  # نام کانتینر پایتون
    'model_path': '/app/trainer/model.xml',            # مسیر فایل مدل در کانتینر
    'label_mapping_path': '/app/labels/label_mapping.json',  # مسیر فایل نگاشت برچسب‌ها
    'labels_to_name_path': '/app/labels/labels_to_name.json'  # مسیر فایل نگاشت برچسب‌ها به نام
}

# --------------------- کلاس دانلود فایل‌های از VPS ---------------------
class ModelDownloader:
    def __init__(self, config):
        self.config = config
        self.ssh_client = None
        # حذف مسیر downloaded_models
        # os.makedirs(self.local_dir, exist_ok=True)

    def connect(self):
        """Establish SSH connection to the server"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(
                hostname=self.config['host'],
                username=self.config['username'],
                password=self.config['password'],
                timeout=10
            )
            logger.info("SSH connection to server established successfully.")
            return True
        except Exception as e:
            logger.error("Error establishing SSH connection to server: %s", e)
            return False

    def download_file_from_container(self, container_path, local_path):
        """دانلود فایل از کانتینر داکر به مسیر دلخواه"""
        if not self.ssh_client:
            if not self.connect():
                return None

        try:
            temp_dir = "/tmp"
            remote_temp_file = f"{temp_dir}/{os.path.basename(container_path)}"
            docker_cp_cmd = f"docker cp {self.config['docker_container']}:{container_path} {remote_temp_file}"
            stdin, stdout, stderr = self.ssh_client.exec_command(docker_cp_cmd)
            exit_status = stdout.channel.recv_exit_status()

            if exit_status != 0:
                error = stderr.read().decode('utf-8')
                logger.error("خطا در کپی فایل از کانتینر: %s", error)
                return None

            # دانلود فایل از سرور به سیستم محلی با SFTP
            sftp = self.ssh_client.open_sftp()
            sftp.get(remote_temp_file, local_path)
            sftp.close()

            self.ssh_client.exec_command(f"rm {remote_temp_file}")

            logger.info("فایل %s با موفقیت دانلود شد.", os.path.basename(local_path))
            return local_path
        except Exception as e:
            logger.error("خطا در دانلود فایل %s: %s", local_path, e)
            return None

    def download_all_model_files(self):
        """دانلود تمام فایل‌های مدل از کانتینر به مسیرهای اصلی پروژه"""
        if not self.connect():
            return None, None, None

        try:
            # ایجاد پوشه‌های مورد نیاز
            base_dir = os.path.dirname(os.path.abspath(__file__))
            trainer_dir = os.path.join(base_dir, 'trainer')
            labels_dir = os.path.join(base_dir, 'labels')
            
            os.makedirs(trainer_dir, exist_ok=True)
            os.makedirs(labels_dir, exist_ok=True)
            
            # مسیرهای مقصد
            model_path = self.download_file_from_container(
                self.config['model_path'],
                os.path.join(trainer_dir, 'model.xml')
            )
            
            # اگر فایل label_mapping.json وجود ندارد، یک فایل خالی ایجاد می‌کنیم
            mapping_path = os.path.join(labels_dir, 'label_mapping.json')
            if not os.path.exists(mapping_path):
                with open(mapping_path, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
                logger.info("فایل label_mapping.json ایجاد شد.")
            
            labels_path = self.download_file_from_container(
                self.config['labels_to_name_path'],
                os.path.join(labels_dir, 'labels_to_name.json')
            )

            self.disconnect()
            return model_path, mapping_path, labels_path
        except Exception as e:
            logger.error("خطا در دانلود فایل‌های مدل: %s", e)
            self.disconnect()
            return None, None, None

    def disconnect(self):
        """قطع اتصال SSH"""
        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None

# --------------------- کلاس مدیریت دوربین‌ها ---------------------
class CameraManager:
    def __init__(self):
        self.cameras = []  # لیست دوربین‌ها
        self.grid_size = (2, 2)  # تعداد ردیف و ستون در نمایش گرید
        self.active_cam = -1     # -1 یعنی نمایش گرید، غیر از -1 یعنی نمایش تمام صفحه یک دوربین
        self.window_name = "Face Recognition System"
        self.last_click = 0
        self.click_delay = 500   # میلی‌ثانیه
        
        # دیکشنری جهت جلوگیری از ثبت مکرر حضور (به مدت 2 ساعت)
        self.last_checkin = {}
    
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
    
        # ایجاد دانلودر برای فایل‌های مدل از VPS
        self.downloader = ModelDownloader(VPS_CONFIG)
        
        # ایجاد پوشه‌های مورد نیاز
        base_dir = os.path.dirname(os.path.abspath(__file__))
        os.makedirs(os.path.join(base_dir, 'trainer'), exist_ok=True)
        os.makedirs(os.path.join(base_dir, 'labels'), exist_ok=True)
        
        # ابتدا سعی می‌کنیم از VPS دریافت کنیم
        logger.info("تلاش برای دریافت مدل از VPS...")
        self.face_recognizer, self.label_mapping, self.labels_to_name = self.load_model_from_vps()
        
        # اتصال به دیتابیس MySQL
        try:
            self.db = mysql.connector.connect(**DB_CONFIG)
            logger.info("اتصال به دیتابیس MySQL برقرار شد.")
        except mysql.connector.Error as err:
            logger.error("خطا در اتصال به دیتابیس: %s", err)
            self.db = None
    
            # اتصال به Redis (اختیاری)
            try:
                self.redis_db = redis.StrictRedis(
                    host=os.environ.get("REDIS_HOST", "localhost"), 
                    port=int(os.environ.get("REDIS_PORT", "6379")), 
                    db=0, 
                    decode_responses=True
                )
                logger.info("اتصال به Redis برقرار شد.")
            except Exception as e:
                logger.error("خطا در اتصال به Redis: %s", e)
                self.redis_db = None
    
                # زمانبندی بررسی بروزرسانی‌های مدل - هر 30 دقیقه یکبار
                schedule.every(30).minutes.do(self.check_for_model_updates)

    def load_model_from_vps(self):
        """دریافت مدل و فایل‌های مربوطه از VPS"""
        model_path, mapping_path, labels_path = self.downloader.download_all_model_files()
        
        # بارگذاری مدل تشخیص چهره
        face_recognizer = None
        if model_path and os.path.exists(model_path):
            try:
                if not hasattr(cv2, 'face'):
                    raise AttributeError("ماژول cv2.face موجود نیست. لطفاً opencv-contrib-python را نصب کنید.")
                face_recognizer = cv2.face.LBPHFaceRecognizer_create()
                face_recognizer.read(model_path)
                logger.info("مدل تشخیص چهره از VPS بارگذاری شد.")
            except Exception as e:
                logger.error("خطا در بارگذاری مدل تشخیص چهره: %s", e)
        
        # بارگذاری نگاشت برچسب‌ها
        label_mapping = {}
        base_dir = os.path.dirname(os.path.abspath(__file__))
        mapping_path = os.path.join(base_dir, 'labels', 'label_mapping.json')
        if os.path.exists(mapping_path):
            try:
                with open(mapping_path, 'r', encoding='utf-8') as f:
                    label_mapping = json.load(f)
                logger.info("فایل نگاشت برچسب‌ها بارگذاری شد.")
            except Exception as e:
                logger.error("خطا در بارگذاری نگاشت برچسب‌ها: %s", e)
        else:
            # ایجاد فایل خالی
            with open(mapping_path, 'w', encoding='utf-8') as f:
                json.dump({}, f)
            logger.info("فایل نگاشت برچسب‌ها ایجاد شد.")
        
        # بارگذاری نگاشت برچسب‌ها به نام
        labels_to_name = {}
        labels_path = os.path.join(base_dir, 'labels', 'labels_to_name.json')
        if labels_path and os.path.exists(labels_path):
            try:
                with open(labels_path, 'r', encoding='utf-8') as f:
                    labels_to_name = json.load(f)
                logger.info("فایل نگاشت برچسب‌ها به نام بارگذاری شد.")
            except Exception as e:
                logger.error("خطا در بارگذاری نگاشت برچسب‌ها به نام: %s", e)
        
        return face_recognizer, label_mapping, labels_to_name

    def check_for_model_updates(self):
        """بررسی و دریافت بروزرسانی‌های مدل از API"""
        try:
            logger.info("بررسی بروزرسانی‌های مدل از API...")
            
            # بررسی وضعیت فایل‌ها در سرور
            check_url = f"{API_BASE_URL}/check-model"
            response = requests.get(check_url)
            
            if response.status_code != 200:
                logger.error("خطا در بررسی وضعیت مدل: کد وضعیت %s", response.status_code)
                return
            
            data = response.json()
            if data.get("status") != "success":
                logger.error("خطا در بررسی وضعیت مدل: %s", data.get("message", "خطای نامشخص"))
                return
            
            file_status = data.get("file_status", {})
            
            # اگر همه فایل‌ها در سرور موجود باشند، آنها را دانلود می‌کنیم
            if file_status.get("model_exists") and file_status.get("mapping_exists") and file_status.get("labels_exists"):
                face_recognizer, label_mapping, labels_to_name = self.load_model_from_api()
                
                if face_recognizer is not None:
                    self.face_recognizer = face_recognizer
                    self.label_mapping = label_mapping
                    self.labels_to_name = labels_to_name
                    logger.info("مدل و فایل‌های مرتبط با موفقیت بروزرسانی شدند.")
                else:
                    logger.warning("بروزرسانی مدل ناموفق بود.")
            else:
                logger.warning("برخی از فایل‌های مورد نیاز در سرور موجود نیستند.")
        
        except Exception as e:
            logger.error("خطا در بررسی بروزرسانی‌های مدل: %s", e)

    def load_model_from_server(self):
        """این متد برای سازگاری با کد قبلی حفظ شده اما دیگر استفاده نمی‌شود"""
        logger.info("استفاده از روش جدید بارگذاری مدل از VPS")
        return None
        
    def load_label_mapping_from_server(self):
        """این متد برای سازگاری با کد قبلی حفظ شده اما دیگر استفاده نمی‌شود"""
        logger.info("استفاده از روش جدید بارگذاری نگاشت برچسب‌ها از VPS")
        return {}
        
    def load_labels_to_name_from_server(self):
        """این متد برای سازگاری با کد قبلی حفظ شده اما دیگر استفاده نمی‌شود"""
        logger.info("استفاده از روش جدید بارگذاری نگاشت برچسب‌ها به نام از VPS")
        return {}

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

    def process_faces(self, frame, location):
        """
        پردازش فریم:
          - تبدیل به تصویر خاکستری و بهبود کنتراست.
          - تشخیص چهره‌ها با پارامترهای بهینه‌شده.
          - در صورت کوچک بودن چهره (به علت فاصله از لنز) تصویر چهره بزرگ‌نمایی می‌شود.
          - پیش‌بینی برچسب با استفاده از مدل آموزش‌دیده.
          - ثبت حضور در صورت تشخیص با اطمینان کافی.
        """
        # تبدیل به تصویر خاکستری
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # بهبود کنتراست تصویر برای تشخیص بهتر چهره
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced_gray = clahe.apply(gray)
        
        # استفاده از پارامترهای بهینه‌شده برای تشخیص چهره‌های دور
        faces = self.face_cascade.detectMultiScale(
            enhanced_gray, 
            scaleFactor=1.2, 
            minNeighbors=5, 
            minSize=(30, 30),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        
        for (x, y, w, h) in faces:
            # کشیدن کادر دور چهره
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            
            # برش چهره از تصویر اصلی
            face_roi = enhanced_gray[y:y+h, x:x+w]

            # اگر چهره کوچک باشد، بزرگ‌نمایی می‌شود
            if w < 100 or h < 100:
                try:
                    face_roi = cv2.resize(face_roi, (100, 100), interpolation=cv2.INTER_CUBIC)
                except Exception as e:
                    logger.error("خطا در بزرگنمایی تصویر چهره: %s", e)
            else:
                # تغییر اندازه به ابعاد ثابت برای یکنواختی
                face_roi = cv2.resize(face_roi, (100, 100))
            
            # نرمال‌سازی روشنایی
            face_roi = cv2.equalizeHist(face_roi)

            if self.face_recognizer is not None:
                try:
                    label, confidence = self.face_recognizer.predict(face_roi)
                    
                    # نمایش اطلاعات تشخیص روی تصویر
                    confidence_text = f"Conf: {confidence:.1f}"
                    cv2.putText(frame, confidence_text, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    
                    # تنظیم آستانه دقت (مثلاً confidence کمتر از 80 برای دقت بیشتر)
                    if confidence < 80:
                        # استخراج کد ملی از برچسب
                        national_code = None
                        for nc, lbl in self.label_mapping.items():
                            if int(lbl) == label:
                                national_code = nc
                                break
                        
                        if national_code:
                            # بررسی آیا این فرد در دیکشنری last_checkin وجود دارد
                            current_time = time.time()
                            if national_code in self.last_checkin:
                                # اگر بیش از 2 ساعت از آخرین ثبت حضور گذشته باشد، مجدداً ثبت می‌کنیم
                                if current_time - self.last_checkin[national_code] > 7200:  # 2 ساعت = 7200 ثانیه
                                    self.log_attendance(national_code, location)
                                    self.last_checkin[national_code] = current_time
                            else:
                                # اولین بار است که این فرد را می‌بینیم
                                self.log_attendance(national_code, location)
                                self.last_checkin[national_code] = current_time
                        else:
                            logger.warning(f"برچسب {label} در نگاشت یافت نشد.")
                    else:
                        logger.debug("چهره با دقت کافی شناسایی نشد (confidence: %s).", confidence)
                except Exception as e:
                    logger.error("خطا در پیش‌بینی چهره: %s", e)
        
        return cv2.resize(frame, (640, 480))

    def log_attendance(self, national_code, location):
        """ثبت حضور دانش آموز در دیتابیس"""
        if self.db is None:
            logger.error("اتصال به دیتابیس برقرار نیست")
            return
        
        now = datetime.now()
        jalali_date = JalaliDateTime.now()
        
        try:
            with self.db.cursor() as cursor:
                # دریافت اطلاعات کاربر و کلاس
                cursor.execute("""
                    SELECT u.fullName, u.classId, c.name as className 
                    FROM user u 
                    LEFT JOIN class c ON u.classId = c.id 
                    WHERE u.nationalCode = %s
                """, (national_code,))
                
                user_info = cursor.fetchone()
                if not user_info:
                    logger.error(f"کاربر با کد ملی {national_code} یافت نشد")
                    return
                    
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
                    logger.info(f"حضور برای {full_name} در کلاس {class_name} ثبت شد")
                
                # آپدیت last_seen
                jalali_datetime = jalali_date.strftime("%Y/%m/%d %H:%M:%S")
                self.update_last_seen(national_code, full_name, jalali_datetime, location)
                
        except mysql.connector.Error as err:
            logger.error(f"خطای دیتابیس: {err}")
            self.db.rollback()

    def update_last_seen(self, national_code, full_name, timestamp, location):
        """به‌روزرسانی آخرین وضعیت مشاهده کاربر"""
        try:
            jalali_datetime = JalaliDateTime.now().strftime("%Y/%m/%d %H:%M:%S")
            
            with self.db.cursor() as cursor:
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


def detect_and_recognize_faces(self, frame, camera_index):
    """تشخیص و شناسایی چهره‌ها در فریم"""
    if self.face_recognizer is None:
        return frame, []

    # تبدیل به خاکستری
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # بهبود کنتراست تصویر برای دوربین‌های مداربسته
    gray = cv2.equalizeHist(gray)
    
    # تشخیص چهره‌ها
    faces = self.face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.2,  # کاهش مقدار برای تشخیص بهتر چهره‌های کوچک
        minNeighbors=5,
        minSize=(30, 30),
        flags=cv2.CASCADE_SCALE_IMAGE
    )
    
    recognized_faces = []
    
    for (x, y, w, h) in faces:
        # برش چهره
        face_gray = gray[y:y+h, x:x+w]
        
        # تغییر اندازه به 100x100 (همان اندازه‌ای که مدل با آن آموزش دیده)
        face_resized = cv2.resize(face_gray, (100, 100))
        
        # شناسایی چهره
        try:
            label, confidence = self.face_recognizer.predict(face_resized)
            label_str = str(label)
            
            # تبدیل برچسب عددی به کد ملی
            national_code = None
            for nc, lbl in self.label_mapping.items():
                if int(lbl) == label:
                    national_code = nc
                    break
            
            # دریافت اطلاعات کاربر
            user_info = self.labels_to_name.get(label_str, {})
            full_name = user_info.get("fullName", "ناشناس")
            
            # آستانه اطمینان - مقدار کمتر یعنی تطابق بیشتر
            threshold = 80  # می‌توانید این مقدار را تنظیم کنید
            
            if confidence < threshold and national_code:
                # رنگ کادر بر اساس میزان اطمینان
                # هرچه اطمینان بیشتر (confidence کمتر)، رنگ سبزتر
                confidence_normalized = min(confidence / threshold, 1.0)
                box_color = (
                    0,  # آبی
                    int(255 * (1 - confidence_normalized)),  # سبز
                    int(255 * confidence_normalized)  # قرمز
                )
                
                # رسم کادر دور چهره
                cv2.rectangle(frame, (x, y), (x+w, y+h), box_color, 2)
                
                # نمایش نام و میزان اطمینان
                confidence_text = f"{int(100 - confidence)}%"
                label_text = f"{full_name} ({confidence_text})"
                
                # رسم پس‌زمینه برای متن
                cv2.rectangle(frame, (x, y-30), (x+w, y), box_color, -1)
                cv2.putText(frame, label_text, (x+5, y-10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # ثبت حضور
                self.register_attendance(national_code, full_name, camera_index, confidence)
                
                recognized_faces.append({
                    "nationalCode": national_code,
                    "fullName": full_name,
                    "confidence": confidence,
                    "position": (x, y, w, h)
                })
            else:
                # چهره ناشناس
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
                cv2.putText(frame, "ناشناس", (x+5, y-10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        except Exception as e:
            logger.error("خطا در شناسایی چهره: %s", e)
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
    
    return frame, recognized_faces

# Add this method to the CameraManager class after the __init__ method
def load_model_from_api(self):
    """دریافت مدل و فایل‌های مربوطه از API با مکانیزم بهینه‌شده"""
    try:
        # ایجاد پوشه‌های مورد نیاز
        base_dir = os.path.dirname(os.path.abspath(__file__))
        trainer_dir = os.path.join(base_dir, 'trainer')
        labels_dir = os.path.join(base_dir, 'labels')
        
        os.makedirs(trainer_dir, exist_ok=True)
        os.makedirs(labels_dir, exist_ok=True)
        
        # مسیرهای فایل‌های محلی
        model_path = os.path.join(trainer_dir, 'model.xml')
        mapping_path = os.path.join(labels_dir, 'label_mapping.json')
        labels_path = os.path.join(labels_dir, 'labels_to_name.json')
        
        # بررسی وضعیت فایل‌ها در سرور قبل از دانلود
        check_url = f"{API_BASE_URL}/check-model"
        try:
            response = requests.get(check_url, timeout=5)
            if response.status_code != 200:
                logger.error("خطا در بررسی وضعیت مدل: کد وضعیت %s", response.status_code)
                return None, None, None
            
            data = response.json()
            if data.get("status") != "success":
                logger.error("خطا در بررسی وضعیت مدل: %s", data.get("message", "خطای نامشخص"))
                return None, None, None
            
            file_status = data.get("file_status", {})
            if not file_status.get("model_exists") or not file_status.get("mapping_exists") or not file_status.get("labels_exists"):
                logger.warning("برخی از فایل‌های مورد نیاز در سرور موجود نیستند.")
                return None, None, None
        except requests.exceptions.RequestException as e:
            logger.error("خطا در ارتباط با API برای بررسی وضعیت مدل: %s", e)
            return None, None, None
        
        # دریافت فایل مدل
        model_url = f"{API_BASE_URL}/public-model"
        try:
            response = requests.get(model_url, timeout=30)  # زمان انتظار بیشتر برای فایل‌های بزرگ
            if response.status_code == 200:
                with open(model_path, 'wb') as f:
                    f.write(response.content)
                logger.info("فایل مدل با موفقیت از API دریافت شد.")
            else:
                logger.warning("خطا در دریافت فایل مدل از API: %s", response.status_code)
                return None, None, None
        except requests.exceptions.RequestException as e:
            logger.error("خطا در دریافت فایل مدل از API: %s", e)
            return None, None, None
        
        # دریافت فایل نگاشت برچسب‌ها
        mapping_url = f"{API_BASE_URL}/label-mapping"
        try:
            response = requests.get(mapping_url, timeout=10)
            if response.status_code == 200:
                mapping_data = response.json().get('mapping', {})
                with open(mapping_path, 'w', encoding='utf-8') as f:
                    json.dump(mapping_data, f, ensure_ascii=False, indent=4)
                logger.info("فایل نگاشت برچسب‌ها با موفقیت از API دریافت شد.")
            else:
                logger.warning("خطا در دریافت فایل نگاشت برچسب‌ها از API: %s", response.status_code)
                return None, None, None
        except requests.exceptions.RequestException as e:
            logger.error("خطا در دریافت فایل نگاشت برچسب‌ها از API: %s", e)
            return None, None, None
        
        # دریافت فایل نگاشت برچسب‌ها به نام
        labels_url = f"{API_BASE_URL}/labels-to-name"
        try:
            response = requests.get(labels_url, timeout=10)
            if response.status_code == 200:
                labels_data = response.json().get('labels_to_name', {})
                with open(labels_path, 'w', encoding='utf-8') as f:
                    json.dump(labels_data, f, ensure_ascii=False, indent=4)
                logger.info("فایل نگاشت برچسب‌ها به نام با موفقیت از API دریافت شد.")
            else:
                logger.warning("خطا در دریافت فایل نگاشت برچسب‌ها به نام از API: %s", response.status_code)
                return None, None, None
        except requests.exceptions.RequestException as e:
            logger.error("خطا در دریافت فایل نگاشت برچسب‌ها به نام از API: %s", e)
            return None, None, None
        
        # بارگذاری مدل با پارامترهای بهینه‌شده
        try:
            if not hasattr(cv2, 'face'):
                raise AttributeError("ماژول cv2.face موجود نیست. لطفاً opencv-contrib-python را نصب کنید.")
            
            recognizer = cv2.face.LBPHFaceRecognizer_create(
                radius=2,
                neighbors=8,
                grid_x=8,
                grid_y=8,
                threshold=80.0  # آستانه پایین‌تر برای تشخیص دقیق‌تر
            )
            recognizer.read(model_path)
            
            # بارگذاری فایل‌های نگاشت
            with open(mapping_path, 'r', encoding='utf-8') as f:
                label_mapping = json.load(f)
            
            with open(labels_path, 'r', encoding='utf-8') as f:
                labels_to_name = json.load(f)
            
            logger.info("مدل و فایل‌های نگاشت با موفقیت از API بارگذاری شدند.")
            return recognizer, label_mapping, labels_to_name
        except Exception as e:
            logger.error("خطا در بارگذاری مدل: %s", e)
            return None, None, None
    
    except Exception as e:
        logger.error("خطا در بارگذاری مدل از API: %s", e)
        return None, None, None
