from flask import Flask, request, send_file
from fingerprint_enhancer import enhance_fingerprint
import cv2
import numpy as np
import os
from werkzeug.utils import secure_filename
import zipfile
import time

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp'
os.makedirs('/tmp', exist_ok=True)

HTML = '''
<!DOCTYPE html>
<html>
<head><title>Fingerprint Cleaner</title>
<style>
body{font-family:Arial;text-align:center;margin:50px;background:#f0f0f0;}
h1{color:#333;}
input,button{padding:15px 30px;font-size:18px;margin:10px;border-radius:8px;}
button{background:#0066ff;color:white;border:none;cursor:pointer;}
img{max-width:90%;margin:20px;border:2px solid #333;border-radius:10px;}
</style>
</head>
<body>
<h1>Fingerprint Enhancer (Free & Fast)</h1>
<p>Ek baar me 5 fingerprints upload karo → sab clean mil jayenge!</p>
<form method=post enctype=multipart/form-data>
<input type=file name=files accept="image/*" multiple required>
<br><br>
<button type=submit>Enhance Karo!</button>
</form>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':

        files = request.files.getlist("files")

        if not files or len(files) == 0:
            return "<h3>Koi file nahi chuni!</h3><a href='/'>Wapas</a>"

        if len(files) > 5:
            return "<h3>Maximum 5 fingerprints upload kar sakte ho.</h3><a href='/'>Wapas</a>"

        output_files = []

        for file in files:
            filename = secure_filename(file.filename)
            input_path = os.path.join('/tmp', filename)
            file.save(input_path)

            img = cv2.imread(input_path, 0)
            if img is None:
                continue

            # FREE PLAN SAFE RESIZE (super important)
            max_dim = 800
            h, w = img.shape

            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)))

            # Enhance
            enhanced = enhance_fingerprint(img)
            final = (enhanced.astype(np.uint8) * 255)
            final = 255 - final  # white bg + black ridges

            # Save
            output_path = '/tmp/CLEAN_' + filename
            cv2.imwrite(output_path, final)
            output_files.append(output_path)

            # MEMORY CLEANUP (free plan essential)
            del img
            del enhanced
            del final
            cv2.destroyAllWindows()

        # ZIP all files
        zip_name = f"/tmp/cleaned_{int(time.time())}.zip"
        with zipfile.ZipFile(zip_name, 'w') as zipf:
            for fpath in output_files:
                zipf.write(fpath, os.path.basename(fpath))

        return f'''
        <h2>Saare Fingerprints Clean Ho Gaye! 🔥</h2>
        <a href="/download/{os.path.basename(zip_name)}" download>
            <button style="padding:20px 50px;font-size:22px;">Download ALL (ZIP)</button>
        </a>
        <hr><a href="/">Wapas</a>
        '''

    return HTML


@app.route("/download/<zipfile_name>")
def download(zipfile_name):
    path = os.path.join('/tmp', zipfile_name)
    return send_file(path, as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
