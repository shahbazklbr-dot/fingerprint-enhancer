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
app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ==================== PERFECT FUNCTION (Exact match to your image) ====================
def make_perfect_fingerprint(img):
    # Step 1: Enhance with Gabor (best possible ridge clarity)
    enhanced = enhance_fingerprint(img)
    enhanced = np.clip(enhanced, 0, 1)
    enhanced8 = (enhanced * 255).astype(np.uint8)

    # Step 2: Ultra-smooth adaptive threshold (exact thickness jaise tumhari photo)
    thresh = cv2.adaptiveThreshold(
        enhanced8, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 51, 8
    )

    # Step 3: Remove tiny dots & fill small gaps (perfect continuity)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2,2))
    opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)
    closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel, iterations=3)

    # Step 4: Final image - White background, EXACT grey shade like your photo
    result = np.full_like(closed, 255)                    # Pure white background
    result[closed == 255] = 80                            # Exact grey shade (80 = perfect match)

    # Step 5: Add clean white border (exactly like your image)
    result = cv2.copyMakeBorder(result, 35, 35, 35, 35, cv2.BORDER_CONSTANT, value=255)

    return result

# ==================== ROUTES ====================
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        files = request.files.getlist('files')
        if not files or len(files) > 5:
            return "<h3>1-5 images only!</h3><a href='/'>Back</a>"

        temp_files = []
        outputs = []

        try:
            for file in files:
                if not file or not file.filename:
                    continue

                name = secure_filename(file.filename)
                in_path = os.path.join(app.config['UPLOAD_FOLDER'], name)
                file.save(in_path)
                temp_files.append(in_path)

                img = cv2.imread(in_path, 0)
                if img is None:
                    continue

                # Resize only if huge
                if max(img.shape) > 1300:
                    scale = 1300 / max(img.shape)
                    img = cv2.resize(img, (int(img.shape[1]*scale), int(img.shape[0]*scale)))

                # MAGIC - Exact same as your uploaded image
                perfect = make_perfect_fingerprint(img)

                out_name = f"PERFECT_{os.path.splitext(name)[0]}.png"
                out_path = os.path.join(app.config['UPLOAD_FOLDER'], out_name)
                cv2.imwrite(out_path, perfect, [cv2.IMWRITE_PNG_COMPRESSION, 0])
                outputs.append(out_path)
                temp_files.append(out_path)

            if not outputs:
                return "No valid image!<a href='/'>Back</a>"

            # ZIP
            zip_path = f"/tmp/fingerprints_{int(time.time())}.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
                for p in outputs:
                    z.write(p, os.path.basename(p))
            temp_files.append(zip_path)

            return f'''
            <h2 style="font-family:sans-serif;text-align:center;margin-top:100px;">
                Done! Your fingerprints are PERFECT now
            </h2>
            <center>
                <a href="/download/{os.path.basename(zip_path)}" 
                   style="display:inline-block;padding:20px 50px;background:#11998e;color:white;font-size:22px;text-decoration:none;border-radius:15px;">
                   Download All (ZIP)
                </a>
                <br><br>
                <a href="/">Clean More</a>
            </center>
            '''

        finally:
            def cleanup():
                time.sleep(180)
                for f in temp_files:
                    try: os.remove(f)
                    except: pass
            threading.Thread(target=cleanup, daemon=True).start()

    # Simple beautiful homepage
    return '''
    <!DOCTYPE html>
    <html><head><meta charset="utf-8"><title>Perfect Fingerprint Cleaner</title>
    <style>
        body{margin:0;background:linear-gradient(135deg,#667eea,#764ba2);font-family:Segoe UI;display:flex;justify-content:center;align-items:center;height:100vh;}
        .box{background:white;padding:50px;border-radius:25px;box-shadow:0 20px 40px rgba(0,0,0,0.3);text-align:center;max-width:500px;width:90%;}
        h1{font-size:34px;color:#222;}
        input,button{margin:15px 0;padding:18px;width:100%;border-radius:12px;font-size:18px;}
        input{border:3px dashed #667eea;background:#f8f9ff;}
        button{background:#667eea;color:white;border:none;cursor:pointer;}
        button:hover{background:#5542c7;}
    </style></head>
    <body>
    <div class="box">
        <h1>Perfect Fingerprint Cleaner</h1>
        <p>Upload up to 5 prints → Get exactly like the pro image</p>
        <form method="post" enctype="multipart/form-data">
            <input type="file" name="files" multiple accept="image/*" required>
            <button type="submit">Make Perfect</button>
        </form>
    </div>
    </body></html>
    '''

@app.route('/download/<filename>')
def download(filename):
    path = f"/tmp/{filename}"
    if os.path.exists(path):
        return send_file(path, as_attachment=True, download_name="Perfect_Cleaned_Fingerprints.zip")
    abort(404)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
