from flask import Flask, request, send_file, render_template_string, make_response
import cv2
import numpy as np
import os
import zipfile
import time
import requests
import threading
from werkzeug.utils import secure_filename

# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
PHP_DOMAIN = "https://jharkhand.govt.hu"   # ←← TERA DOMAIN
# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp'
app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024
os.makedirs('/tmp', exist_ok=True)

DEDUCT_API = f"{PHP_DOMAIN}/deduct.php"
DASHBOARD_URL = f"{PHP_DOMAIN}/dashboard.php?success=1"

# Global storage for ZIP files
ZIP_STORAGE = {}

HTML = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fingerprint Enhancer</title>
<style>
    body{margin:0;background:linear-gradient(135deg,#667eea,#764ba2);display:flex;justify-content:center;align-items:center;min-height:100vh;font-family:Arial}
    .box{background:white;padding:40px;border-radius:20px;box-shadow:0 20px 50px rgba(0,0,0,0.3);width:90%;max-width:500px;text-align:center}
    h1{font-size:32px;color:#333}
    input[type=file],button{width:100%;padding:15px;margin:15px 0;border-radius:12px}
    input[type=file]{border:2px dashed #667eea;background:#f9f9ff}
    button{background:#667eea;color:white;border:none;font-size:20px;cursor:pointer}
    .error{background:#ffebee;color:red;padding:15px;border-radius:10px;margin:15px 0}
</style></head><body>
<div class="box">
    <h1>Fingerprint Enhancer</h1>
    <p>Upload 1-5 fingerprint images</p>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="post" enctype="multipart/form-data">
        <input type="hidden" name="token" value="{{ token }}">
        <input type="hidden" name="user_id" value="{{ user_id }}">
        <input type="file" name="files" accept="image/*" multiple required>
        <button type="submit">Enhance Now (₹10)</button>
    </form>
</div></body></html>'''

SUCCESS_PAGE = '''<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Downloading...</title>
<meta http-equiv="refresh" content="5;url={dashboard}">
<style>
    body{background:#f8f9fa;font-family:Arial;display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;margin:0}
    .box{background:white;padding:70px;border-radius:20px;box-shadow:0 15px 40px rgba(0,0,0,0.15);text-align:center}
    h2{color:#28a745;font-size:38px;margin:10px 0}
    .spinner{border:10px solid #f3f3f3;border-top:10px solid #28a745;border-radius:50%;width:70px;height:70px;animation:s 1s linear infinite;margin:25px auto}
    @keyframes s{to{transform:rotate(360deg)}}
</style></head><body>
<div class="box">
    <div class="spinner"></div>
    <h2>Done!</h2>
    <p>₹10 deducted • File downloading automatically</p>
    <p>Redirecting in <b id="c">5</b> seconds...</p>
</div>
<script>
    var a = document.createElement('a');
    a.href = '{zip_url}';
    a.download = 'CLEAN_Fingerprints.zip';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    var s=5; setInterval(()=>{document.getElementById('c').innerText=--s;},1000);
</script>
</body></html>'''

@app.route('/', methods=['GET', 'POST'])
def index():
    token = request.args.get('token')
    user_id = request.args.get('user_id')
    if not token or not user_id:
        return "<h2>Invalid Access</h2>", 403

    if request.method == 'POST':
        files = request.files.getlist('files')
        if not 1 <= len(files) <= 5:
            return render_template_string(HTML, error="Upload 1-5 images only!", token=token, user_id=user_id)

        processed = []
        temp_files = []

        try:
            # IMPORT YAHAN KAR RAHE HAIN (lazy import — Render pe safe)
            from fingerprint_enhancer import enhance_fingerprint

            for file in files:
                if not file or not file.filename:
                    continue
                filename = secure_filename(file.filename)
                input_path = f"/tmp/input_{int(time.time()*1000)}_{filename}"
                file.save(input_path)
                temp_files.append(input_path)

                img = cv2.imread(input_path, cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue

                # Resize if too large
                if max(img.shape) > 1200:
                    scale = 1200 / max(img.shape)
                    img = cv2.resize(img, (int(img.shape[1]*scale), int(img.shape[0]*scale)))

                # ENHANCE
                enhanced = enhance_fingerprint(img)
                enhanced = (np.clip(enhanced, 0, 1) * 255).astype(np.uint8)
                enhanced = 255 - enhanced  # Invert for clean look

                output_path = f"/tmp/CLEAN_{filename}"
                cv2.imwrite(output_path, enhanced)
                processed.append((f"CLEAN_{filename}", output_path))

            if not processed:
                return render_template_string(HTML, error="No valid fingerprint found!", token=token, user_id=user_id)

            # ZIP
            zip_name = f"clean_{user_id}_{int(time.time())}.zip"
            zip_path = f"/tmp/{zip_name}"
            with zipfile.ZipFile(zip_path, 'w') as z:
                for name, path in processed:
                    z.write(path, name)

            # Deduct ₹10
            try:
                r = requests.post(DEDUCT_API, data={'token': token, 'user_id': user_id}, timeout=10)
                if not r.json().get('success'):
                    for p in temp_files + [p[1] for p in processed] + [zip_path]:
                        if os.path.exists(p): os.unlink(p)
                    return render_template_string(HTML, error="Low balance!", token=token, user_id=user_id)
            except:
                return render_template_string(HTML, error="Payment server down!", token=token, user_id=user_id)

            # Store ZIP
            ZIP_STORAGE[zip_name] = zip_path
            download_url = request.url_root + "dl/" + zip_name

            # Auto cleanup after 3 minutes
            def cleanup():
                time.sleep(180)
                if os.path.exists(zip_path):
                    os.unlink(zip_path)
                ZIP_STORAGE.pop(zip_name, None)
            threading.Thread(target=cleanup, daemon=True).start()

            return SUCCESS_PAGE.format(dashboard=DASHBOARD_URL, zip_url=download_url)

        except Exception as e:
            print("ERROR:", str(e))  # Render logs me dikhega
            return render_template_string(HTML, error="Processing failed! Try again.", token=token, user_id=user_id)

    return render_template_string(HTML, error=None, token=token, user_id=user_id)


@app.route('/dl/<filename>')
def download_zip(filename):
    if '..' in filename or '/' in filename:
        return "Invalid", 400
    path = ZIP_STORAGE.get(filename)
    if not path or not os.path.exists(path):
        return "File expired!", 404
    return send_file(path, as_attachment=True, download_name="CLEAN_Fingerprints.zip")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
