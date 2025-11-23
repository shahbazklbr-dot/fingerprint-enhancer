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

PHP_DOMAIN = "https://jharkhand.govt.hu"

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp'
app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024
os.makedirs('/tmp', exist_ok=True)

DEDUCT_API = f"{PHP_DOMAIN}/deduct.php"
DASHBOARD_URL = f"{PHP_DOMAIN}/dashboard.php?success=1"

ZIP_STORAGE = {}

HTML = """<!DOCTYPE html><html><head><meta charset='UTF-8'>
<title>Fingerprint Enhancer</title>
<style>
body{margin:0;padding:0;font-family:Arial;background:#f0f2f5;display:flex;justify-content:center;align-items:center;height:100vh}
.box{background:white;padding:40px;border-radius:20px;box-shadow:0 10px 25px rgba(0,0,0,0.1);width:90%;max-width:450px;text-align:center}
input[type=file]{padding:14px;width:100%;border:1px solid #ddd;border-radius:10px;background:#fafafa}
button{margin-top:20px;padding:15px;background:#007bff;color:white;border:none;width:100%;font-size:18px;border-radius:10px;cursor:pointer}
.error{background:#ffe6e6;color:#d10000;padding:12px;border-radius:10px;margin-bottom:10px}
</style></head>
<body>
<div class="box">
    <h2>Fingerprint Enhancer</h2>
    <p>Upload 1–5 fingerprints</p>
    {% if error %}<div class="error">{{error}}</div>{% endif %}
    <form method="POST" enctype="multipart/form-data">
        <input type="hidden" name="token" value="{{ token }}">
        <input type="hidden" name="user_id" value="{{ user_id }}">
        <input type="file" name="files" accept="image/*" multiple required>
        <button type="submit">Enhance (₹10)</button>
    </form>
</div>
</body></html>"""

SUCCESS_PAGE = """<!DOCTYPE html><html><head><meta charset='UTF-8'>
<title>Downloading...</title>
<meta http-equiv="refresh" content="5;url={dashboard}">
<style>
body{background:#f0f2f5;font-family:Arial;display:flex;justify-content:center;align-items:center;height:100vh}
.box{background:white;padding:50px;border-radius:20px;text-align:center;box-shadow:0 10px 25px rgba(0,0,0,0.1)}
.spinner{width:60px;height:60px;border:7px solid #eee;border-top-color:#28a745;border-radius:50%;animation:spin 1s linear infinite;margin:20px auto}
@keyframes spin{100%{transform:rotate(360deg)}}
</style></head><body>
<div class="box">
    <div class="spinner"></div>
    <h2>Done!</h2>
    <p>₹10 deducted • Download starting...</p>
</div>
<script>
var a=document.createElement('a');
a.href='{zip_url}';
a.download='CLEAN_Fingerprints.zip';
document.body.appendChild(a);a.click();a.remove();
</script>
</body></html>"""

def safe_read(path):
    """Convert any image safely → grayscale numpy."""
    try:
        img = Image.open(path)

        if img.mode not in ["RGB", "L", "GRAY"]:
            img = img.convert("RGB")

        img = np.array(img)

        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

        return img
    except:
        return cv2.imread(path, 0)


@app.route('/', methods=['GET', 'POST'])
def index():
    token = request.args.get('token')
    user_id = request.args.get('user_id')

    if not token or not user_id:
        return "<h2>Invalid Access</h2>", 403

    if request.method == 'POST':
        files = request.files.getlist("files")

        if not (1 <= len(files) <= 5):
            return render_template_string(HTML, error="Upload 1-5 files only!", token=token, user_id=user_id)

        processed = []

        for file in files:
            filename = secure_filename(file.filename)
            input_path = f"/tmp/{int(time.time()*1000)}_{filename}"
            file.save(input_path)

            img = safe_read(input_path)
            if img is None:
                continue

            # EXACTLY SAME RESIZE AS YOUR WORKING CODE
            max_dim = 800
            h, w = img.shape
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)))

            # EXACT SAME ENHANCER BEHAVIOR LIKE WORKING CODE
            try:
                enhanced = enhance_fingerprint(img)
            except Exception as e:
                print("ENHANCE ERROR:", e)
                return render_template_string(HTML, error="Bad fingerprint! Try a clearer one.", token=token, user_id=user_id)

            final = (enhanced.astype(np.uint8) * 255)
            final = 255 - final  # SAME CLEAN LOOK

            output_path = f"/tmp/CLEAN_{filename}"
            cv2.imwrite(output_path, final)
            processed.append((filename, output_path))

        if not processed:
            return render_template_string(HTML, error="No valid fingerprints found!", token=token, user_id=user_id)

        # MAKE ZIP
        zip_name = f"clean_{user_id}_{int(time.time())}.zip"
        zip_path = f"/tmp/{zip_name}"

        with zipfile.ZipFile(zip_path, 'w') as z:
            for original, cleaned in processed:
                z.write(cleaned, os.path.basename(cleaned))

        # PAYMENT
        try:
            r = requests.post(DEDUCT_API, data={'token': token, 'user_id': user_id}, timeout=10)
            if not r.json().get("success"):
                return render_template_string(HTML, error="Low balance!", token=token, user_id=user_id)
        except:
            return render_template_string(HTML, error="Payment server offline!", token=token, user_id=user_id)

        ZIP_STORAGE[zip_name] = zip_path
        download_url = request.url_root + "dl/" + zip_name

        # AUTO CLEANUP
        def cleanup():
            time.sleep(180)
            if os.path.exists(zip_path):
                os.unlink(zip_path)
            ZIP_STORAGE.pop(zip_name, None)

        threading.Thread(target=cleanup, daemon=True).start()

        return SUCCESS_PAGE.format(dashboard=DASHBOARD_URL, zip_url=download_url)

    return render_template_string(HTML, token=token, user_id=user_id, error=None)


@app.route('/dl/<filename>')
def download_zip(filename):
    path = ZIP_STORAGE.get(filename)
    if not path or not os.path.exists(path):
        return "Expired or invalid!", 404
    return send_file(path, as_attachment=True, download_name="CLEAN_Fingerprints.zip")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
