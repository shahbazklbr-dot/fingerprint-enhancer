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
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fingerprint Cleaner</title>

<style>
    body{
        margin:0;
        padding:0;
        font-family: 'Segoe UI', sans-serif;
        background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
        display:flex;
        justify-content:center;
        align-items:center;
        min-height:100vh;
        color:#fff;
    }

    .container{
        width:90%;
        max-width:520px;
        padding:30px;
        background: rgba(255,255,255,0.08);
        backdrop-filter: blur(15px);
        border-radius:20px;
        text-align:center;
        box-shadow:0 10px 25px rgba(0,0,0,0.3);
        animation: fadeIn 0.6s ease-in-out;
    }

    h1{
        font-size:32px;
        margin-bottom:10px;
        font-weight:700;
    }

    p{
        font-size:16px;
        margin-bottom:25px;
        opacity:0.9;
    }

    input[type=file]{
        background:#ffffff25;
        padding:12px;
        border-radius:10px;
        width:100%;
        color:#eee;
        border:1px solid #ffffff40;
    }

    button{
        margin-top:20px;
        padding:15px 40px;
        font-size:20px;
        border:none;
        border-radius:12px;
        background:#0d6efd;
        color:white;
        cursor:pointer;
        transition:0.25s;
        width:100%;
    }

    button:hover{
        background:#0a58ca;
        transform:translateY(-3px);
        box-shadow:0 8px 18px rgba(0,0,0,0.3);
    }

    /* Loader Background */
    #loader-area{
        display:none;
        position:fixed;
        top:0;
        left:0;
        right:0;
        bottom:0;
        background:rgba(0,0,0,0.7);
        backdrop-filter: blur(6px);
        justify-content:center;
        align-items:center;
        flex-direction:column;
        z-index:999;
    }

    /* Loader Animation */
    .spinner{
        width:70px;
        height:70px;
        border-radius:50%;
        border:6px solid rgba(255,255,255,0.2);
        border-top-color:#fff;
        animation: spin 1s linear infinite;
        margin-bottom:20px;
    }

    @keyframes spin{
        0%{transform:rotate(0deg);}
        100%{transform:rotate(360deg);}
    }

    /* Progress Bar */
    .progress-box{
        width:80%;
        height:12px;
        background:rgba(255,255,255,0.2);
        border-radius:8px;
        overflow:hidden;
    }
    .progress-bar{
        width:0%;
        height:100%;
        background:#00ffea;
        transition:0.3s;
    }

    #loader-text{
        margin-top:15px;
        font-size:18px;
        letter-spacing:1px;
    }

    @keyframes fadeIn{
        from{opacity:0; transform:translateY(15px);}
        to{opacity:1; transform:translateY(0);}
    }

</style>
</head>

<body>

<div class="container">
    <h1>Fingerprint Enhancer</h1>
    <p>Upload up to 5 fingerprints — get all cleaned instantly!</p>

    <form id="uploadForm" method="post" enctype="multipart/form-data">
        <input type="file" name="files" accept="image/*" multiple required>
        <button type="submit">Enhance!</button>
    </form>
</div>

<!-- Loader Overlay -->
<div id="loader-area">
    <div class="spinner"></div>
    <div class="progress-box">
        <div class="progress-bar" id="progress"></div>
    </div>
    <div id="loader-text">Processing...</div>
</div>

<script>
    document.getElementById("uploadForm").addEventListener("submit", function(e){
        document.getElementById("loader-area").style.display = "flex";

        let bar = document.getElementById("progress");
        let width = 0;

        let interval = setInterval(() => {
            if(width >= 100){
                clearInterval(interval);
            } else {
                width += 2;
                bar.style.width = width + "%";
            }
        }, 100);
    });
</script>

</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':

        files = request.files.getlist("files")

        if not files or len(files) == 0:
            return "<h3>No file selected!</h3><a href='/'>Return</a>"

        if len(files) > 5:
            return "<h3>You can upload a maximum of 5 fingerprints.</h3><a href='/'>Return</a>"

        output_files = []

        for file in files:
            filename = secure_filename(file.filename)
            input_path = os.path.join('/tmp', filename)
            file.save(input_path)

            img = cv2.imread(input_path, 0)
            if img is None:
                continue

            # FREE PLAN SAFE RESIZE
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

            # MEMORY CLEANUP
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
        <h2>All fingerprints have been cleaned! 🔥</h2>
        <a href="/download/{os.path.basename(zip_name)}" download>
            <button style="padding:20px 50px;font-size:22px;">Download ALL (ZIP)</button>
        </a>
        <hr><a href="/">Return</a>
        '''

    return HTML


@app.route("/download/<zipfile_name>")
def download(zipfile_name):
    path = os.path.join('/tmp', zipfile_name)
    return send_file(path, as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
