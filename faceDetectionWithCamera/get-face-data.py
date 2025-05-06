#!/usr/bin/env python3
import os
import base64
import logging
import numpy as np
import cv2
import redis
from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3
from botocore.exceptions import NoCredentialsError

# --------------------- تنظیمات اولیه ---------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
try:
    redis_client = redis.StrictRedis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)
    redis_client.ping()
    logging.info("اتصال به Redis با موفقیت برقرار شد.")
except Exception as e:
    logging.error("خطا در اتصال به Redis: %s", e)
    exit(1)

app = Flask(__name__)
CORS(app)

HAAR_CASCADE_PATHS = {
    "face": "assets/face_detection/haarcascade_frontalface_default.xml",
    "eye": "assets/face_detection/haarcascade_eye.xml"
}
for key, path in HAAR_CASCADE_PATHS.items():
    if not os.path.exists(path):
        raise FileNotFoundError(f"فایل Haar Cascade برای {key} در مسیر {path} یافت نشد.")

face_cascade = cv2.CascadeClassifier(HAAR_CASCADE_PATHS["face"])
eye_cascade = cv2.CascadeClassifier(HAAR_CASCADE_PATHS["eye"])

LIARA_ACCESS_KEY = 'u2cgc3ev1i29tmeg'
LIARA_SECRET_KEY = '46c86213-2684-4421-9c1d-7d96cb22ac14'
LIARA_BUCKET_NAME = 'photo-attendance-system'
LIARA_ENDPOINT_URL = 'https://storage.c2.liara.space'

s3_client = boto3.client('s3',
                         aws_access_key_id=LIARA_ACCESS_KEY,
                         aws_secret_access_key=LIARA_SECRET_KEY,
                         endpoint_url=LIARA_ENDPOINT_URL)

def upload_to_liara(national_code, color_image_data):
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
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)
        if len(faces) == 0:
            logging.warning("هیچ چهره‌ای در تصویر شناسایی نشد.")
            return None, None
        for (x, y, w, h) in faces:
            face_gray = gray[y:y + h, x:x + w]
            face_color = image[y:y + h, x:x + w]
            resized_gray = cv2.resize(face_gray, (200, 200))
            resized_color = cv2.resize(face_color, (200, 200))
            eyes = eye_cascade.detectMultiScale(resized_gray)
            if len(eyes) < 2:
                logging.warning("چهره شناسایی شده چشم‌های کافی ندارد.")
                continue
            return resized_gray, resized_color
        return None, None
    except Exception as e:
        logging.error("خطا در پردازش تصویر: %s", e)
        return None, None

def save_to_redis(national_code, face_image_gray):
    try:
        success, buffer = cv2.imencode('.jpg', face_image_gray, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not success:
            raise ValueError("خطا در رمزگذاری تصویر به JPEG.")
        face_base64 = base64.b64encode(buffer).decode('utf-8')
        redis_client.setex(national_code, 60 * 60 * 24 * 30, face_base64)
        logging.info(f"تصویر چهره برای کد ملی {national_code} در Redis ذخیره شد.")
    except Exception as e:
        logging.error(f"خطا در ذخیره تصویر در Redis: {e}")
        raise

@app.route('/register-face', methods=['POST'])
def register_face():
    data = request.get_json()
    national_code = data.get('nationalCode')
    face_base64 = data.get('faceImage')
    if not national_code or not face_base64:
        return jsonify({"error": "کد ملی یا تصویر ارسال نشده است."}), 400
    try:
        image = base64_to_cv2_image(face_base64)
        face_gray, face_color = detect_and_validate_face(image)
        if face_gray is None or face_color is None:
            return jsonify({"error": "چهره معتبر شناسایی نشد."}), 400
        save_to_redis(national_code, face_gray)
        _, color_buffer = cv2.imencode('.jpg', face_color, [cv2.IMWRITE_JPEG_QUALITY, 95])
        upload_to_liara(national_code, color_buffer.tobytes())
        return jsonify({"message": "تصویر با موفقیت ذخیره شد."}), 200
    except Exception as e:
        logging.error(f"خطا در ثبت چهره: {e}")
        return jsonify({"error": "خطا در ثبت چهره."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)