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

HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset='UTF-8'>
<title>Fingerprint Enhancer</title>
<meta name="viewport" content="width=device-width, initial-scale=1">

<style>
body{
    margin:0;
    padding:0;
    font-family: 'Segoe UI', sans-serif;
    background: linear-gradient(135deg,#667eea,#764ba2);
    height:100vh;
    display:flex;
    justify-content:center;
    align-items:center;
}

/* Glass Card */
.box{
    width:90%;
    max-width:460px;
    padding:40px;
    background:rgba(255,255,255,0.15);
    backdrop-filter:blur(12px);
    border-radius:22px;
    box-shadow:0 10px 35px rgba(0,0,0,0.25);
    text-align:center;
    animation:fadeIn 0.7s ease;
}

@keyframes fadeIn{
    from{opacity:0;transform:translateY(20px);}
    to{opacity:1;transform:translateY(0);}
}

h2{
    font-size:32px;
    font-weight:700;
    color:white;
    margin-bottom:8px;
}

p{
    color:#f1f1f1;
    margin-bottom:25px;
    font-size:16px;
}

/* File Upload */
input[type=file]{
    width:100%;
    padding:13px;
    border-radius:12px;
    background:white;
    border:2px dashed #e3e6ff;
    font-size:16px;
    cursor:pointer;
}

/* Button */
button{
    width:100%;
    padding:16px;
    margin-top:20px;
    background:#00d084;
    color:white;
    font-size:20px;
    border:none;
    border-radius:12px;
    cursor:pointer;
    transition:0.25s;
    font-weight:600;
}

button:hover{
    background:#00b070;
    transform:translateY(-3px);
    box-shadow:0 6px 18px rgba(0,0,0,0.2);
}

/* Error Box */
.error{
    background:#ffebee;
    color:#d80000;
    padding:12px;
    border-radius:12px;
    margin-bottom:15px;
    animation:shake 0.3s;
}

@keyframes shake{
    25%{transform:translateX(-4px);}
    50%{transform:translateX(4px);}
    75%{transform:translateX(-4px);}
}
</style>
</head>

<body>
<div class="box">
    <h2>Fingerprint Enhancer</h2>
    <p>Upload 1–5 fingerprint images</p>

    {% if error %}
        <div class="error">{{error}}</div>
    {% endif %}

    <form method="POST" enctype="multipart/form-data">
        <input type="hidden" name="token" value="{{ token }}">
        <input type="hidden" name="user_id" value="{{ user_id }}">

        <input type="file" name="files" accept="image/*" multiple required>

        <button type="submit">Enhance (₹10)</button>
    </form>
</div>
</body>
</html>"""



def safe_read(path):
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
            return render_template_string(HTML, error="Upload 1–5 files only!", token=token, user_id=user_id)

        processed = []

        for file in files:
            filename = secure_filename(file.filename)
            input_path = f"/tmp/{int(time.time()*1000)}_{filename}"
            file.save(input_path)

            img = safe_read(input_path)
            if img is None:
                continue

            max_dim = 800
            h, w = img.shape
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)))

            try:
                enhanced = enhance_fingerprint(img)
            except:
                return render_template_string(HTML, error="Bad fingerprint! Try again.", token=token, user_id=user_id)

            final = (enhanced.astype(np.uint8) * 255)
            final = 255 - final

            output_path = f"/tmp/CLEAN_{filename}"
            cv2.imwrite(output_path, final)
            processed.append(output_path)

        if not processed:
            return render_template_string(HTML, error="No valid fingerprints found!", token=token, user_id=user_id)

        zip_name = f"clean_{user_id}_{int(time.time())}.zip"
        zip_path = f"/tmp/{zip_name}"

        with zipfile.ZipFile(zip_path, 'w') as z:
            for fpath in processed:
                z.write(fpath, os.path.basename(fpath))

        try:
            r = requests.post(DEDUCT_API, data={'token': token, 'user_id': user_id}, timeout=10)
            if not r.json().get("success"):
                return render_template_string(HTML, error="Low balance!", token=token, user_id=user_id)
        except:
            return render_template_string(HTML, error="Payment server offline!", token=token, user_id=user_id)

        ZIP_STORAGE[zip_name] = zip_path
        download_url = request.url_root + "dl/" + zip_name

        def cleanup():
            time.sleep(180)
            if os.path.exists(zip_path):
                os.unlink(zip_path)
            ZIP_STORAGE.pop(zip_name, None)

        threading.Thread(target=cleanup, daemon=True).start()

        page = SUCCESS_PAGE.replace("{dashboard}", DASHBOARD_URL).replace("{zip_url}", download_url)
        return page

    return render_template_string(HTML, token=token, user_id=user_id, error=None)


@app.route('/dl/<filename>')
def download_zip(filename):
    path = ZIP_STORAGE.get(filename)
    if not path or not os.path.exists(path):
        return "Expired or invalid!", 404
    return send_file(path, as_attachment=True, download_name="CLEAN_Fingerprints.zip")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
