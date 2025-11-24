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
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer

# -------------------------
# CONFIG
# -------------------------
PHP_DOMAIN = "https://enhance.strangled.net" # ← change if needed
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', base64.b64encode(os.urandom(24)).decode())  # Secure random key
app.config['UPLOAD_FOLDER'] = '/tmp'
app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
DEDUCT_API = f"{PHP_DOMAIN}/deduct.php"
DASHBOARD_URL = f"{PHP_DOMAIN}/dashboard.php?success=1"

# Serializer for secure download tokens (expires in 180 seconds)
serializer = Serializer(app.secret_key, expires_in=180)

# -------------------------
# PREMIUM UPLOAD PAGE (UI)
# -------------------------
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
  <div class="footer">Poweredd by SecureEnhance — Keep your biometrics private</div>
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

# -------------------------
# PREMIUM SUCCESS PAGE (UI) - placeholders {dashboard} and {zip_url}
# -------------------------
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

# -------------------------
# UTILS
# -------------------------
def safe_read(path):
    """
    Robust reader: use Pillow to handle many formats and conversions,
    then convert to grayscale numpy array for enhancer.
    """
    try:
        img = Image.open(path)
        # Convert to RGB if needed (Pillow handles HEIC if supported)
        if img.mode not in ("L", "RGB"):
            img = img.convert("RGB")
        arr = np.array(img)
        if arr.ndim == 3:
            arr = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        return arr
    except Exception as e:
        # Fallback to OpenCV grayscale read
        print("safe_read error (PIL):", e)
        try:
            return cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        except Exception as e2:
            print("safe_read fallback error:", e2)
            return None

def make_zip_from_paths(paths, zip_path):
    with zipfile.ZipFile(zip_path, "w") as zf:
        for p in paths:
            if os.path.exists(p):
                zf.write(p, os.path.basename(p))

def start_cleanup_later(zip_path, delay=180):
    def _cleanup():
        time.sleep(delay)
        try:
            if os.path.exists(zip_path):
                os.unlink(zip_path)
        except Exception as e:
            print("cleanup error:", e)
    t = threading.Thread(target=_cleanup, daemon=True)
    t.start()

def generate_download_token(zip_name, user_id):
    return serializer.dumps({'zip_name': zip_name, 'user_id': user_id}).decode()

def validate_token(token):
    try:
        data = serializer.loads(token)
        zip_name = data['zip_name']
        # user_id = data['user_id']  # Optional: validate user_id if needed
        path = os.path.join(app.config['UPLOAD_FOLDER'], zip_name)
        if os.path.exists(path):
            return path
        return None
    except Exception as e:
        print("Token validation error:", e)
        return None

# -------------------------
# ROUTES
# -------------------------
@app.route('/', methods=['GET', 'POST'])
def index():
    token = request.args.get('token')
    user_id = request.args.get('user_id')
    if not token or not user_id:
        return "<h2>Invalid Access</h2>", 403
    if request.method == "POST":
        files = request.files.getlist("files")
        if not files or len(files) == 0:
            return render_template_string(HTML, error="No files selected!", token=token, user_id=user_id)
        if len(files) > 5:
            return render_template_string(HTML, error="Upload maximum 5 files!", token=token, user_id=user_id)
        processed_paths = []
        temp_paths = []
        for file in files:
            if not file or not getattr(file, "filename", None):
                continue
            filename = secure_filename(file.filename)
            timestamp = int(time.time() * 1000)
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{timestamp}_{filename}")
            try:
                file.save(input_path)
            except Exception as e:
                print("file.save error:", e)
                continue
            temp_paths.append(input_path)
            img = safe_read(input_path)
            if img is None:
                print("Could not read image:", input_path)
                continue
            # Resize maximum dimension to 800 px (keeps aspect)
            try:
                h, w = img.shape
            except Exception:
                print("invalid img shape:", type(img), getattr(img, "shape", None))
                continue
            max_dim = 800
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)))
            # Run enhancer in try/except (so whole app doesn't crash)
            try:
                enhanced = enhance_fingerprint(img)
            except Exception as e:
                print("enhancer error:", e)
                # cleanup immediate temp files we created for this request
                for p in temp_paths + processed_paths:
                    try:
                        if os.path.exists(p): os.unlink(p)
                    except: pass
                return render_template_string(HTML, error="Enhancement failed on one of the images. Try a clearer image.", token=token, user_id=user_id)
            if enhanced is None or getattr(enhanced, "size", 1) == 0:
                print("enhancer returned invalid output for", input_path)
                continue
            try:
                final = (np.clip(enhanced, 0, 1) * 255).astype(np.uint8)
                final = 255 - final
            except Exception as e:
                print("postprocess error:", e)
                continue
            output_name = f"CLEAN_{filename}"
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_name)
            try:
                cv2.imwrite(output_path, final)
            except Exception as e:
                print("cv2.imwrite error:", e)
                continue
            processed_paths.append(output_path)
        # Nothing processed?
        if not processed_paths:
            # remove any temp files
            for p in temp_paths:
                try: os.unlink(p)
                except: pass
            return render_template_string(HTML, error="No valid fingerprints were processed.", token=token, user_id=user_id)
        # Create ZIP
        zip_name = f"clean_{user_id}_{int(time.time())}.zip"
        zip_path = os.path.join(app.config['UPLOAD_FOLDER'], zip_name)
        try:
            make_zip_from_paths(processed_paths, zip_path)
        except Exception as e:
            print("zip creation error:", e)
            return render_template_string(HTML, error="Failed to create ZIP.", token=token, user_id=user_id)
        # Attempt payment (deduct ₹10)
        try:
            r = requests.post(DEDUCT_API, data={'token': token, 'user_id': user_id}, timeout=10)
            ok = False
            try:
                ok = bool(r.json().get("success"))
            except Exception:
                ok = False
            if not ok:
                # cleanup created files
                try:
                    if os.path.exists(zip_path): os.unlink(zip_path)
                    for p in processed_paths + temp_paths:
                        if os.path.exists(p): os.unlink(p)
                except: pass
                return render_template_string(HTML, error="Low balance or payment failed!", token=token, user_id=user_id)
        except Exception as e:
            print("payment request error:", e)
            # cleanup
            try:
                if os.path.exists(zip_path): os.unlink(zip_path)
                for p in processed_paths + temp_paths:
                    if os.path.exists(p): os.unlink(p)
            except: pass
            return render_template_string(HTML, error="Payment service unreachable!", token=token, user_id=user_id)
        # Schedule cleanup
        start_cleanup_later(zip_path, delay=180)
        # Generate secure token for download
        download_token = generate_download_token(zip_name, user_id)
        download_url = request.url_root.rstrip('/') + "/dl/" + download_token
        # Use safe replace to avoid .format() curly-brace issues
        page = SUCCESS_PAGE.replace("{dashboard}", DASHBOARD_URL).replace("{zip_url}", download_url)
        return page
    # GET
    return render_template_string(HTML, token=token, user_id=user_id, error=None)

@app.route("/dl/<token>")
def download(token):
    path = validate_token(token)
    if not path:
        return "Expired or invalid!", 404
    return send_file(path, as_attachment=True, download_name="CLEAN_Fingerprints.zip")

# -------------------------
# START APP
# -------------------------
if __name__ == "__main__":
    # for local testing use debug=True (don't use in production)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=False)
