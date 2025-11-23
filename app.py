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

# ==================== FINAL PERFECT GREY RIDGES (EXACTLY LIKE GOVT FORMS) ====================
def make_perfect_grey_fingerprint(img):
    # Enhance
    enhanced = enhance_fingerprint(img)
    enhanced = np.clip(enhanced, 0, 1)
    enhanced8 = (enhanced * 255).astype(np.uint8)

    # Strong but smooth threshold
    thresh = cv2.adaptiveThreshold(
        enhanced8, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 61, 12
    )

    # Clean noise + perfect ridge continuity
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
    opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)
    closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel, iterations=3)

    # Slightly thicken ridges (professional look)
    kernel_thick = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
    ridges = cv2.dilate(closed, kernel_thick, iterations=1)

    # Final output: White background + Perfect GREY ridges (value 70 = standard form shade)
    result = np.full_like(ridges, 255)      # Pure white background
    result[ridges == 255] = 70              # Perfect dark grey (exact match to forms)

    # Add clean white border
    result = cv2.copyMakeBorder(result, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)

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
                if not file or not file.filename: continue

                name = secure_filename(file.filename)
                in_path = os.path.join(app.config['UPLOAD_FOLDER'], name)
                file.save(in_path)
                temp_files.append(in_path)

                img = cv2.imread(in_path, 0)
                if img is None: continue

                if max(img.shape) > 1400:
                    scale = 1400 / max(img.shape)
                    img = cv2.resize(img, (int(img.shape[1]*scale), int(img.shape[0]*scale)))

                # Yeh line 100% tumhara desired output dega
                final_grey = make_perfect_grey_fingerprint(img)

                out_name = f"FINAL_GREY_{os.path.splitext(name)[0]}.png"
                out_path = os.path.join(app.config['UPLOAD_FOLDER'], out_name)
                cv2.imwrite(out_path, final_grey)
                outputs.append(out_path)
                temp_files.append(out_path)

            # ZIP
            zip_path = f"/tmp/final_grey_fingerprints_{int(time.time())}.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
                for p in outputs:
                    z.write(p, os.path.basename(p))
            temp_files.append(zip_path)

            return f'''
            <center style="margin-top:100px;font-family:system-ui;">
                <h1 style="color:#2e8b57;font-size:40px;">Perfect Grey Ridges Done!</h1>
                <a href="/download/{os.path.basename(zip_path)}" 
                   style="display:inline-block;padding:22px 70px;background:#2e8b57;color:white;font-size:24px;text-decoration:none;border-radius:15px;">
                   Download All (Grey Ridges)
                </a>
                <br><br><a href="/" style="color:#333;">Clean More</a>
            </center>
            '''

        finally:
            def cleanup():
                time.sleep(180)
                for f in temp_files:
                    if os.path.exists(f):
                        try: os.remove(f)
                        except: pass
            threading.Thread(target=cleanup, daemon=True).start()

    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Perfect Grey Fingerprint Cleaner</title>
        <style>
            body{background:linear-gradient(135deg,#11998e,#38ef7d);margin:0;display:flex;justify-content:center;align-items:center;height:100vh;font-family:system-ui;}
            .box{background:white;padding:55px;border-radius:25px;box-shadow:0 25px 50px rgba(0,0,0,0.3);text-align:center;width:90%;max-width:520px;}
            h1{color:#222;font-size:36px;margin-bottom:10px;}
            p{font-size:18px;color:#555;}
            input,button{margin:18px 0;padding:20px;width:100%;border-radius:14px;font-size:19px;border:none;}
            input{background:#f0f8ff;border:3px dashed #11998e;}
            button{background:#11998e;color:white;cursor:pointer;font-weight:bold;}
            button:hover{background:#0d7a63;}
        </style>
    </head>
    <body>
    <div class="box">
        <h1>Grey Ridge Cleaner</h1>
        <p>Upload any fingerprint → Get perfect grey ridges on white background<br>(exactly like government/police forms)</p>
        <form method="post" enctype="multipart/form-data">
            <input type="file" name="files" multiple accept="image/*" required>
            <button type="submit">Make Perfect Grey</button>
        </form>
    </div>
    </body>
    </html>
    '''

@app.route('/download/<filename>')
def download(filename):
    path = f"/tmp/{filename}"
    if os.path.exists(path):
        return send_file(path, as_attachment=True, download_name="Perfect_Grey_Fingerprints.zip")
    abort(404)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
