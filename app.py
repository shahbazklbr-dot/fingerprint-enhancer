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
    <title>5 Fingerprint Cleaner</title>
    <style>
        body {font-family: Arial; text-align:center; margin:50px; background:#f4f4f4;}
        h1 {color:#333;}
        input, button {padding:15px; font-size:18px; margin:10px; border-radius:8px;}
        button {background:#007bff; color:white; border:none; cursor:pointer;}
    </style>
</head>
<body>
    <h1>Ek Saath 5 Fingerprint Upload Karo</h1>
    <p>5 tak images select karo → sab clean black-on-white ban jayengi</p>
    <form method="post" enctype="multipart/form-data">
        <input type="file" name="files" accept="image/*" multiple required>
        <br><br>
        <button type="submit">Enhance Karo!</button>
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

        output_paths = []
        result_html = "<h2>Processing... 20-30 sec lagega</h2><div style='display:flex;flex-wrap:wrap;justify-content:center;'>"

        for i, file in enumerate(files):
            if not file or file.filename == '':
                continue
            filename = secure_filename(file.filename)
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(input_path)

            img = cv2.imread(input_path, 0)
            enhanced = enhance_fingerprint(img)
            final = (enhanced.astype(np.uint8) * 255)
            final = 255 - final  # white background + black ridges

            clean_name = f"CLEAN_{i+1}_{filename}"
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], clean_name)
            cv2.imwrite(output_path, final)
            output_paths.append((output_path, clean_name))

            result_html += f'''
            <div style="margin:20px;">
                <p><b>{filename}</b></p>
                <img src="/download/{clean_name}" width="350"><br>
                <a href="/download/{clean_name}" download><button>Download</button></a>
            </div>
            '''

        result_html += "</div><br><br>"

        # ZIP banao
        zip_path = os.path.join(app.config['UPLOAD_FOLDER'], "ALL_5_CLEAN_FINGERPRINTS.zip")
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for path, name in output_paths:
                zf.write(path, name)

        result_html += f'''
        <a href="/download/ALL_5_CLEAN_FINGERPRINTS.zip">
            <button style="padding:20px 50px; font-size:24px; background:green;">
                Download Sab 5 Ek Saath (ZIP)
            </button>
        </a>
        <hr><a href="/">Ek aur batch</a>
        '''

        return result_html

    return HTML

@app.route('/download/<filename>')
def download(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    app.run()
