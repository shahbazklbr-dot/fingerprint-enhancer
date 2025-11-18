from flask import Flask, request, send_file, render_template_string, jsonify
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

# ← YEH LINE ADD KARO (timeout badhane ke liye)
@app.before_request
def before_request():
    from flask import g
    import time
    g.start = time.time()

@app.after_request
def after_request(response):
    # Render ko batao ki zyada time lagega
    response.headers['X-Response-Time'] = '30s'
    return response

HTML = '''... same rahega ...'''  # pehle wala HTML

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        files = request.files.getlist('files')
        if len(files) > 5:
            return "<h3>Max 5 images!</h3><a href='/'>Wapas</a>"

        output_paths = []
        display_html = "<h2>Processing shuru... 20-30 second lagega</h2><p>Page refresh mat karna!</p>"

        for i, file in enumerate(files):
            if file.filename == '':
                continue
            filename = secure_filename(file.filename)
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(input_path)

            img = cv2.imread(input_path, 0)
            enhanced = enhance_fingerprint(img)
            final = (enhanced.astype(np.uint8) * 255)
            final = 255 - final

            clean_name = f"CLEAN_{i+1}_{filename}"
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], clean_name)
            cv2.imwrite(output_path, final)
            output_paths.append((output_path, clean_name))

            display_html += f'<p>{filename} → Done!</p>'

        # Sab images dikhao
        display_html += "<h2>Ho Gaya Bhai! 🔥</h2><div style='display:flex;flex-wrap:wrap;justify-content:center;'>"
        for path, name in output_paths:
            display_html += f'''
            <div style="margin:20px;">
                <img src="/download/{name}" width="300"><br>
                <a href="/download/{name}" download><button>Download {name}</button></a>
            </div>'''

        # ZIP button
        zip_data = BytesIO()
        with zipfile.ZipFile(zip_data, 'w') as zf:
            for path, name in output_paths:
                zf.write(path, name)
        zip_data.seek(0)
        # Temp zip save (download ke liye)
        zip_path = os.path.join(app.config['UPLOAD_FOLDER'], 'ALL_CLEAN_FINGERPRINTS.zip')
        with open(zip_path, 'wb') as f:
            f.write(zip_data.read())

        display_html += f'''
        <br><br><a href="/download/ALL_CLEAN_FINGERPRINTS.zip">
        <button style="padding:20px 50px; font-size:24px; background:green;">
            Download Sab 5 Ek Saath (ZIP)
        </button></a><hr><a href="/">Ek aur batch</a>'''

        return display_html

    return HTML

@app.route('/download/<filename>')
def download(filename):
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return send_file(path, as_attachment=True)
