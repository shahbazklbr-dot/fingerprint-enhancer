from flask import Flask, request, send_file, render_template_string, make_response
from fingerprint_enhancer import enhance_fingerprint
import cv2, numpy as np, os, zipfile, time, requests
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp'
os.makedirs('/tmp', exist_ok=True)

# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
PHP_DOMAIN = "https://jharkhand.govt.hu"   # ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←

DEDUCT_URL = f"{PHP_DOMAIN}/deduct.php"
DASHBOARD_URL = f"{PHP_DOMAIN}/dashboard.php?success=1"

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

# SUCCESS PAGE WITH AUTO DOWNLOAD + REDIRECT
SUCCESS_HTML = '''<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Downloading...</title>
<meta http-equiv="refresh" content="4;url={dashboard}">
<style>
    body{background:#f8f9fa;font-family:Arial;display:flex;flex-direction:column;justify-content:center;align-items:center;height:100vh;margin:0}
    .box{background:white;padding:50px 70px;border-radius:20px;text-align:center;box-shadow:0 10px 30px rgba(0,0,0,0.1);max-width:500px}
    h2{color:#28a745;font-size:32px;margin:10px 0}
    .loader{border:8px solid #f3f3f3;border-top:8px solid #28a745;border-radius:50%;width:60px;height:60px;animation:spin 1s linear infinite;margin:20px auto}
    @keyframes spin {0% {{transform:rotate(0deg)}} 100% {{transform:rotate(360deg)}}}
</style>
</head><body>
<div class="box">
    <div class="loader"></div>
    <h2>Enhancement Complete!</h2>
    <p>₹10 deducted successfully.</p>
    <p><strong>Your file is downloading...</strong></p>
    <p>Redirecting to dashboard in <span id="count">4</span> seconds...</p>
</div>
<script>
    // Auto download trigger
    const link = document.createElement('a');
    link.href = '{zip_url}';
    link.download = 'CLEAN_Fingerprints.zip';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    // Countdown
    let sec = 4;
    setInterval(() => {
        sec--;
        document.getElementById('count').innerText = sec;
        if(sec <= 0) location.href = '{dashboard}';
    }, 1000);
</script>
</body></html>'''

@app.route('/', methods=['GET', 'POST'])
def index():
    token = request.args.get('token')
    user_id = request.args.get('user_id')
    
    if not token or not user_id:
        return "<h2>Access Denied</h2><p>Invalid link.</p>", 403

    if request.method == 'POST':
        files = request.files.getlist('files')
        if len(files) == 0 or len(files) > 5:
            return render_template_string(HTML, error="Select 1-5 images only!", token=token, user_id=user_id)

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
                return render_template_string(HTML, error="No valid image found!", token=token, user_id=user_id)

            # Create ZIP
            zip_path = f"/tmp/enhanced_{int(time.time())}_{user_id}.zip"
            with zipfile.ZipFile(zip_path, 'w') as z:
                for name, path in outputs:
                    z.write(path, f"CLEAN_{name}")

            # Deduct balance
            try:
                r = requests.post(DEDUCT_URL, data={'token': token, 'user_id': user_id}, timeout=10)
                if not r.json().get('success'):
                    os.unlink(zip_path)
                    return render_template_string(HTML, error="Payment failed! Contact admin.", token=token, user_id=user_id)
            except:
                os.unlink(zip_path)
                return render_template_string(HTML, error="Server error!", token=token, user_id=user_id)

            # Generate direct download URL (using /download route)
            download_url = request.url_root + 'download?file=' + os.path.basename(zip_path)

            # Show success page with auto download
            success_page = SUCCESS_HTML.format(
                dashboard=DASHBOARD_URL,
                zip_url=download_url
            )
            return success_page

        except Exception as e:
            return render_template_string(HTML, error="Processing failed!", token=token, user_id=user_id)

    return render_template_string(HTML, error=None, token=token, user_id=user_id)


# NEW ROUTE: Direct file download
@app.route('/download')
def download():
    filename = request.args.get('file')
    if not filename or '..' in filename or '/' in filename:
        return "Invalid file", 400
    file_path = os.path.join('/tmp', filename)
    if not os.path.exists(file_path):
        return "File not found", 404
    
    response = make_response(send_file(file_path, as_attachment=True, download_name="CLEAN_Fingerprints.zip"))
    
    # Delete file after sending
    @response.call_on_close
    def cleanup():
        try: os.unlink(file_path)
        except: pass
    
    return response


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
