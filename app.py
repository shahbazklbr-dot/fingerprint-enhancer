from flask import Flask, request, send_file, render_template_string, make_response, url_for
from werkzeug.utils import secure_filename
import cv2
import numpy as np
import os
import zipfile
import time
import requests
import threading

# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
PHP_DOMAIN = "https://jharkhand.govt.hu"   # ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp'
os.makedirs('/tmp', exist_ok=True)

DEDUCT_URL   = f"{PHP_DOMAIN}/deduct.php"
DASHBOARD_URL = f"{PHP_DOMAIN}/dashboard.php?success=1"

# Keep files for 2 minutes (cleanup background)
CLEANUP_FILES = {}

def background_cleanup(filepath, delay=120):
    time.sleep(delay)
    try:
        if os.path.exists(filepath):
            os.unlink(filepath)
    except:
        pass

HTML = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fingerprint Enhancer</title>
<style>
    body{margin:0;padding:0;background:linear-gradient(135deg,#667eea,#764ba2);display:flex;justify-content:center;align-items:center;min-height:100vh;font-family:Arial}
    .box{background:white;padding:40px;border-radius:20px;box-shadow:0 15px 40px rgba(0,0,0,0.3);width:90%;max-width:500px;text-align:center}
    h1{font-size:32px;color:#333;margin-bottom:10px}
    input[type=file],button{width:100%;padding:15px;margin:15px 0;border-radius:12px}
    input[type=file]{border:2px dashed #667eea;background:#f9f9ff}
    button{background:#667eea;color:white;border:none;font-size:20px;cursor:pointer}
    .error{background:#ffe6e6;color:red;padding:15px;border-radius:8px;margin:15px 0}
</style></head><body>
<div class="box">
    <h1>Fingerprint Enhancer</h1>
    <p>Upload 1–5 fingerprints</p>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="post" enctype="multipart/form-data">
        <input type="hidden" name="token" value="{{ token }}">
        <input type="hidden" name="user_id" value="{{ user_id }}">
        <input type="file" name="files" accept="image/*" multiple required>
        <button type="submit">Enhance Now (₹10)</button>
    </form>
</div></body></html>'''

SUCCESS_PAGE = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Downloading...</title>
<meta http-equiv="refresh" content="5;url={dashboard}">
<style>
    body{background:#f8f9fa;font-family:Arial;display:flex;flex-direction:column;justify-content:center;align-items:center;height:100vh;margin:0}
    .box{background:white;padding:60px 80px;border-radius:20px;text-align:center;box-shadow:0 15px 35px rgba(0,0,0,0.1)}
    h2{color:#28a745;font-size:34px}
    .spinner{border:8px solid #f3f3f3;border-top:8px solid #28a745;border-radius:50%;width:60px;height:60px;animation:s 1s linear infinite;margin:20px auto}
    @keyframes s {to{transform:rotate(360deg)}}
</style></head><body>
<div class="box">
    <div class="spinner"></div>
    <h2>Enhancement Complete!</h2>
    <p>₹10 deducted • File downloading automatically...</p>
    <p>Redirecting in <b id="c">5</b> seconds...</p>
</div>
<script>
    // Auto download
    const a = document.createElement('a');
    a.href = '{zip_url}';
    a.download = 'CLEAN_Fingerprints.zip';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    // Countdown
    let s = 5;
    setInterval(()=>{document.getElementById('c').innerText=--s;},1000);
</script>
</body></html>'''

@app.route('/', methods=['GET', 'POST'])
def index():
    token = request.args.get('token')
    user_id = request.args.get('user_id')
    if not token or not user_id:
        return "<h2>Invalid Link</h2>", 403

    if request.method == 'POST':
        files = request.files.getlist('files')
        if not 1 <= len(files) <= 5:
            return render_template_string(HTML, error="Upload 1–5 images only!", token=token, user_id=user_id)

        temp_paths = []
        output_paths = []

        try:
            # 1. Process each image
            for file in files:
                if not file.filename:
                    continue
                filename = secure_filename(file.filename)
                in_path = os.path.join('/tmp', f"in_{int(time.time()*1000)}_{filename}")
                file.save(in_path)
                temp_paths.append(in_path)

                img = cv2.imread(in_path, cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue

                # Resize if too big
                if max(img.shape) > 1200:
                    scale = 1200 / max(img.shape)
                    img = cv2.resize(img, (int(img.shape[1]*scale), int(img.shape[0]*scale)))

                # ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
                from fingerprint_enhancer import enhance_fingerprint   # ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
                enhanced = enhance_fingerprint(img)
                # ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←

                final = (np.clip(enhanced, 0, 1) * 255).astype(np.uint8)
                final = 255 - final

                out_name = "CLEAN_" + filename
                out_path = os.path.join('/tmp', out_name)
                cv2.imwrite(out_path, final)
                output_paths.append((out_name, out_path))

            if not output_paths:
                return render_template_string(HTML, error="No valid image found!", token=token, user_id=user_id)

            # 2. Create ZIP
            zip_name = f"enhanced_{user_id}_{int(time.time())}.zip"
            zip_path = os.path.join('/tmp', zip_name)
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
                for name, path in output_paths:
                    z.write(path, name)

            # 3. Deduct balance
            try:
                r = requests.post(DEDUCT_URL, data={'token': token, 'user_id': user_id}, timeout=10)
                if not r.json().get('success'):
                    [os.unlink(p) for p in temp_paths + [p[1] for p in output_paths] + [zip_path] if os.path.exists(p)]
                    return render_template_string(HTML, error="Low balance or payment failed!", token=token, user_id=user_id)
            except:
                return render_template_string(HTML, error="Payment server error!", token=token, user_id=user_id)

            # 4. Keep file for download
            download_url = request.url_root.rstrip('/') + url_for('download_file', filename=zip_name)
            CLEANUP_FILES[zip_name] = zip_path
            threading.Thread(target=background_cleanup, args=(zip_path, 120)).start()

            # 5. Success page with auto download
            return SUCCESS_PAGE.format(dashboard=DASHBOARD_URL, zip_url=download_url)

        except Exception as e:
            # Any error → show message
            return render_template_string(HTML, error="Processing failed! Try again.", token=token, user_id=user_id)

    return render_template_string(HTML, error=None, token=token, user_id=user_id)


@app.route('/download/<filename>')
def download_file(filename):
    if '..' in filename or '/' in filename:
        return "Invalid", 400
    path = CLEANUP_FILES.get(filename)
    if not path or not os.path.exists(path):
        return "File expired or not found", 404

    response = send_file(path, as_attachment=True, download_name="CLEAN_Fingerprints.zip")
    return response


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
