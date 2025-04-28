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
    """
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)

        if len(faces) == 0:
            logging.warning("هیچ چهره‌ای در تصویر شناسایی نشد.")
            return None, None, None

        for (x, y, w, h) in faces:
            face_gray = gray[y:y + h, x:x + w]
            face_color = image[y:y + h, x:x + w]

            # تغییر اندازه به ابعاد ثابت - اندازه را به 100x100 تغییر دادیم
            resized_gray = cv2.resize(face_gray, (100, 100))
            resized_color = cv2.resize(face_color, (200, 200))  # رنگی همان 200x200 بماند

            # اعتبارسنجی چشم‌ها
            eyes = eye_cascade.detectMultiScale(resized_gray)
            if len(eyes) < 2:
                logging.warning("چهره شناسایی شده چشم‌های کافی ندارد.")
                continue

            return resized_gray, resized_color, (x, y, w, h)

        return None, None, None
    except Exception as e:
        logging.error("خطا در پردازش تصویر: %s", e)
        raise


def save_to_redis(national_code, full_name, face_image_gray):
    """
    ذخیره اطلاعات کاربر در Redis.
    """
    try:
        success, buffer = cv2.imencode('.jpg', face_image_gray)
        if not success:
            raise ValueError("خطا در رمزگذاری تصویر به JPEG.")

        face_base64 = base64.b64encode(buffer).decode('utf-8')
        data = {
            "nationalCode": national_code,
            "fullName": full_name,
            "faceImage": face_base64,
            "detectionTime": JalaliDateTime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        redis_client.set(national_code, json.dumps(data))
        logging.info("اطلاعات کاربر با کد ملی %s در Redis ذخیره شد.", national_code)
    except Exception as e:
        logging.error("خطا در ذخیره اطلاعات در Redis: %s", e)
        raise ValueError("ذخیره اطلاعات در Redis با خطا مواجه شد.")


def train_model():
    """
    آموزش مدل تشخیص چهره با استفاده از داده‌های ذخیره‌شده در Redis.
    """
    faces = []
    labels = []
    labels_to_name = {}
    # دیکشنری برای نگاشت بین کد ملی و برچسب عددی یکتا
    national_code_to_label = {}
    label_counter = 1

    # بررسی وجود فایل نگاشت قبلی برای حفظ سازگاری
    mapping_path = os.path.join("labels", "label_mapping.json")
    if os.path.exists(mapping_path):
        try:
            with open(mapping_path, 'r', encoding='utf-8') as f:
                national_code_to_label = json.load(f)
                # تعیین بزرگترین شماره برچسب موجود
                if national_code_to_label:
                    label_counter = max([int(v) for v in national_code_to_label.values()]) + 1
                    logging.info(f"فایل نگاشت موجود بارگذاری شد. شمارنده برچسب از {label_counter} شروع می‌شود.")
        except Exception as e:
            logging.error(f"خطا در بارگذاری فایل نگاشت موجود: {e}")

    for key in redis_client.scan_iter():
        try:
            value = redis_client.get(key)
            if not value:
                continue
            data = json.loads(value)
            national_code = data.get("nationalCode", key)
            face_base64 = data.get('faceImage')
            if not face_base64:
                continue

            img_data = base64.b64decode(face_base64)
            np_arr = np.frombuffer(img_data, np.uint8)
            face_img = cv2.imdecode(np_arr, cv2.IMREAD_GRAYSCALE)

            if face_img is None:
                continue

            # اندازه تصویر را بررسی می‌کنیم - اگر نیاز به تغییر اندازه باشد
            if face_img.shape[0] != 100 or face_img.shape[1] != 100:
                resized_face = cv2.resize(face_img, (100, 100))
            else:
                resized_face = face_img
            
            # استفاده از شمارنده برای اختصاص شناسه‌های صحیح و یکتا
            if national_code not in national_code_to_label:
                national_code_to_label[national_code] = label_counter
                label_counter += 1
            
            label_int = national_code_to_label[national_code]
            
            # افزودن چندین نمونه از هر چهره با تغییرات جزئی برای افزایش دقت
            faces.append(resized_face)
            labels.append(label_int)
            
            # افزودن نمونه‌های با چرخش جزئی برای افزایش دقت
            for angle in [-5, 5, -10, 10]:  # افزایش تنوع زوایای چرخش
                M = cv2.getRotationMatrix2D((50, 50), angle, 1)
                rotated = cv2.warpAffine(resized_face, M, (100, 100))
                faces.append(rotated)
                labels.append(label_int)
            
            # افزودن نمونه‌های با تغییر روشنایی برای افزایش دقت
            for alpha in [0.8, 1.2]:  # کاهش و افزایش روشنایی
                brightness_adjusted = cv2.convertScaleAbs(resized_face, alpha=alpha, beta=0)
                faces.append(brightness_adjusted)
                labels.append(label_int)
            
            labels_to_name[str(label_int)] = {
                "nationalCode": national_code,
                "fullName": data.get("fullName", "")
            }
            logging.info(f"کد ملی {national_code} با برچسب {label_int} آماده آموزش شد.")
        except Exception as e:
            logging.error("خطا در پردازش داده‌های ذخیره‌شده برای کلید %s: %s", key, e)
            continue

    if faces and labels:
        try:
            # تنظیم پارامترهای LBPH برای افزایش دقت
            model = cv2.face.LBPHFaceRecognizer_create(
                radius=2,        # شعاع برای الگوهای محلی باینری
                neighbors=8,     # تعداد همسایه‌ها
                grid_x=8,        # تقسیم‌بندی افقی تصویر
                grid_y=8,        # تقسیم‌بندی عمودی تصویر
                threshold=70     # کاهش آستانه برای تشخیص دقیق‌تر
            )
            
            # تبدیل لیست‌ها به آرایه‌های NumPy
            faces_array = np.array(faces)
            labels_array = np.array(labels)
            
            # بررسی تعداد نمونه‌ها
            logging.info(f"آموزش مدل با {len(faces_array)} نمونه چهره و {len(set(labels_array))} فرد متمایز")
            
            # آموزش مدل
            model.train(faces_array, labels_array)
            model_path = os.path.join("trainer", "model.xml")
            model.write(model_path)
            logging.info("مدل تشخیص چهره در %s ذخیره شد.", model_path)

            # ذخیره نگاشت کد ملی به برچسب برای استفاده در تشخیص
            with open(mapping_path, 'w', encoding='utf-8') as f:
                json.dump(national_code_to_label, f, ensure_ascii=False, indent=4)
            logging.info("نگاشت برچسب‌ها در %s ذخیره شد.", mapping_path)

            labels_path = os.path.join("labels", "labels_to_name.json")
            with open(labels_path, 'w', encoding='utf-8') as f:
                json.dump(labels_to_name, f, ensure_ascii=False, indent=4)
            logging.info("لیبل‌ها در %s ذخیره شدند.", labels_path)
            
            return True
        except Exception as e:
            logging.error("خطا در آموزش مدل: %s", e)
            raise
    else:
        logging.warning("داده‌ای جهت آموزش مدل یافت نشد.")
        return False


def validate_inputs(data):
    """
    اعتبارسنجی ورودی دریافتی از کلاینت.
    """
    required_fields = ["nationalCode", "image"]
    for field in required_fields:
        if field not in data or not data[field]:
            raise ValueError(f"فیلد {field} الزامی است.")
    return True


# --------------------- روت‌های API ---------------------
@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "success", "message": "سرور در حال اجراست."})


@app.route('/trainer/<path:filename>', methods=['GET'])
def serve_trainer_file(filename):
    """
    ارسال فایل‌های داخل پوشه trainer
    """
    try:
        full_path = os.path.join("trainer", filename)
        if not os.path.exists(full_path):
            return jsonify({"status": "error", "message": f"فایل {filename} در پوشه trainer یافت نشد."}), 404
            
        return send_file(full_path)
    except Exception as e:
        logging.error(f"خطا در ارسال فایل {filename} از پوشه trainer: {e}")
        return jsonify({"status": "error", "message": f"خطا در ارسال فایل {filename}"}), 500


@app.route('/labels/<path:filename>', methods=['GET'])
def serve_labels_file(filename):
    """
    ارسال فایل‌های داخل پوشه labels
    """
    try:
        full_path = os.path.join("labels", filename)
        if not os.path.exists(full_path):
            return jsonify({"status": "error", "message": f"فایل {filename} در پوشه labels یافت نشد."}), 404
            
        return send_file(full_path)
    except Exception as e:
        logging.error(f"خطا در ارسال فایل {filename} از پوشه labels: {e}")
        return jsonify({"status": "error", "message": f"خطا در ارسال فایل {filename}"}), 500


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


# --------------------- روت‌های جدید برای دسترسی به فایل مدل و لیبل‌ها ---------------------
@app.route('/model', methods=['GET'])
def get_model():
    """
    ارسال فایل مدل XML به درخواست‌کننده
    """
    try:
        model_path = os.path.join("trainer", "model.xml")
        if not os.path.exists(model_path):
            return jsonify({"status": "error", "message": "فایل مدل یافت نشد."}), 404
        
        return send_file(model_path, mimetype='application/xml')
    except Exception as e:
        logging.error("خطا در ارسال فایل مدل: %s", e)
        return jsonify({"status": "error", "message": "خطا در ارسال فایل مدل."}), 500


@app.route('/label-mapping', methods=['GET'])
def get_label_mapping():
    """
    ارسال فایل نگاشت برچسب‌ها به درخواست‌کننده
    """
    try:
        mapping_path = os.path.join("labels", "label_mapping.json")
        if not os.path.exists(mapping_path):
            return jsonify({"status": "error", "message": "فایل نگاشت برچسب‌ها یافت نشد."}), 404
            
        with open(mapping_path, 'r', encoding='utf-8') as f:
            mapping_data = json.load(f)
            
        return jsonify({"status": "success", "mapping": mapping_data})
    except Exception as e:
        logging.error("خطا در ارسال فایل نگاشت برچسب‌ها: %s", e)
        return jsonify({"status": "error", "message": "خطا در ارسال فایل نگاشت برچسب‌ها."}), 500


@app.route('/labels-to-name', methods=['GET'])
def get_labels_to_name():
    """
    ارسال فایل نگاشت برچسب‌ها به نام به درخواست‌کننده
    """
    try:
        labels_path = os.path.join("labels", "labels_to_name.json")
        if not os.path.exists(labels_path):
            return jsonify({"status": "error", "message": "فایل نگاشت برچسب‌ها به نام یافت نشد."}), 404
            
        with open(labels_path, 'r', encoding='utf-8') as f:
            labels_data = json.load(f)
            
        return jsonify({"status": "success", "labels_to_name": labels_data})
    except Exception as e:
        logging.error("خطا در ارسال فایل نگاشت برچسب‌ها به نام: %s", e)
        return jsonify({"status": "error", "message": "خطا در ارسال فایل نگاشت برچسب‌ها به نام."}), 500


@app.route('/check-model', methods=['GET'])
def check_model_status():
    """
    بررسی وضعیت مدل و فایل‌های لیبل
    """
    try:
        model_path = os.path.join("trainer", "model.xml")
        mapping_path = os.path.join("labels", "label_mapping.json")
        labels_path = os.path.join("labels", "labels_to_name.json")
        
        status = {
            "model_exists": os.path.exists(model_path),
            "mapping_exists": os.path.exists(mapping_path),
            "labels_exists": os.path.exists(labels_path)
        }
        
        return jsonify({"status": "success", "file_status": status})
    except Exception as e:
        logging.error("خطا در بررسی وضعیت فایل‌ها: %s", e)
        return jsonify({"status": "error", "message": "خطا در بررسی وضعیت فایل‌ها."}), 500


# --------------------- روت‌های دیباگ ---------------------
@app.route('/debug/check-dirs', methods=['GET'])
def check_directories():
    """
    بررسی وضعیت پوشه‌ها و فایل‌ها
    """
    try:
        # مسیر فعلی
        current_dir = os.getcwd()
        
        # بررسی پوشه‌های موجود
        directories = [d for d in os.listdir() if os.path.isdir(d)]
        
        # بررسی وجود پوشه‌های trainer و labels
        trainer_dir = os.path.exists("trainer")
        labels_dir = os.path.exists("labels")
        
        # بررسی وجود فایل‌ها
        model_file = os.path.exists("trainer/model.xml") if trainer_dir else False
        mapping_file = os.path.exists("labels/label_mapping.json") if labels_dir else False
        labels_file = os.path.exists("labels/labels_to_name.json") if labels_dir else False
        
        # محتویات پوشه‌ها
        trainer_files = os.listdir("trainer") if trainer_dir else []
        labels_files = os.listdir("labels") if labels_dir else []
        
        # دسترسی‌های فایل‌ها و پوشه‌ها
        trainer_permissions = oct(os.stat("trainer").st_mode)[-3:] if trainer_dir else ""
        labels_permissions = oct(os.stat("labels").st_mode)[-3:] if labels_dir else ""
        
        return jsonify({
            "status": "success",
            "current_directory": current_dir,
            "all_directories": directories,
            "trainer_exists": trainer_dir,
            "labels_exists": labels_dir,
            "model_file_exists": model_file,
            "mapping_file_exists": mapping_file,
            "labels_file_exists": labels_file,
            "trainer_files": trainer_files,
            "labels_files": labels_files,
            "trainer_permissions": trainer_permissions,
            "labels_permissions": labels_permissions
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/debug/create-test-files', methods=['GET'])
def create_test_files():
    """
    ایجاد فایل‌های تستی
    """
    try:
        # اطمینان از وجود پوشه‌ها
        os.makedirs("trainer", exist_ok=True)
        os.makedirs("labels", exist_ok=True)
        
        # ایجاد فایل مدل تستی
        with open("trainer/model.xml", 'w', encoding='utf-8') as f:
            f.write("<model>Test Model</model>")
        
        # ایجاد فایل نگاشت برچسب‌ها
        mapping_data = {"1234567890": 1}
        with open("labels/label_mapping.json", 'w', encoding='utf-8') as f:
            json.dump(mapping_data, f, ensure_ascii=False, indent=4)
        
        # ایجاد فایل لیبل‌ها
        labels_data = {"1": {"nationalCode": "1234567890", "fullName": "کاربر تست"}}
        with open("labels/labels_to_name.json", 'w', encoding='utf-8') as f:
            json.dump(labels_data, f, ensure_ascii=False, indent=4)
        
        return jsonify({
            "status": "success",
            "message": "فایل‌های تستی با موفقیت ایجاد شدند."
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# مسیرهای جدید برای دسترسی به فایل‌ها
@app.route('/public-model', methods=['GET'])
def public_model():
    """
    ارسال فایل مدل XML به درخواست‌کننده بدون احراز هویت
    """
    try:
        model_path = os.path.join("trainer", "model.xml")
        if not os.path.exists(model_path):
            return jsonify({"status": "error", "message": "فایل مدل یافت نشد."}), 404
        
        return send_file(model_path, mimetype='application/xml')
    except Exception as e:
        logging.error("خطا در ارسال فایل مدل: %s", e)
        return jsonify({"status": "error", "message": "خطا در ارسال فایل مدل."}), 500

@app.route('/public-files/<path:filename>', methods=['GET'])
def public_files(filename):
    """
    ارسال فایل‌ها بدون احراز هویت
    """
    try:
        # ابتدا بررسی می‌کنیم فایل در پوشه trainer وجود دارد
        trainer_path = os.path.join("trainer", filename)
        if os.path.exists(trainer_path):
            return send_file(trainer_path)
        
        # سپس بررسی می‌کنیم فایل در پوشه labels وجود دارد
        labels_path = os.path.join("labels", filename)
        if os.path.exists(labels_path):
            return send_file(labels_path)
        
        return jsonify({"status": "error", "message": f"فایل {filename} یافت نشد."}), 404
    except Exception as e:
        logging.error(f"خطا در ارسال فایل {filename}: {e}")
        return jsonify({"status": "error", "message": f"خطا در ارسال فایل {filename}"}), 500

# --------------------- اجرای سرور ---------------------
if __name__ == '__main__':
    # اجرای فلسک در حالت دسترس از همه آدرس‌ها برای استفاده در داکر
    app.run(host='0.0.0.0', port=5000, debug=True)