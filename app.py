from flask import Flask, request, send_file, render_template_string
from fingerprint_enhancer import enhance_fingerprint
import cv2
import numpy as np
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

HTML = '''
<!DOCTYPE html>
<html><head><title>Fingerprint Cleaner</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{font-family:Arial;text-align:center;margin:50px;background:#f4f4f4;}
h1{color:#333;}input,button{padding:15px;font-size:18px;margin:10px;border-radius:8px;}
button{background:#007bff;color:white;border:none;cursor:pointer;}
img{max-width:90%;margin:20px;}</style></head>
<body><h1>Fingerprint Enhancer</h1>
<p>Low quality fingerprint daalo → clean black on white milega</p>
<form method=post enctype=multipart/form-data>
<input type=file name=file accept=image/* required>
<br><br><button type=submit>Enhance Karo!</button></form></body></html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files['file']
        if file:
            filename = secure_filename(file.filename)
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(input_path)

            img = cv2.imread(input_path, 0)
            enhanced = enhance_fingerprint(img)
            final = (enhanced.astype(np.uint8) * 255)
            final = 255 - final  # white background + black ridges

            output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'CLEAN_' + filename)
            cv2.imwrite(output_path, final)

            return f'''
            <h2>Ho Gaya Bhai! 🔥</h2>
            <img src="/download/{filename}"><br><br>
            <a href="/download/{filename}">
            <button style="padding:20px 40px;font-size:20px">Download Clean Fingerprint</button>
            </a><hr><a href="/">Ek aur try karo</a>
            '''
    return HTML

@app.route('/download/<filename>')
def download(filename):
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'CLEAN_' + filename)
    return send_file(output_path, as_attachment=True, download_name="CLEAN_FINGERPRINT.jpg")

if __name__ == '__main__':
    app.run()
