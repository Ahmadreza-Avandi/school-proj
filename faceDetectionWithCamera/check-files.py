#!/usr/bin/env python3
import os
import json
from flask import Flask, jsonify

app = Flask(__name__)

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
        
        # ایجاد پوشه‌ها و فایل‌های خالی برای تست در صورت عدم وجود
        if not trainer_dir:
            os.makedirs("trainer", exist_ok=True)
        
        if not labels_dir:
            os.makedirs("labels", exist_ok=True)
            
        if not mapping_file:
            with open("labels/label_mapping.json", 'w', encoding='utf-8') as f:
                json.dump({}, f)
            
        if not labels_file:
            with open("labels/labels_to_name.json", 'w', encoding='utf-8') as f:
                json.dump({}, f)
        
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 