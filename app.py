from flask import Flask, request, send_file, render_template_string
from fingerprint_enhancer import enhance_fingerprint
import cv2
import numpy as np
import os
import zipfile
import time
import shutil
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp'
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB max

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ───────────────────────────────
# TERA Cpanel DOMAIN YAHAN DAAL DE
# ───────────────────────────────
REDIRECT_DASHBOARD_URL = "https://jharkhand.govt.hu/dashboard.php?deduct=success"  # ←← YAHAN APNA DOMAIN DAAL!
# Example: "https://fp.rahulpro.in/dashboard.php?deduct=success"

# HTML Pages
HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fingerprint Enhancer</title>
    <style>
        body{margin:0;padding:0;font-family:'Segoe UI',sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);display:flex;justify-content:center;align-items:center;min-height:100vh;color:#333}
        .container{width:90%;max-width:520px;padding:40px;background:white;border-radius:20px;text-align:center;box-shadow:0 15px 35px rgba(0,0,0,0.2);}
        h1{font-size:32px;margin-bottom:10px;color:#222}
        p{font-size:17px;opacity:0.85;margin-bottom:30px}
        input[type=file]{background:#f8f9fa;padding:16px;border-radius:12px;width:100%;border:2px dashed #667eea;margin-bottom:20px}
        button{padding:16px 40px;font-size:20px;border:none;border-radius:12px;background:#667eea;color:white;cursor:pointer;width:100%;transition:0.3s}
        button:hover{background:#5a6fd8;transform:scale(1.05)}
        .back-btn{margin-top:20px;display:inline-block;color:#667eea;text-decoration:none;font-weight:600}
    </style>
</head>
<body>
<div class="container">
    <h1>Fingerprint Enhancer</h1>
    <p>Upload up to 5 fingerprints → Get cleaned instantly!</p>
    <form method="post" enctype="multipart/form-data">
        <input type="file" name="files" accept="image/*" multiple required>
        <button type="submit">Enhance Now!</button>
    </form>
    <a href="https://jharkhand.govt.hu/dashboard.php" class="back-btn">Back to Dashboard</a>
</div>
</body>
</html>
'''

# Success + Auto Redirect Page
SUCCESS_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Enhance Complete!</title>
    <meta http-equiv="refresh" content="3;url={{REDIRECT_URL}}">
    <style>
        body{font-family:'Segoe UI',sans-serif;background:#f8f9fa;display:flex;flex-direction:column;justify-content:center;align-items:center;height:100vh;margin:0;color:#333}
        .box{background:white;padding:40px 60px;border-radius:20px;box-shadow:0 10px 30px rgba(0,0,0,0.1);text-align:center;max-width:500px}
        h2{color:#28a745;font-size:28px;margin:0 0 15px 0}
        p{font-size:18px;margin:15px 0}
        .countdown{color:#667eea;font-weight:bold}
        .manual{margin-top:25px}
        .manual a{color:#667eea;font-weight:600;text-decoration:none}
    </style>
</head>
<body>
<div class="box">
    <h2>Enhancement Complete!</h2>
    <p>₹10 has been deducted from your wallet.</p>
    <p>Redirecting back to dashboard in <span class="countdown">3</span> seconds...</p>
    <div class="manual">
        <a href="{{REDIRECT_URL}}">Click here if not redirected</a>
    </div>
</div>

<script>
    let seconds = 3;
    setInterval(() => {
        seconds--;
        document.querySelector('.countdown').textContent = seconds;
        if(seconds <= 0) location.href = "{{REDIRECT_URL}}";
    }, 1000);
</script>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        files = request.files.getlist("files")
        if not files or len(files) == 0:
            return "No file selected!", 400
        if len(files) > 5:
            return "Max 5 images allowed!", 400

        output_paths = []
        temp_files = []

        try:
            for file in files:
                if not file.filename:
                    continue
                filename = secure_filename(file.filename)
                input_path = os.path.join(app.config['UPLOAD_FOLDER'], f"in_{int(time.time()*1000)}_{filename}")
                file.save(input_path)
                temp_files.append(input_path)

                img = cv2.imread(input_path, cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue

                # Resize if too big
                if max(img.shape) > 1000:
                    scale = 1000 / max(img.shape)
                    img = cv2.resize(img, (int(img.shape[1]*scale), int(img.shape[0]*scale)))

                enhanced = enhance_fingerprint(img)
                final = (np.clip(enhanced, 0, 1) * 255).astype(np.uint8)
                final = 255 - final  # Black ridges

                out_name = "CLEAN_" + filename
                out_path = os.path.join(app.config['UPLOAD_FOLDER'], out_name)
                cv2.imwrite(out_path, final)
                output_paths.append((out_name, out_path))

            if not output_paths:
                return "No valid images processed!", 400

            # Create ZIP
            zip_filename = f"enhanced_fingerprints_{int(time.time())}.zip"
            zip_path = os.path.join(app.config['UPLOAD_FOLDER'], zip_filename)

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for name, path in output_paths:
                    zf.write(path, name)

            # Send ZIP
            response = send_file(zip_path, as_attachment=True, download_name="Enhanced_Fingerprints.zip")

            # Auto cleanup after send
            @response.call_on_close
            def cleanup():
                try:
                    for _, p in output_paths:
                        if os.path.exists(p): os.unlink(p)
                    for p in temp_files:
                        if os.path.exists(p): os.unlink(p)
                    if os.path.exists(zip_path): os.unlink(zip_path)
                except:
                    pass

            # Now show success page with redirect
            return render_template_string(
                SUCCESS_PAGE.replace("{{REDIRECT_URL}}", REDIRECT_DASHBOARD_URL)
            )

        except Exception as e:
            return f"Error: {str(e)}", 500

    return HTML.replace("jharkhand.govt.hu", REDIRECT_DASHBOARD_URL.split("/")[2])

@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
