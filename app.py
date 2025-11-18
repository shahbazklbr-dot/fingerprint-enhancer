from flask import Flask, request, send_file, render_template_string
from fingerprint_enhancer import enhance_fingerprint
import cv2
import numpy as np
import os
from werkzeug.utils import secure_filename
import zipfile

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp'
os.makedirs('/tmp', exist_ok=True)

HTML = '''
<!DOCTYPE html>
<html>
<head><title>5 Fingerprint Enhancer</title>
<style>
body{font-family:Arial;text-align:center;margin:50px;background:#f0f0f0;}
h1{color:#333;}
input,button{padding:15px;font-size:18px;margin:10px;border-radius:8px;}
button{background:#007bff;color:white;border:none;cursor:pointer;}
.progress {font-size:20px;color:green;margin:30px;}
</style>
</head>
<body>
<h1>Ek Saath 5 Fingerprint Upload Karo</h1>
<p>5 tak images select karo → 20-30 second mein sab ready</p>
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
        files = request.files.getlist('files')
        if len(files) == 0 or len(files) > 5:
            return "<h3>1 se 5 images select karo!</h3><a href='/'>Wapas</a>"

        result_html = "<h2>Processing chal raha hai... ruk jao 30 second</h2><div class='progress'>"
        "

        output_files = []

        for i, file in enumerate(files):
            if not file or file.filename == '':
                continue

            filename = secure_filename(file.filename)
            input_path = os.path.join('/tmp', filename)
            file.save(input_path)

            # Enhance
            img = cv2.imread(input_path, 0)
            enhanced = enhance_fingerprint(img)
            final = (enhanced.astype(np.uint8) * 255)
            final = 255 - final  # white background + black ridges

            clean_name = f"CLEAN_{i+1}_{filename}"
            output_path = os.path.join('/tmp', clean_name)
            cv2.imwrite(output_path, final)
            output_files.append((clean_name, output_path))

            result_html += f"<p>{filename} ✓ Done!</p>"

        # Sab images dikhao
        result_html += "<hr><h2>Ho Gaya Bhai! 🔥</h2><div style='display:flex;flex-wrap:wrap;justify-content:center;'>"
        for clean_name, _ in output_files:
            result_html += f'''
            <div style="margin:20px;">
                <img src="/files/{clean_name}" width="350"><br>
                <a href="/files/{clean_name}" download><button>Download {clean_name}</button></a>
            </div>'''

        # ZIP banao
        zip_path = '/tmp/ALL_CLEAN_FINGERPRINTS.zip'
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for _, path in output_files:
                z.write(path, os.path.basename(path))

        result_html += f'''
        <br><br><a href="/files/ALL_CLEAN_FINGERPRINTS.zip">
        <button style="padding:20px 60px;font-size:24px;background:green;">
            Download Sab 5 Ek Saath (ZIP)
        </button></a>
        <hr><a href="/">Ek aur batch karo</a>
        '''

        return result_html

    return HTML

@app.route('/files/<filename>')
def serve_file(filename):
    return send_file(os.path.join('/tmp', filename), as_attachment=('zip' in filename))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
