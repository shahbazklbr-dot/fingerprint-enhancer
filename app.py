from flask import Flask, request, send_file, render_template_string
import cv2
import numpy as np
import os
import zipfile
import time
import requests
import threading
from werkzeug.utils import secure_filename
from PIL import Image
from fingerprint_enhancer import enhance_fingerprint

# ======================== CONFIG ========================
PHP_DOMAIN = "https://enhance.strangled.net"
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024

# PERSISTENT ZIP FOLDER (सर्वर रीस्टार्ट होने पर भी ZIP रहेगी)
ZIP_FOLDER = "/home/ubuntu/enhance_zips"        # ← ये फोल्डर बनाना है
os.makedirs(ZIP_FOLDER, exist_ok=True)

UPLOAD_FOLDER = "/tmp"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DEDUCT_API = f"{PHP_DOMAIN}/deduct.php"
DASHBOARD_URL = f"{PHP_DOMAIN}/dashboard.php?success=1"

# ======================== HTML (तुम्हारा पुराना वही) ========================
HTML = """<!DOCTYPE html>
... तुम्हारा पूरा HTML यहाँ रहेगा (पहले जैसा) ...
"""

SUCCESS_PAGE = """<!DOCTYPE html>
... तुम्हारा पूरा SUCCESS_PAGE यहाँ रहेगा (पहले जैसा) ...
"""

# ======================== UTILS ========================
def safe_read(path):
    try:
        img = Image.open(path)
        if img.mode not in ("L", "RGB"):
            img = img.convert("RGB")
        arr = np.array(img)
        if arr.ndim == 3:
            arr = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        return arr
    except:
        return cv2.imread(path, cv2.IMREAD_GRAYSCALE)

def make_zip_from_paths(paths, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            if os.path.exists(p):
                zf.write(p, os.path.basename(p))

def cleanup_file(path, delay=300):  # 5 मिनट बाद डिलीट
    def _cleanup():
        time.sleep(delay)
        try:
            if os.path.exists(path):
                os.remove(path)
                print(f"Auto-cleaned: {path}")
        except:
            pass
    threading.Thread(target=_cleanup, daemon=True).start()

# ======================== MAIN ROUTE ========================
@app.route('/', methods=['GET', 'POST'])
def index():
    token = request.args.get('token')
    user_id = request.args.get('user_id')
    if not token or not user_id:
        return "<h2>Invalid Access</h2>", 403

    if request.method == "POST":
        files = request.files.getlist("files")
        if not files or len(files) == 0 or len(files) > 5:
            return render_template_string(HTML, error="Select 1-5 images!", token=token, user_id=user_id)

        processed_paths = []
        temp_paths = []

        for file in files:
            if not file or not file.filename:
                continue
            filename = secure_filename(file.filename)
            input_path = os.path.join(UPLOAD_FOLDER, f"{int(time.time()*1000)}_{filename}")
            file.save(input_path)
            temp_paths.append(input_path)

            img = safe_read(input_path)
            if img is None:
                continue

            h, w = img.shape[:2]
            if max(h, w) > 800:
                scale = 800 / max(h, w)
                img = cv2.resize(img, (int(w*scale), int(h*scale)))

            try:
                enhanced = enhance_fingerprint(img)
                final = (np.clip(enhanced, 0, 1) * 255).astype(np.uint8)
                final = 255 - final
            except Exception as e:
                print("Enhancer error:", e)
                continue

            output_name = f"CLEAN_{filename}"
            output_path = os.path.join(UPLOAD_FOLDER, output_name)
            cv2.imwrite(output_path, final)
            processed_paths.append(output_path)

        if not processed_paths:
            for p in temp_paths:
                try: os.remove(p)
                except: pass
            return render_template_string(HTML, error="No valid fingerprint found!", token=token, user_id=user_id)

        # ZIP बनाओ — persistent folder में
        timestamp = int(time.time())
        zip_name = f"clean_{user_id}_{timestamp}.zip"
        zip_path = os.path.join(ZIP_FOLDER, zip_name)
        make_zip_from_paths(processed_paths, zip_path)

        # Payment deduct
        try:
            r = requests.post(DEDUCT_API, data={'token': token, 'user_id': user_id}, timeout=10)
            if not r.json().get("success"):
                os.remove(zip_path)
                for p in processed_paths + temp_paths:
                    try: os.remove(p)
                    except: pass
                return render_template_string(HTML, error="Insufficient balance!", token=token, user_id=user_id)
        except:
            os.remove(zip_path)
            for p in processed_paths + temp_paths:
                try: os.remove(p)
                except: pass
            return render_template_string(HTML, error="Payment failed!", token=token, user_id=user_id)

        # ZIP को 5 मिनट बाद डिलीट करो
        cleanup_file(zip_path, delay=300)

        # टेंप फाइल्स अभी डिलीट करो
        for p in processed_paths + temp_paths:
            try: os.remove(p)
            except: pass

        download_url = f"https://enhance.mooo.com/dl/{zip_name}"
        page = SUCCESS_PAGE.replace("{dashboard}", DASHBOARD_URL).replace("{zip_url}", download_url)
        return page

    return render_template_string(HTML, token=token, user_id=user_id, error=None)

# ======================== DOWNLOAD ROUTE ========================
@app.route("/dl/<zipfile>")
def download(zipfile):
    if ".." in zipfile or not zipfile.startswith("clean_"):
        return "Bad request!", 400

    zip_path = os.path.join(ZIP_FOLDER, zipfile)
    if not os.path.exists(zip_path):
        return "File expired or already downloaded!", 404

    response = send_file(zip_path, as_attachment=True, download_name="CLEAN_Fingerprints.zip")

    # डाउनलोड शुरू होते ही फाइल डिलीट कर दो (सुरक्षा + स्पेस बचत)
    def delete_now():
        time.sleep(3)
        try:
            os.remove(zip_path)
        except:
            pass
    threading.Thread(target=delete_now, daemon=True).start()

    return response

# ======================== START ========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=False)
