from flask import Flask, request, send_file, redirect, session
from fingerprint_enhancer import enhance_fingerprint
import cv2
import numpy as np
import os
from werkzeug.utils import secure_filename
import zipfile
import time

app = Flask(__name__)
app.secret_key = "supersecretkey123"  # session ke liye
app.config['UPLOAD_FOLDER'] = '/tmp'
os.makedirs('/tmp', exist_ok=True)

# ------------------ BEAUTIFUL LOGIN PAGE ------------------
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Login</title>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
<style>
    body{
        margin:0;
        padding:0;
        font-family:'Roboto', sans-serif;
        background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%);
        height:100vh;
        display:flex;
        justify-content:center;
        align-items:center;
    }
    .login-card{
        background:white;
        padding:50px 40px;
        border-radius:20px;
        box-shadow:0 20px 50px rgba(0,0,0,0.2);
        text-align:center;
        width:90%;
        max-width:400px;
        animation: fadeIn 1s ease;
    }
    .login-card h2{
        margin-bottom:20px;
        color:#333;
    }
    .login-card input{
        width:100%;
        padding:14px;
        margin:12px 0;
        border-radius:10px;
        border:1px solid #ccc;
        font-size:16px;
    }
    .login-card button{
        width:100%;
        padding:14px;
        border:none;
        border-radius:10px;
        background: #6a11cb;
        background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%);
        color:white;
        font-size:18px;
        cursor:pointer;
        margin-top:20px;
        transition:0.3s;
    }
    .login-card button:hover{
        opacity:0.9;
        transform:translateY(-3px);
    }
    .error-msg{
        color:red;
        margin-top:10px;
        font-size:14px;
    }
    @keyframes fadeIn{
        from{opacity:0; transform:translateY(20px);}
        to{opacity:1; transform:translateY(0);}
    }
</style>
</head>
<body>
<div class="login-card">
    <h2>Welcome Back</h2>
    <form method="POST">
        <input type="text" name="username" placeholder="Username" required>
        <input type="password" name="password" placeholder="Password" required>
        <button type="submit">Login</button>
    </form>
    <div class="error-msg">{{msg}}</div>
</div>
</body>
</html>
"""

# ------------------ ORIGINAL MAIN PAGE HTML ------------------
HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fingerprint Enhancer</title>
<style>
    body{margin:0;padding:0;font-family:'Segoe UI',sans-serif;background:#f5f7fa;display:flex;justify-content:center;align-items:center;min-height:100vh;color:#333;}
    .container{width:90%;max-width:520px;padding:35px;background:white;border-radius:20px;text-align:center;box-shadow:0 8px 20px rgba(0,0,0,0.12);}
    h1{font-size:30px;margin-bottom:10px;font-weight:700;color:#222;}
    p{font-size:16px;margin-bottom:25px;opacity:0.8;}
    input[type=file]{background:#eef2f5;padding:14px;border-radius:10px;width:100%;border:1px solid #d0d7de;color:#444;}
    button{margin-top:20px;padding:15px 40px;font-size:20px;border:none;border-radius:12px;background:#007bff;color:white;cursor:pointer;width:100%;}
    button:hover{background:#0056d8;transform:translateY(-3px);box-shadow:0 6px 14px rgba(0,0,0,0.2);}
    #loader-area{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(255,255,255,0.8);backdrop-filter: blur(4px);justify-content:center;align-items:center;flex-direction:column;z-index:999;}
    .spinner{width:60px;height:60px;border-radius:50%;border:6px solid rgba(0,0,0,0.1);border-top-color:#007bff;animation: spin 1s linear infinite;margin-bottom:20px;}
    @keyframes spin{0%{transform:rotate(0deg);}100%{transform:rotate(360deg);}}
    .progress-box{width:80%;height:12px;background:#e3e7eb;border-radius:8px;overflow:hidden;}
    .progress-bar{width:0%;height:100%;background:#00c2ff;transition:0.3s;}
    #loader-text{margin-top:15px;font-size:17px;color:#444;}
</style>
</head>
<body>
<div style="text-align:right; padding:20px;">
    <a href="/logout" style="font-size:18px; text-decoration:none; color:#007bff;">Logout</a>
</div>
<div class="container">
    <h1>Fingerprint Enhancer</h1>
    <p>Upload up to 5 fingerprints — get all cleaned instantly!</p>
    <form id="uploadForm" method="post" enctype="multipart/form-data">
        <input type="file" name="files" accept="image/*" multiple required>
        <button type="submit">Enhance!</button>
    </form>
</div>
<div id="loader-area">
    <div class="spinner"></div>
    <div class="progress-box">
        <div class="progress-bar" id="progress"></div>
    </div>
    <div id="loader-text">Processing fingerprints...</div>
</div>
<script>
document.getElementById("uploadForm").addEventListener("submit", function(e){
    document.getElementById("loader-area").style.display = "flex";
    let bar = document.getElementById("progress");
    let width = 0;
    let interval = setInterval(() => {
        if(width >= 100){ clearInterval(interval); } else { width += 2; bar.style.width = width + "%"; }
    }, 100);
});
</script>
</body>
</html>
'''

SUCCESS_PAGE = '''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Done</title>
<style>
    body{margin:0;padding:0;background:#f5f7fa;font-family:'Segoe UI',sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;}
    .box{background:white;padding:40px;border-radius:20px;text-align:center;box-shadow:0 8px 20px rgba(0,0,0,0.12);width:90%;max-width:450px;}
    h2{font-size:28px;color:#222;margin-bottom:10px;}
    .download-btn{margin-top:20px;padding:18px 40px;background:#28a745;color:white;font-size:20px;border:none;border-radius:12px;cursor:pointer;text-decoration:none;display:inline-block;transition:0.2s;}
    .download-btn:hover{background:#1e8a39;transform:translateY(-3px);}
    a{color:#007bff;margin-top:15px;display:block;font-size:18px;}
</style>
</head>
<body>
<div class="box">
    <h2>All fingerprints have been cleaned! 🔥</h2>
    <a href="{DOWNLOAD_LINK}" download class="download-btn">Download ALL (ZIP)</a>
    <a href="/">⟵ Return</a>
    <br><br>
    <a href="/logout" style="font-size:18px;">Logout</a>
</div>
</body>
</html>
'''

# ------------------ LOGIN ROUTE ------------------
@app.route('/login', methods=['GET','POST'])
def login():
    msg = ""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username=="AdminEnhance" and password=="FPEnhance@765":
            session["logged"] = True
            return redirect("/")
        else:
            msg = "Invalid username or password!"
    return LOGIN_HTML.replace("{{msg}}", msg)

# ------------------ LOGOUT ------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ------------------ MAIN PAGE ------------------
@app.route("/", methods=["GET","POST"])
def index():
    if "logged" not in session:
        return redirect("/login")

    if request.method=="POST":
        files = request.files.getlist("files")
        if not files or len(files)==0:
            return "<h3>No file selected!</h3><a href='/'>Return</a>"
        if len(files)>5:
            return "<h3>You can upload a maximum of 5 fingerprints.</h3><a href='/'>Return</a>"
        output_files = []
        for file in files:
            filename = secure_filename(file.filename)
            input_path = os.path.join('/tmp', filename)
            file.save(input_path)
            img = cv2.imread(input_path,0)
            if img is None: continue
            max_dim = 800
            h,w = img.shape
            if max(h,w) > max_dim:
                scale = max_dim/max(h,w)
                img = cv2.resize(img,(int(w*scale), int(h*scale)))
            enhanced = enhance_fingerprint(img)
            final = (enhanced.astype(np.uint8)*255)
            final = 255 - final
            output_path = '/tmp/CLEAN_'+filename
            cv2.imwrite(output_path, final)
            output_files.append(output_path)
        zip_name = f"/tmp/cleaned_{int(time.time())}.zip"
        with zipfile.ZipFile(zip_name,'w') as zipf:
            for fpath in output_files:
                zipf.write(fpath, os.path.basename(fpath))
        return SUCCESS_PAGE.replace("{DOWNLOAD_LINK}", f"/download/{os.path.basename(zip_name)}")

    return HTML

# ------------------ DOWNLOAD ------------------
@app.route("/download/<zipfile_name>")
def download(zipfile_name):
    if "logged" not in session:
        return redirect("/login")
    path = os.path.join('/tmp', zipfile_name)
    return send_file(path, as_attachment=True)

if __name__=="__main__":
    app.run(host="0.0.0.0", port=8080)
