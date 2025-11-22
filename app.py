from flask import Flask, request, send_file, abort
from fingerprint_enhancer import enhance_fingerprint
import cv2
import numpy as np
import os
import zipfile
import time
import threading
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp/fp_uploads'
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25 MB max

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --------------------- HTML (Beautiful UI) ---------------------
HTML = '''
<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fingerprint Cleaner Pro</title>
<style>
    body{margin:0;padding:0;font-family:'Segoe UI',sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);display:flex;justify-content:center;align-items:center;min-height:100vh;color:#333;}
    .box{max-width:520px;width:90%;padding:40px;background:white;border-radius:20px;box-shadow:0 15px 35px rgba(0,0,0,0.2);text-align:center;}
    h1{font-size:32px;margin-bottom:8px;color:#222;}
    p{font-size:17px;opacity:0.85;margin-bottom:25px;}
    input[type=file]{width:100%;padding:15px;border:2px dashed #667eea;border-radius:12px;background:#f8f9ff;}
    button{margin-top:25px;padding:16px;font-size:19px;width:100%;border:none;border-radius:12px;background:#667eea;color:white;cursor:pointer;transition:0.3s;}
    button:hover{background:#5542c7;transform:translateY(-3px);}
    #loader{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(255,255,255,0.95);justify-content:center;align-items:center;flex-direction:column;z-index:999;}
    .spin{border:8px solid #f0f0f0;border-top:8px solid #667eea;border-radius:50%;width:60px;height:60px;animation:s 1s linear infinite;margin-bottom:20px;}
    @keyframes s{to{transform:rotate(360deg);}}
</style></head><body>
<div class="box">
    <h1>Fingerprint Cleaner Pro</h1>
    <p>Upload up to 5 fingerprints → Get ultra-clean grey-ridge versions instantly!</p>
    <form id="f" method="post" enctype="multipart/form-data">
        <input type="file" name="files" multiple accept="image/*" required>
        <button type="submit">Clean & Enhance</button>
    </form>
</div>
<div id="loader"><div class="spin"></div><h3>Processing your fingerprints...</h3></div>
<script>
document.getElementById("f").onsubmit = () => {
    document.getElementById("loader").style.display = "flex";
};
</script>
</body></html>
'''

SUCCESS_HTML = '''
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Done!</title>
<style>
    body{background:linear-gradient(135deg,#11998e,#38ef7d);margin:0;display:flex;justify-content:center;align-items:center;min-height:100vh;font-family:'Segoe UI',sans-serif;}
    .box{background:white;padding:50px;border-radius:20px;box-shadow:0 20px 40px rgba(0,0,0,0.2);text-align:center;max-width:500px;width:90%;}
    h2{font-size:30px;color:#222;margin-bottom:15px;}
    .btn{display:inline-block;margin:20px 0;padding:18px 40px;background:#11998e;color:white;font-size:20px;border-radius:12px;text-decoration:none;}
    .btn:hover{background:#0e7a6e;}
    a{color:#667eea;font-size:18px;}
</style></head><body>
<div class="box">
    <h2>All Done! Your fingerprints are perfectly cleaned</h2>
    <a href="{LINK}" download class="btn">Download All (ZIP)</a><br>
    <a href="/">← Clean More</a>
</div></body></html>
'''

# --------------------- MAGIC CLEANING FUNCTION ---------------------
def clean_fingerprint_perfectly(img):
    # Step 1: Enhance with the best Gabor filter method
    enhanced = enhance_fingerprint(img)  # Returns float 0-1
    
    # Step 2: Convert to 8-bit
    enhanced8 = (enhanced * 255).astype(np.uint8)
    
    # Step 3: Strong adaptive binarization
    thresh = cv2.adaptiveThreshold(
        enhanced8, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 35, 15
    )
    
    # Step 4: Clean small noise & connect ridges
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
    clean = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
    clean = cv2.morphologyEx(clean, cv2.MORPH_CLOSE, kernel, iterations=2)
    
    # Step 5: Convert ridges to GREY (value = 100) and background to WHITE (255)
    result = np.full_like(clean, 255)  # Start with white background
    result[clean == 255] = 100         # Where ridges were → dark grey
    
    # Step 6: Add nice white padding
    result = cv2.copyMakeBorder(result, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)
    
    return result

# --------------------- ROUTES ---------------------
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        files = request.files.getlist('files')
        if len(files) == 0 or len(files) > 5:
            return "<h3>Upload 1–5 images only!</h3><a href='/'>Back</a>"

        temp_files = []
        output_paths = []

        try:
            for file in files:
                if file.filename == '':
                    continue
                sec_name = secure_filename(file.filename)
                in_path = os.path.join(app.config['UPLOAD_FOLDER'], sec_name)
                file.save(in_path)
                temp_files.append(in_path)

                # Read image
                img = cv2.imread(in_path, cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue

                # Resize if too large (better speed & quality)
                if max(img.shape) > 1200:
                    scale = 1200 / max(img.shape)
                    img = cv2.resize(img, (int(img.shape[1]*scale), int(img.shape[0]*scale)))

                # MAGIC CLEANING
                cleaned = clean_fingerprint_perfectly(img)

                # Save as PNG (lossless)
                name = os.path.splitext(sec_name)[0]
                out_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{name}_CLEANED.png")
                cv2.imwrite(out_path, cleaned)
                output_paths.append(out_path)
                temp_files.append(out_path)

            # Create ZIP
            zip_path = f"/tmp/fingerprints_cleaned_{int(time.time())}.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
                for p in output_paths:
                    z.write(p, os.path.basename(p))
            temp_files.append(zip_path)

            # Success page
            link = f"/download/{os.path.basename(zip_path)}"
            return SUCCESS_HTML.replace("{LINK}", link)

        finally:
            # Auto delete everything after 2 minutes
            def delete_later():
                time.sleep(120)
                for f in temp_files:
                    try:
                        if os.path.exists(f):
                            os.remove(f)
                    except:
                        pass
            threading.Thread(target=delete_later, daemon=True).Zb start()

    return HTML

@app.route('/download/<filename>')
def download(filename):
    path = os.path.join('/tmp', filename)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True, download_name="Cleaned_Fingerprints_GreyRidges.zip")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
