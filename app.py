from flask import Flask, request, send_file, render_template_string, make_response
from fingerprint_enhancer import enhance_fingerprint
import cv2, numpy as np, os, zipfile, time, requests
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp'
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024
os.makedirs('/tmp', exist_ok=True)

# ←← APNA DOMAIN YAHAN DAAL ←←
PHP_DOMAIN = "https://jharkhand.govt.hu"  # ←← Tera domain
DEDUCT_API = f"{PHP_DOMAIN}/deduct.php"
DASHBOARD_URL = f"{PHP_DOMAIN}/dashboard.php?success=1"

# Ye global rakho taaki download route access kar sake
TEMP_ZIP_FILES = {}  # {zip_filename: full_path}

HTML = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fingerprint Enhancer</title>
<style>
    body{margin:0;padding:0;font-family:Arial;background:linear-gradient(135deg,#667eea,#764ba2);display:flex;justify-content:center;align-items:center;min-height:100vh}
    .box{max-width:500px;width:90%;background:white;padding:40px;border-radius:20px;text-align:center;box-shadow:0 15px 40px rgba(0,0,0,0.3)}
    h1{color:#333;font-size:32px;margin-bottom:10px}
    input[type=file],button{width:100%;padding:15px;margin:15px 0;border-radius:12px}
    input[type=file]{border:2px dashed #667eea;background:#f8f9fa}
    button{background:#667eea;color:white;border:none;font-size:20px;cursor:pointer}
    .error{color:red;background:#ffe6e6;padding:15px;border-radius:8px;margin:15px 0}
</style></head><body>
<div class="box">
    <h1>Fingerprint Enhancer</h1>
    <p>Upload up to 5 fingerprints</p>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="post" enctype="multipart/form-data">
        <input type="hidden" name="token" value="{{ token }}">
        <input type="hidden" name="user_id" value="{{ user_id }}">
        <input type="file" name="files" accept="image/*" multiple required>
        <button type="submit">Enhance Now (₹10)</button>
    </form>
</div></body></html>'''

# SUCCESS PAGE + AUTO DOWNLOAD + REDIRECT
SUCCESS_PAGE = '''<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Downloading...</title>
<meta http-equiv="refresh" content="5;url={dashboard_url}">
<style>
    body{background:#f0f8ff;font-family:Arial;display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;margin:0}
    .box{background:white;padding:60px;border-radius:20px;box-shadow:0 10px 30px rgba(0,0,0,0.2);text-align:center}
    h2{color:#28a745;font-size:36px}
    .loader{border:10px solid #f3f3f3;border-top:10px solid #28a745;border-radius:50%;width:70px;height:70px;animation:spin 1s linear infinite;margin:20px auto}
    @keyframes spin {0% {transform:rotate(0deg)} 100% {transform:rotate(360deg)}}
</style>
</head><body>
<div class="box">
    <div class="loader"></div>
    <h2>Enhancement Complete!</h2>
    <p>₹10 deducted successfully</p>
    <p><strong>Download starting automatically...</strong></p>
    <p>Redirecting in <span id="countdown">5</span> seconds...</p>
</div>
<script>
// Auto download
var link = document.createElement('a');
link.href = '{download_url}';
link.download = 'CLEAN_Fingerprints.zip';
document.body.appendChild(link);
link.click();
document.body.removeChild(link);

// Countdown
var secs = 5;
setInterval(function() {
    secs--;
    document.getElementById("countdown").innerText = secs;
}, 1000);
</script>
</body></html>'''

@app.route('/', methods=['GET', 'POST'])
def index():
    token = request.args.get('token')
    user_id = request.args.get('user_id')
    
    if not token or not user_id:
        return "<h2>Access Denied</h2>", 403

    if request.method == 'POST':
        files = request.files.getlist('files')
        if not (1 <= len(files) <= 5):
            return render_template_string(HTML, error="Select 1-5 images!", token=token, user_id=user_id)

        outputs = []
        temps = []

        try:
            for file in files:
                if not file.filename: continue
                name = secure_filename(file.filename)
                in_path = f"/tmp/in_{int(time.time()*1000)}_{name}"
                file.save(in_path)
                temps.append(in_path)

                img = cv2.imread(in_path, 0)
                if img is None: continue
                if max(img.shape) > 1000:
                    scale = 1000 / max(img.shape)
                    img = cv2.resize(img, (int(img.shape[1]*scale), int(img.shape[0]*scale)))

                enhanced = enhance_fingerprint(img)
                final = (np.clip(enhanced, 0, 1) * 255).astype(np.uint8)
                final = 255 - final
                out_path = f"/tmp/CLEAN_{name}"
                cv2.imwrite(out_path, final)
                outputs.append((name, out_path))

            if not outputs:
                return render_template_string(HTML, error="No valid image!", token=token, user_id=user_id)

            # ZIP banao
            zip_filename = f"enhanced_{user_id}_{int(time.time())}.zip"
            zip_path = f"/tmp/{zip_filename}"
            with zipfile.ZipFile(zip_path, 'w') as z:
                for name, path in outputs:
                    z.write(path, f"CLEAN_{name}")

            # Balance deduct
            try:
                r = requests.post(DEDUCT_API, data={'token': token, 'user_id': user_id}, timeout=10)
                if not r.json().get('success'):
                    # Cleanup if payment fail
                    for p in temps + [p[1] for p in outputs] + [zip_path]:
                        if os.path.exists(p): os.unlink(p)
                    return render_template_string(HTML, error="Insufficient balance!", token=token, user_id=user_id)
            except:
                return render_template_string(HTML, error="Server error!", token=token, user_id=user_id)

            # File ko global dict me daal do
            TEMP_ZIP_FILES[zip_filename] = zip_path

            # Download URL banao
            download_url = request.url_root + "download/" + zip_filename

            # Success page dikhao (auto download + redirect)
            return SUCCESS_PAGE.format(
                dashboard_url=DASHBOARD_URL,
                download_url=download_url
            )

        except Exception as e:
            return render_template_string(HTML, error="Processing failed! Try again.", token=token, user_id=user_id)

    return render_template_string(HTML, error=None, token=token, user_id=user_id)


# NAYA ROUTE: Direct download
@app.route('/download/<filename>')
def download_file(filename):
    if '..' in filename or '/' in filename:
        return "Bad request!", 400
    file_path = TEMP_ZIP_FILES.get(filename)
    if not file_path or not os.path.exists(file_path):
        return "File expired or not found!", 404

    response = make_response(send_file(file_path, as_attachment=True, download_name="CLEAN_Fingerprints.zip"))
    
    # File delete 2 minute baad (safe)
    def delayed_delete():
        import time; time.sleep(120)
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
                TEMP_ZIP_FILES.pop(filename, None)
        except: pass
    import threading
    threading.Thread(target=delayed_delete).start()

    return response


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
