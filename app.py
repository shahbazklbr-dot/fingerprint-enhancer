from flask import Flask, request, send_file, render_template_string
from fingerprint_enhancer import enhance_fingerprint
import cv2
import numpy as np
import os
from werkzeug.utils import secure_filename
import zipfile
from io import BytesIO

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>5 Fingerprint Enhancer</title>
    <style>
        body {font-family: Arial; text-align:center; margin:50px; background:#f4f4f4;}
        h1 {color:#333;}
        input, button {padding:15px; font-size:18px; margin:10px;}
        button {background:#007bff; color:white; border:none; border-radius:8px; cursor:pointer;}
    </style>
</head>
<body>
    <h1>Ek Saath 5 Fingerprint Upload Karo</h1>
    <p>Maximum 5 images select karo → sab clean black-on-white ban jayengi</p>
    <form method="post" enctype="multipart/form-data">
        <input type="file" name="files" accept="image/*" multiple required>
        <br><br>
        <button type="submit">5 Images Enhance Karo!</button>
    </form>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        files = request.files.getlist('files')
        if not files or len(files) == 0:
            return "<h3>Koi file nahi chuni!</h3><a href='/'>Wapas</a>"

        if len(files) > 5:
            return "<h3>Max 5 images hi allow hain!</h3><a href='/'>Wapas</a>"

        output_paths = []
        display_html = "<h2>Ho Gaya Bhai! 🔥</h2><div style='display:flex;flex-wrap:wrap;justify-content:center;'>"

        for file in files:
            if file.filename == '':
                continue
            filename = secure_filename(file.filename)
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(input_path)

            img = cv2.imread(input_path, 0)
            enhanced = enhance_fingerprint(img)
            final = (enhanced.astype(np.uint8) * 255)
            final = 255 - final  # white background + black ridges

            clean_name = "CLEAN_" + filename
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], clean_name)
            cv2.imwrite(output_path, final)
            output_paths.append(output_path)

            display_html += f'''
            <div style="margin:20px;">
                <p><b>{filename}</b></p>
                <img src="/download/{clean_name}" width="300"><br>
                <a href="/download/{clean_name}" download><button>Download</button></a>
            </div>
            '''

        display_html += "</div><hr>"

        # Zip banao taaki ek click mein sab download ho jaye
        memory_file = BytesIO()
        with zipfile.ZipFile(memory_file, 'w') as zf:
            for path in output_paths:
                zf.write(path, os.path.basename(path))
        memory_file.seek(0)

        # Zip download button
        display_html += '''
        <br><br>
        <h3>Ya phir sab ek saath download karo (ZIP)</h3>
        <form action="/download_zip" method="post">
            <input type="hidden" name="files" value="%s">
            <button style="padding:20px 50px; font-size:22px; background:#28a745;">
                Download All 5 Clean Fingerprints (ZIP)
            </button>
        </form>
        <hr><a href="/">Ek aur batch karo</a>
        ''' % ';'.join([os.path.basename(p) for p in output_paths])

        return display_html

    return HTML

# Individual download
@app.route('/download/<filename>')
def download(filename):
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return send_file(path, as_attachment=True)

# ZIP download
@app.route('/download_zip', methods=['POST'])
def download_zip():
    filenames = request.form['files'].split(';')
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for name in filenames:
            if name:
                path = os.path.join(app.config['UPLOAD_FOLDER'], name)
                if os.path.exists(path):
                    zf.write(path, name)
    memory_file.seek(0)
    return send_file(memory_file, as_attachment=True, download_name='CLEAN_FINGERPRINTS_5.zip')

if __name__ == '__main__':
    app.run()
