#!/usr/bin/env python3
# faceDetectionWithCamera.py

import cv2
import numpy as np
import redis
import mysql.connector
import os
import json
import requests
import paramiko
import time
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

# --------------------- تنظیمات Redis ---------------------
REDIS_CONFIG = {
    'host': os.environ.get('REDIS_HOST', 'localhost'),
    'port': 6379,
    'db': 0,
    'decode_responses': False
}

# --------------------- کلاس مدیریت مدل ---------------------
class ModelTrainer:
    def __init__(self):
        self.redis_conn = redis.Redis(**REDIS_CONFIG)
        self.face_recognizer = cv2.face.LBPHFaceRecognizer_create()
        self.label_mapping = {}
        self.labels_to_name = {}

    def load_training_data(self):
        """بارگذاری داده‌های آموزشی از Redis"""
        try:
            images = []
            labels = []
            label_count = 0
            
            for key in self.redis_conn.keys('face_*'):
                national_code = key.decode().split('_')[1]
                face_data = self.redis_conn.get(key)
                
                # تبدیل داده‌های باینری به آرایه numpy
                nparr = np.frombuffer(face_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
                
                if img is not None:
                    images.append(img)
                    labels.append(label_count)
                    self.label_mapping[national_code] = label_count
                    self.labels_to_name[label_count] = national_code
                    label_count += 1
            
            logger.info(f"تعداد {len(images)} تصویر برای آموزش بارگذاری شد")
            return images, labels
        except Exception as e:
            logger.error("خطا در بارگذاری داده‌های آموزشی: %s", e)
            return [], []

    def train_model(self):
        """آموزش مدل با داده‌های جدید"""
        try:
            images, labels = self.load_training_data()
            if len(images) == 0:
                logger.warning("هیچ داده آموزشی برای آموزش مدل وجود ندارد")
                return
            
            # آموزش مدل LBPH
            self.face_recognizer.train(images, np.array(labels))
            
            # ذخیره مدل آموزش دیده
            self.face_recognizer.save('trainer/trained_model.yml')
            logger.info("مدل با موفقیت آموزش داده و ذخیره شد")
        except Exception as e:
            logger.error("خطا در آموزش مدل: %s", e)
            raise

# --------------------- کلاس مدیریت دوربین‌ها ---------------------
class CameraManager:
    def __init__(self, face_recognizer, label_mapping, labels_to_name):
        self.cameras = []  # لیست دوربین‌ها
        self.grid_size = (2, 2)  # تعداد ردیف و ستون در نمایش گرید
        self.active_cam = -1     # -1 یعنی نمایش گرید، غیر از -1 یعنی نمایش تمام صفحه یک دوربین
        self.window_name = "Face Recognition System"
        self.last_click = 0
        self.click_delay = 500   # میلی‌ثانیه
        self.last_checkin = {}
        self.persian_days = {
            0: "شنبه",
            1: "یکشنبه",
            2: "دوشنبه",
            3: "سه‌شنبه",
            4: "چهارشنبه",
            5: "پنج‌شنبه",
            6: "جمعه"
        }
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        self.face_recognizer = face_recognizer
        self.label_mapping = label_mapping
        self.labels_to_name = labels_to_name
        try:
            self.db = mysql.connector.connect(**DB_CONFIG)
            logger.info("اتصال به دیتابیس MySQL برقرار شد.")
        except mysql.connector.Error as err:
            logger.error("خطا در اتصال به دیتابیس: %s", err)
            self.db = None

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

# تابع آموزش مدل با داده‌های Redis حذف شد - این تابع در سرور اجرا می‌شود

# --------------------- تابع اصلی ---------------------
def main():
    # --- اتصال به Redis و آموزش مدل قبل از هر چیز ---
    model_trainer = ModelTrainer()
    model_trainer.load_training_data()
    model_trainer.train_model()
    manager = CameraManager(
        model_trainer.face_recognizer,
        model_trainer.label_mapping,
        model_trainer.labels_to_name
    )
    
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
