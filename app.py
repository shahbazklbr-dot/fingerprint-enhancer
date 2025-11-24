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
<html>
<head>
<meta charset='UTF-8'>
<title>Fingerprint Enhancer</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{
  --bg1:#667eea; --bg2:#764ba2; --card:#ffffffcc;
  --btn:#00d084; --btn-hover:#00b070;
}
*{box-sizing:border-box}
body{
  margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
  font-family:Inter, "Segoe UI", Roboto, Arial, sans-serif;
  background: linear-gradient(135deg,var(--bg1),var(--bg2));
  padding:32px;
}
.container{
  width:100%; max-width:560px; background:var(--card); border-radius:18px;
  padding:34px; box-shadow:0 20px 40px rgba(10,10,30,0.25); backdrop-filter: blur(6px);
}
.header{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}
.h-title{font-size:22px;font-weight:700;color:#0f1724}
.h-sub{font-size:13px;color:#374151}
.input-row{margin-top:10px}
input[type=file]{
  display:block; width:100%; padding:14px 12px; border-radius:12px; border:2px dashed rgba(99,102,241,0.18);
  background: #fff; font-size:14px; outline:none; cursor:pointer;
}
.note{font-size:13px;color:#374151;margin-top:8px}
.actions{margin-top:20px;display:flex;gap:12px;align-items:center}
.btn{
  flex:1; padding:14px 18px; border-radius:12px; font-size:17px; font-weight:600;
  border:none; cursor:pointer; color:white; background:var(--btn); transition:all .18s ease;
}
.btn:hover{background:var(--btn-hover); transform:translateY(-3px)}
.error{
  margin-top:12px;padding:12px;border-radius:10px;background:#fff0f0;color:#a60000;font-weight:600;
}
.small{font-size:13px;color:#6b7280;margin-top:8px}
.footer{margin-top:18px;font-size:13px;color:#6b7280;text-align:center}
@media (max-width:540px){
  .container{padding:20px}
  .h-title{font-size:20px}
}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <div class="h-title">Fingerprint Enhancer</div>
      <div class="h-sub">Upload up to 5 fingerprint images — cleaned and ready to download</div>
    </div>
  </div>

  {% if error %}
    <div class="error">{{ error }}</div>
  {% endif %}

  <form method="POST" enctype="multipart/form-data" id="uploadForm">
    <input type="hidden" name="token" value="{{ token }}">
    <input type="hidden" name="user_id" value="{{ user_id }}">
    <div class="input-row">
      <input type="file" name="files" accept="image/*" multiple required>
    </div>

    <div class="actions">
      <button type="submit" class="btn">Enhance</button>
    </div>
  </form>

  <div class="footer">Powered by SecureEnhance — Keep your biometrics private</div>
</div>

<script>
document.getElementById('uploadForm')?.addEventListener('submit', function(){ 
  // simple visual feedback (no spinner to avoid extra assets)
  const btn = document.querySelector('.btn');
  if(btn){ btn.disabled = true; btn.innerText = 'Processing...'; }
});
</script>
</body>
</html>
"""

SUCCESS_PAGE = """<!DOCTYPE html>
<html>
<head>
<meta charset='UTF-8'>
<title>Download Ready</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="5;url={dashboard}">
<style>
:root{--g1:#00c6ff; --g2:#0072ff; --cardc:rgba(255,255,255,0.12)}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;font-family:Inter,Arial;background:linear-gradient(135deg,var(--g1),var(--g2));color:white;padding:28px}
.card{width:100%;max-width:520px;background:var(--cardc);padding:36px;border-radius:18px;text-align:center;box-shadow:0 18px 36px rgba(3,10,40,0.3);backdrop-filter:blur(8px)}
.tick{width:84px;height:84px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;background:rgba(255,255,255,0.06);margin-bottom:18px}
.tick svg{width:44px;height:44px;fill:#fff}
h1{margin:0;font-size:26px}
p{margin:10px 0 0;font-size:16px;color:rgba(255,255,255,0.92)}
.download-btn{display:inline-block;margin-top:20px;padding:12px 26px;border-radius:12px;background:#10b981;color:white;text-decoration:none;font-weight:700;box-shadow:0 8px 20px rgba(16,185,129,0.18)}
.small{margin-top:10px;color:rgba(255,255,255,0.85);font-size:13px}
@media (max-width:520px){.card{padding:22px}}
</style>
</head>
<body>
<div class="card">
  <div class="tick">
    <svg viewBox="0 0 24 24"><path d="M9 16.17l-3.88-3.88a1 1 0 0 0-1.41 1.41l4.59 4.59a1 1 0 0 0 1.41 0l10-10a1 1 0 1 0-1.41-1.41L9 16.17z"/></svg>
  </div>
  <h1>Enhancement Complete</h1>
  <p>Your cleaned fingerprints are ready.</p>
  <div class="small">You will be redirected to your dashboard in a few seconds.</div>
</div>

<script>
// Trigger automatic download
(function(){
  try{
    var a = document.createElement('a');
    a.href = '{zip_url}';
    a.download = 'CLEAN_Fingerprints.zip';
    document.body.appendChild(a);
    a.click();
    a.remove();
  }catch(e){ console.warn('autodownload failed', e); }
})();
</script>
</body>
</html>
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
