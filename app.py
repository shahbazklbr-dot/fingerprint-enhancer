from flask import Flask, request, send_file, render_template_string
from fingerprint_enhancer import enhance_fingerprint
import cv2
import numpy as np
import os
from werkzeug.utils import secure_filename
import threading
import time

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp'
os.makedirs('/tmp', exist_ok=True)

# Global variable mein result store karenge
processing_results = {}

HTML = '''
<!DOCTYPE html>
<html>
<head><title>5 Fingerprint Enhancer</title>
<style>
body{font-family:Arial;text-align:center;margin:50px;background:#f0f0f0;}
h1{color:#333;}input,button{padding:15px;font-size:18px;margin:10px;border-radius:8px;}
button{background:#007bff;color:white;border:none;cursor:pointer;}
</style>
</head>
<body>
<h1>Ek Saath 5 Fingerprint Upload Karo</h1>
<p>5 tak images select karo → sab clean white background ban jayengi</p>
<form method=post enctype=multipart/form-data>
<input type=file name=files accept="image/*" multiple required>
<br><br>
<button type=submit>Enhance Karo (20-30 sec lagega)</button>
</form>
</body>
</html>
'''

def process_images(job_id, files):
    output_paths = []
    for i, file in enumerate(files):
        if not file or file.filename == '':
            continue
        filename = secure_filename(file.filename)
        input_path = os.path.join('/tmp', f"{job_id}_{filename}")
        file.save(input_path)

        img = cv2.imread(input_path, 0)
        enhanced = enhance_fingerprint(img)
        final = (enhanced.astype(np.uint8) * 255)
        final = 255 - final  # white bg + black ridges

        clean_name = f"CLEAN_{i+1}_{filename}"
        output_path = os.path.join('/tmp', f"{job_id}_{clean_name}")
        cv2.imwrite(output_path, final)
        output_paths.append((output_path, clean_name))

    processing_results[job_id] = output_paths

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        files = request.files.getlist('files')
        if len(files) == 0 or len(files) > 5:
            return "<h3>1 se 5 images select karo!</h3><a href='/'>Wapas</a>"

        job_id = str(time.time()).replace('.', '')
        threading.Thread(target=process_images, args=(job_id, files)).start()

        return f'''
        <h2>Processing shuru ho gaya... 20-30 sec lagega</h2>
        <p>Page refresh mat karna!</p>
        <script>
            setTimeout(() => location.href = "/result/{job_id}", 25000);
        </script>
        <a href="/result/{job_id}">Manual check karo (30 sec baad)</a>
        '''

    return HTML

@app.route('/result/<job_id>')
def result(job_id):
    if job_id not in processing_results:
        return "<h2>Abhi processing chal raha hai... 10 sec baad refresh karo</h2><script>setTimeout(() => location.reload(), 10000);</script>"

    output_paths = processing_results[job_id]
    del processing_results[job_id]  # memory free

    html = "<h2>Ho Gaya Bhai! 🔥</h2><div style='display:flex;flex-wrap:wrap;justify-content:center;'>"
    for path, name in output_paths:
        html += f'''
        <div style="margin:20px;">
            <img src="/download/{job_id}_{name}" width="350"><br>
            <a href="/download/{job_id}_{name}" download><button>Download {name}</button></a>
        </div>'''

    # ZIP download
    zip_path = f"/tmp/ZIP_{job_id}.zip"
    import zipfile
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for path, name in output_paths:
            zf.write(path, name)

    html += f'''
    <br><br><a href="/download/ZIP_{job_id}.zip">
    <button style="padding:20px 60px;font-size:24px;background:green;">
        Download Sab 5 Ek Saath (ZIP)
    </button></a><hr><a href="/">Ek aur batch</a>
    '''

    return html

@app.route('/download/<path:filename>')
def download(filename):
    return send_file(os.path.join('/tmp', filename), as_attachment=True if 'zip' in filename.lower() else False)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
