#!/usr/bin/env python3
import os
import base64
import json
import logging
import numpy as np
import cv2
import redis
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from persiantools.jdatetime import JalaliDateTime
import boto3
from botocore.exceptions import NoCredentialsError
from datetime import datetime

# --------------------- تنظیمات اولیه ---------------------
# ایجاد پوشه‌های مورد نیاز برای ذخیره مدل و لیبل‌ها
os.makedirs("trainer", exist_ok=True)
os.makedirs("labels", exist_ok=True)

# پیکربندی لاگ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
try:
    redis_client = redis.StrictRedis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)
    redis_client.ping()
    logging.info("اتصال به Redis با موفقیت برقرار شد.")
except Exception as e:
    logging.error("خطا در اتصال به Redis: %s", e)
    exit(1)

# تنظیم Flask و CORS
app = Flask(__name__)
CORS(app)

# مسیرهای Haar Cascade برای تشخیص چهره و چشم
HAAR_CASCADE_PATHS = {
    "face": "assets/face_detection/haarcascade_frontalface_default.xml",
    "eye": "assets/face_detection/haarcascade_eye.xml"
}
for key, path in HAAR_CASCADE_PATHS.items():
    if not os.path.exists(path):
        raise FileNotFoundError(f"فایل Haar Cascade برای {key} در مسیر {path} یافت نشد.")

face_cascade = cv2.CascadeClassifier(HAAR_CASCADE_PATHS["face"])
eye_cascade = cv2.CascadeClassifier(HAAR_CASCADE_PATHS["eye"])

# --------------------- تنظیمات فضای ابری لیارا ---------------------
LIARA_ACCESS_KEY = 'u2cgc3ev1i29tmeg'
LIARA_SECRET_KEY = '46c86213-2684-4421-9c1d-7d96cb22ac14'
LIARA_BUCKET_NAME = 'photo-attendance-system'
LIARA_ENDPOINT_URL = 'https://storage.c2.liara.space'

s3_client = boto3.client('s3',
                         aws_access_key_id=LIARA_ACCESS_KEY,
                         aws_secret_access_key=LIARA_SECRET_KEY,
                         endpoint_url=LIARA_ENDPOINT_URL)


# --------------------- توابع کمکی ---------------------
def upload_to_liara(national_code, color_image_data):
    """آپلود تصویر رنگی به فضای ابری لیارا"""
    try:
        folder_name = "user_register"
        file_name = f"{folder_name}/{national_code}.jpg"
        s3_client.put_object(Bucket=LIARA_BUCKET_NAME, Key=file_name, Body=color_image_data, ContentType='image/jpeg')
        logging.info(f"تصویر رنگی برای کد ملی {national_code} در پوشه {folder_name} در لیارا ذخیره شد.")
    except NoCredentialsError:
        logging.error("مشکل در احراز هویت با لیارا.")
        raise ValueError("احراز هویت با لیارا انجام نشد.")
    except Exception as e:
        logging.error(f"خطا در آپلود به لیارا: {e}")
        raise ValueError("خطا در آپلود به فضای ابری.")


def base64_to_cv2_image(base64_str):
    """
    تبدیل رشته Base64 به تصویر OpenCV.
    در صورت وجود پیشوند Data URI آن را حذف می‌کند.
    """
    try:
        if ',' in base64_str:
            base64_str = base64_str.split(',')[1]
        img_data = base64.b64decode(base64_str)
        np_arr = np.frombuffer(img_data, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("تصویر نامعتبر است.")
        return image
    except Exception as e:
        logging.error("خطا در تبدیل Base64 به تصویر: %s", e)
        raise ValueError("عدم توانایی در تبدیل رشته Base64 به تصویر.")


def detect_and_validate_face(image):
    """
    تشخیص چهره در تصویر و اعتبارسنجی آن (حداقل دو چشم).
    بازگشت تصویر خاکستری و رنگی صورت تشخیص داده شده
    بهینه‌سازی شده برای افزایش دقت تشخیص
    """
    try:
        # تبدیل تصویر به خاکستری
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # بهبود کنتراست تصویر برای تشخیص بهتر چهره
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced_gray = clahe.apply(gray)
        
        # تشخیص چهره با پارامترهای بهینه‌شده
        # scaleFactor: مقیاس کاهش اندازه تصویر در هر مرحله
        # minNeighbors: تعداد همسایه‌های مورد نیاز برای تشخیص چهره
        # minSize: حداقل اندازه چهره قابل تشخیص
        faces = face_cascade.detectMultiScale(
            enhanced_gray, 
            scaleFactor=1.2, 
            minNeighbors=5, 
            minSize=(60, 60),
            flags=cv2.CASCADE_SCALE_IMAGE
        )

        if len(faces) == 0:
            logging.warning("هیچ چهره‌ای در تصویر شناسایی نشد.")
            return None, None, None

        # انتخاب بزرگترین چهره (احتمالاً نزدیک‌ترین چهره به دوربین)
        largest_face = max(faces, key=lambda face: face[2] * face[3])
        (x, y, w, h) = largest_face
        
        # برش چهره از تصویر اصلی
        face_gray = enhanced_gray[y:y + h, x:x + w]
        face_color = image[y:y + h, x:x + w]

        # تغییر اندازه به ابعاد ثابت
        resized_gray = cv2.resize(face_gray, (200, 200))
        resized_color = cv2.resize(face_color, (200, 200))

        # بهبود کیفیت تصویر چهره
        # نرمال‌سازی روشنایی
        resized_gray = cv2.equalizeHist(resized_gray)

        # اعتبارسنجی چشم‌ها با پارامترهای بهینه‌شده
        eyes = eye_cascade.detectMultiScale(
            resized_gray,
            scaleFactor=1.1,
            minNeighbors=4,
            minSize=(20, 20)
        )
        
        if len(eyes) < 2:
            logging.warning("چهره شناسایی شده چشم‌های کافی ندارد.")
            # تلاش مجدد با پارامترهای متفاوت
            eyes = eye_cascade.detectMultiScale(
                resized_gray,
                scaleFactor=1.05,
                minNeighbors=3,
                minSize=(15, 15)
            )
            if len(eyes) < 2:
                return None, None, None

        logging.info(f"چهره با {len(eyes)} چشم شناسایی شد.")
        return resized_gray, resized_color, (x, y, w, h)

    except Exception as e:
        logging.error("خطا در پردازش تصویر: %s", e)
        raise


def save_to_redis(national_code, full_name, face_image_gray):
    """
    ذخیره چند تصویر برای هر کاربر در Redis (حداکثر 5 تصویر)
    """
    try:
        success, buffer = cv2.imencode('.jpg', face_image_gray, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not success:
            raise ValueError("خطا در رمزگذاری تصویر به JPEG.")
        face_base64 = base64.b64encode(buffer).decode('utf-8')
        now = datetime.now()
        jalali_now = JalaliDateTime.now()
        # خواندن داده قبلی (در صورت وجود)
        prev_data_json = redis_client.get(national_code)
        if prev_data_json:
            prev_data = json.loads(prev_data_json)
            faces = prev_data.get("faces", [])
        else:
            faces = []
        # اضافه کردن تصویر جدید به ابتدای آرایه
        faces.insert(0, {
            "faceImage": face_base64,
            "detectionTime": jalali_now.strftime('%Y-%m-%d %H:%M:%S'),
            "detectionTimeGregorian": now.strftime('%Y-%m-%d %H:%M:%S'),
            "imageQuality": {
                "width": face_image_gray.shape[1],
                "height": face_image_gray.shape[0],
                "format": "jpg",
                "quality": 95
            },
            "metadata": {
                "version": "2.0",
                "source": "face_registration_api",
                "timestamp": int(now.timestamp())
            }
        })
        # فقط 5 تصویر آخر را نگه دار
        faces = faces[:5]
        data = {
            "nationalCode": national_code,
            "fullName": full_name,
            "faces": faces
        }
        expiry_time = 60 * 60 * 24 * 30
        redis_client.setex(national_code, expiry_time, json.dumps(data))
        logging.info("%d تصویر برای کاربر '%s' با کد ملی %s در Redis ذخیره شد.", len(faces), full_name, national_code)
        return True
    except Exception as e:
        logging.error("خطا در ذخیره اطلاعات در Redis برای کد ملی %s: %s", national_code, e)
        raise ValueError(f"ذخیره اطلاعات در Redis با خطا مواجه شد: {str(e)}")


# --------------------- آموزش مدل تشخیص چهره ---------------------
def train_model_from_redis():
    """
    داده‌های چهره را از Redis جمع‌آوری می‌کند، نگاشت کد ملی به لیبل عددی می‌سازد، مدل را آموزش می‌دهد و فایل‌های نگاشت را ذخیره می‌کند.
    منطق دقیقاً مشابه نسخه لوکال.
    """
    try:
        # جمع‌آوری داده‌ها از Redis
        keys = redis_client.keys()
        faces = []
        labels = []
        label_mapping = {}
        labels_to_name = {}
        label_counter = 0
        for key in keys:
            data_json = redis_client.get(key)
            if not data_json:
                continue
            data = json.loads(data_json)
            national_code = data.get("nationalCode") or key
            full_name = data.get("fullName", "")
            # پشتیبانی از چند تصویر (ساختار جدید)
            face_images = []
            if "faces" in data:
                for face_obj in data["faces"]:
                    face_base64 = face_obj.get("faceImage")
                    if face_base64:
                        img_data = base64.b64decode(face_base64)
                        np_arr = np.frombuffer(img_data, np.uint8)
                        image = cv2.imdecode(np_arr, cv2.IMREAD_GRAYSCALE)
                        if image is not None:
                            face_images.append(image)
            elif "faceImage" in data:
                face_base64 = data["faceImage"]
                img_data = base64.b64decode(face_base64)
                np_arr = np.frombuffer(img_data, np.uint8)
                image = cv2.imdecode(np_arr, cv2.IMREAD_GRAYSCALE)
                if image is not None:
                    face_images.append(image)
            if not face_images:
                continue
            # نگاشت کد ملی به لیبل عددی
            if national_code not in label_mapping:
                label_mapping[national_code] = label_counter
                labels_to_name[str(label_counter)] = full_name
                label_counter += 1
            label = label_mapping[national_code]
            for img in face_images:
                if img.shape != (200, 200):
                    img = cv2.resize(img, (200, 200))
                faces.append(img)
                labels.append(label)
        if not faces or not labels:
            logging.warning("هیچ داده‌ای برای آموزش یافت نشد.")
            return False, "هیچ داده‌ای برای آموزش یافت نشد."
        faces = np.array(faces)
        labels = np.array(labels)
        # آموزش مدل LBPH
        if not hasattr(cv2, 'face'):
            raise AttributeError("ماژول cv2.face موجود نیست. لطفاً opencv-contrib-python را نصب کنید.")
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.train(faces, labels)
        # ذخیره مدل و فایل‌های نگاشت
        model_path = os.path.join("trainer", "model.xml")
        recognizer.save(model_path)
        with open(os.path.join("labels", "label_mapping.json"), "w", encoding="utf-8") as f:
            json.dump(label_mapping, f, ensure_ascii=False, indent=2)
        with open(os.path.join("labels", "labels_to_name.json"), "w", encoding="utf-8") as f:
            json.dump(labels_to_name, f, ensure_ascii=False, indent=2)
        logging.info("مدل و فایل‌های نگاشت با موفقیت ذخیره شدند.")
        return True, "آموزش مدل با موفقیت انجام شد."
    except Exception as e:
        logging.error(f"خطا در آموزش مدل: {e}")
        return False, f"خطا در آموزش مدل: {e}"

# --------------------- API آموزش مدل ---------------------
@app.route("/train-model", methods=["POST"])
def train_model_api():
    """API برای آموزش مدل با داده‌های Redis و ذخیره فایل‌ها به سبک لوکال"""
    success, message = train_model_from_redis()
    status = "success" if success else "error"
    return jsonify({"status": status, "message": message})


def validate_inputs(data):
    """
    اعتبارسنجی ورودی دریافتی از کلاینت.
    """
    required_fields = ["nationalCode", "image"]
    for field in required_fields:
        if field not in data or not data[field]:
            raise ValueError(f"فیلد {field} الزامی است.")
    
    # اعتبارسنجی کد ملی
    national_code = data.get("nationalCode", "")
    if not national_code.isdigit():
        raise ValueError("کد ملی باید فقط شامل اعداد باشد.")
    
    # کد ملی باید حداقل 10 رقم باشد
    if len(national_code) < 10:
        raise ValueError("کد ملی باید حداقل 10 رقم باشد.")
    
    return True


# --------------------- API ---------------------
@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "success", "message": "سرور در حال اجراست."})


@app.route('/system-status', methods=['GET'])
def system_status():
    """
    ارائه وضعیت سیستم و اطلاعات آماری
    """
    try:
        # بررسی وضعیت Redis
        redis_status = "online"
        try:
            redis_client.ping()
        except Exception:
            redis_status = "offline"
        
        # بررسی وضعیت مدل
        model_path = os.path.join("trainer", "model.xml")
        model_exists = os.path.exists(model_path)
        
        # آمار کلی سیستم
        stats = {
            "redis_status": redis_status,
            "model_exists": model_exists,
            "server_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "server_time_jalali": JalaliDateTime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # اگر مدل وجود دارد، اطلاعات آماری آن را اضافه می‌کنیم
        if model_exists:
            mapping_path = os.path.join("labels", "label_mapping.json")
            if os.path.exists(mapping_path):
                with open(mapping_path, 'r', encoding='utf-8') as f:
                    mapping_data = json.load(f)
                    stats["registered_users"] = len(mapping_data)
            
            # زمان آخرین بروزرسانی مدل
            stats["model_last_update"] = datetime.fromtimestamp(
                os.path.getmtime(model_path)
            ).strftime('%Y-%m-%d %H:%M:%S')
            
            # تبدیل به تاریخ شمسی
            jalali_date = JalaliDateTime.to_jalali(
                datetime.fromtimestamp(os.path.getmtime(model_path))
            )
            stats["model_last_update_jalali"] = jalali_date.strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({"status": "success", "system_stats": stats})
    except Exception as e:
        logging.error("خطا در بررسی وضعیت سیستم: %s", e)
        return jsonify({"status": "error", "message": "خطا در بررسی وضعیت سیستم."}), 500


@app.route('/upload', methods=['POST'])
def upload_image():
    """
    دریافت تصویر و کد ملی از کلاینت
    """
    try:
        data = request.get_json()
        if data is None:
            raise ValueError("داده‌های ورودی نامعتبر هستند.")
        validate_inputs(data)

        national_code = data["nationalCode"]
        full_name = data.get("fullName", "")
        image_data = data["image"]

        image = base64_to_cv2_image(image_data)
        face_gray, face_color, bbox = detect_and_validate_face(image)

        if face_gray is None:
            return jsonify({"status": "error", "message": "چهره معتبر در تصویر شناسایی نشد."}), 400

        # ذخیره تصویر خاکستری در Redis
        save_to_redis(national_code, full_name, face_gray)

        # ذخیره تصویر رنگی در لیارا
        _, buffer = cv2.imencode('.jpg', face_color)
        upload_to_liara(national_code, buffer.tobytes())

        # آموزش مدل
        train_model()

        return jsonify({"status": "success", "message": "تصویر پردازش شد، اطلاعات ذخیره و مدل به‌روز شد."})

    except ValueError as ve:
        logging.error("خطای ورودی: %s", ve)
        return jsonify({"status": "error", "message": str(ve)}), 400
    except Exception as e:
        logging.error("خطا در پردازش آپلود تصویر: %s", e)
        return jsonify({"status": "error", "message": "خطای سرور داخلی."}), 500


@app.route('/labels', methods=['GET'])
def get_labels():
    """
    دریافت لیبل‌های ذخیره‌شده
    """
    try:
        labels_path = os.path.join("labels", "labels_to_name.json")
        if not os.path.exists(labels_path):
            return jsonify({"status": "error", "message": "فایل لیبل یافت نشد."}), 404

        with open(labels_path, 'r', encoding='utf-8') as f:
            labels_data = json.load(f)

        return jsonify({"status": "success", "labels": labels_data})
    except Exception as e:
        logging.error("خطا در دریافت لیبل‌ها: %s", e)
        return jsonify({"status": "error", "message": "خطا در دریافت لیبل‌ها."}), 500


# --------------------- روت‌های اصلی برای دسترسی به مدل ---------------------
@app.route('/check-model', methods=['GET'])
def check_model():
    """
    بررسی وضعیت فایل‌های مدل برای دستگاه‌های خارجی
    """
    try:
        model_path = os.path.join("trainer", "model.xml")
        mapping_path = os.path.join("labels", "label_mapping.json")
        labels_path = os.path.join("labels", "labels_to_name.json")
        
        # بررسی وجود فایل‌ها
        model_exists = os.path.exists(model_path)
        mapping_exists = os.path.exists(mapping_path)
        labels_exists = os.path.exists(labels_path)
        
        return jsonify({
            "status": "success", 
            "file_status": {
                "model_exists": model_exists,
                "mapping_exists": mapping_exists,
                "labels_exists": labels_exists
            }
        })
    except Exception as e:
        logging.error("خطا در بررسی وضعیت مدل: %s", e)
        return jsonify({"status": "error", "message": "خطا در بررسی وضعیت مدل."}), 500

@app.route('/public-model', methods=['GET'])
def get_model_file():
    """
    ارسال فایل مدل به دستگاه‌های خارجی
    """
    try:
        model_path = os.path.join("trainer", "model.xml")
        if not os.path.exists(model_path):
            return jsonify({"status": "error", "message": "فایل مدل موجود نیست."}), 404
        
        return send_file(model_path, as_attachment=True)
    except Exception as e:
        logging.error("خطا در ارسال فایل مدل: %s", e)
        return jsonify({"status": "error", "message": "خطا در ارسال فایل مدل."}), 500

@app.route('/label-mapping', methods=['GET'])
def get_label_mapping():
    """
    ارسال فایل نگاشت برچسب‌ها به دستگاه‌های خارجی
    """
    try:
        mapping_path = os.path.join("labels", "label_mapping.json")
        if not os.path.exists(mapping_path):
            return jsonify({"status": "error", "message": "فایل نگاشت برچسب‌ها موجود نیست."}), 404
        
        with open(mapping_path, 'r', encoding='utf-8') as f:
            mapping_data = json.load(f)
        
        return jsonify({"status": "success", "mapping": mapping_data})
    except Exception as e:
        logging.error("خطا در ارسال فایل نگاشت برچسب‌ها: %s", e)
        return jsonify({"status": "error", "message": "خطا در ارسال فایل نگاشت برچسب‌ها."}), 500

@app.route('/labels-to-name', methods=['GET'])
def get_labels_to_name():
    """
    ارسال فایل نگاشت برچسب‌ها به نام به دستگاه‌های خارجی
    """
    try:
        labels_path = os.path.join("labels", "labels_to_name.json")
        if not os.path.exists(labels_path):
            return jsonify({"status": "error", "message": "فایل نگاشت برچسب‌ها به نام موجود نیست."}), 404
        
        with open(labels_path, 'r', encoding='utf-8') as f:
            labels_data = json.load(f)
        
        return jsonify({"status": "success", "labels_to_name": labels_data})
    except Exception as e:
        logging.error("خطا در ارسال فایل نگاشت برچسب‌ها به نام: %s", e)
        return jsonify({"status": "error", "message": "خطا در ارسال فایل نگاشت برچسب‌ها به نام."}), 500


# --------------------- روت‌های آماری و مانیتورینگ ---------------------
@app.route('/stats', methods=['GET'])
def get_system_stats():
    """
    ارائه آمار و اطلاعات سیستم برای مانیتورینگ
    """
    try:
        # آمار کلی سیستم
        stats = {
            "server": {
                "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "time_jalali": JalaliDateTime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "uptime": os.popen('uptime').read().strip() if os.name != 'nt' else 'Not available on Windows'
            },
            "storage": {
                "trainer_dir_exists": os.path.exists("trainer"),
                "labels_dir_exists": os.path.exists("labels")
            },
            "redis": {
                "connected": True
            }
        }
        
        # آمار Redis
        try:
            redis_info = redis_client.info()
            stats["redis"]["version"] = redis_info.get("redis_version", "Unknown")
            stats["redis"]["connected_clients"] = redis_info.get("connected_clients", 0)
            stats["redis"]["used_memory_human"] = redis_info.get("used_memory_human", "Unknown")
            
            # تعداد کلیدهای موجود در Redis
            user_count = 0
            for key in redis_client.scan_iter():
                user_count += 1
            stats["redis"]["stored_users"] = user_count
        except Exception as e:
            logging.error("خطا در دریافت اطلاعات Redis: %s", e)
            stats["redis"]["connected"] = False
        
        # آمار مدل
        model_path = os.path.join("trainer", "model.xml")
        if os.path.exists(model_path):
            model_size = os.path.getsize(model_path) / (1024 * 1024)  # تبدیل به مگابایت
            model_modified = datetime.fromtimestamp(os.path.getmtime(model_path))
            
            stats["model"] = {
                "exists": True,
                "size_mb": round(model_size, 2),
                "last_modified": model_modified.strftime('%Y-%m-%d %H:%M:%S'),
                "last_modified_jalali": JalaliDateTime.to_jalali(model_modified).strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # اطلاعات کاربران ثبت شده در مدل
            mapping_path = os.path.join("labels", "label_mapping.json")
            if os.path.exists(mapping_path):
                with open(mapping_path, 'r', encoding='utf-8') as f:
                    mapping_data = json.load(f)
                    stats["model"]["registered_users"] = len(mapping_data)
        else:
            stats["model"] = {"exists": False}
        
        return jsonify({"status": "success", "stats": stats})
    except Exception as e:
        logging.error("خطا در جمع‌آوری آمار سیستم: %s", e)
        return jsonify({"status": "error", "message": "خطا در جمع‌آوری آمار سیستم."}), 500


# --------------------- اجرای سرور ---------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
else:
    # در حالت اجرا توسط WSGI
    application = app