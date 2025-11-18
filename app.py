from flask import Flask, request, send_file, render_template_string
from fingerprint_enhancer import enhance_fingerprint
import cv2
import numpy as np
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1000 * 1000  # 16MB max
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
<p>1 fingerprint upload karo → clean black ridges + white background milega</p>
<form method=post enctype=multipart/form-data>
<input type=file name=file accept="image/*" required>
<br><br>
<button type=submit>Enhance Karo!</button>
</form>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files['file']
        if not file or file.filename == '':
            return "<h3>File nahi chuna!</h3><a href='/'>Wapas</a>"

        filename = secure_filename(file.filename)
        input_path = os.path.join('/tmp', filename)
        file.save(input_path)

        try:
            img = cv2.imread(input_path, 0)
            if img is None:
                return "<h3>Invalid image!</h3><a href='/'>Wapas</a>"

            enhanced = enhance_fingerprint(img)
            final = (enhanced.astype(np.uint8) * 255)
            final = 255 - final  # white background + black ridges

            output_path = '/tmp/CLEAN_' + filename
            cv2.imwrite(output_path, final)

            return f'''
            <h2>Ho Gaya Bhai! 🔥</h2>
            <img src="/result/{filename}"><br><br>
            <a href="/result/{filename}" download>
                <button style="padding:20px 50px;font-size:22px;">Download Clean Fingerprint</button>
            </a>
            <hr><a href="/">Ek aur karo</a>
            '''
        except Exception as e:
            return f"<h3>Error: {str(e)}</h3><a href='/'>Wapas</a>"

    return HTML

@app.route('/result/<filename>')
def result(filename):
    path = '/tmp/CLEAN_' + filename
    return send_file(path, as_attachment=False)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
