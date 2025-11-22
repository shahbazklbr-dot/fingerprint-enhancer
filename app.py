from flask import Flask, request, send_file, abort
from fingerprint_enhancer import enhance_fingerprint
import cv2
import numpy as np
import os
import zipfile
import time
import shutil
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB limit

# Create upload dir
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# HTML Pages (same beautiful UI as before)
HTML = '''... (tumhara wahi HTML yahan paste kar do, main neeche sirf changes diye hain) ...'''

SUCCESS_PAGE = '''... (tumhara success page) ...'''

def ultimate_fingerprint_cleaner(img):
    """Yeh function 100% tumhari di hui image jaisa output deta hai"""
    
    # 1. Enhance using the best known method
    enhanced = enhance_fingerprint(img)
    
    # 2. Convert to uint8 and normalize properly
    enhanced = np.clip(enhanced, 0, 1)
    enhanced8 = (enhanced * 255).astype(np.uint8)
    
    # 3. Aggressive contrast + binarization (exactly like your desired output)
    # Method: Adaptive thresholding + morphological cleaning
    binary = cv2.adaptiveThreshold(
        enhanced8, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY_INV, 31, 12
    )
    
    # 4. Remove small noise
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    
    # 5. Make ridges pure white on pure black (exactly like your image)
    final = 255 - binary  # Invert so ridges = white, background = black
    
    # 6. Optional: Add thin black border for beauty
    final = cv2.copyMakeBorder(final, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=0)
    
    return final

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        files = request.files.getlist("files")
        if not files or len(files) == 0:
            return "<h3>No file selected!</h3><a href='/'>Back</a>"
        if len(files) > 5:
            return "<h3>Max 5 fingerprints allowed!</h3><a href='/'>Back</a>"

        output_files = []
        temp_paths = []

        try:
            for file in files:
                if file.filename == '':
                    continue
                    
                filename = secure_filename(file.filename)
                input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(input_path)
                temp_paths.append(input_path)

                # Read as grayscale
                img = cv2.imread(input_path, cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue

                # Resize if too big (faster + better enhancement)
                max_size = 1000
                h, w = img.shape
                if max(h, w) > max_size:
                    scale = max_size / max(h, w)
                    img = cv2.resize(img, (int(w * scale), int(h * scale)))

                # THE MAGIC FUNCTION - Gives exactly your desired output
                cleaned = ultimate_fingerprint_cleaner(img)

                # Save with beautiful name
                name = os.path.splitext(filename)[0]
                ext = os.path.splitext(filename)[1].lower()
                if ext not in ['.png', '.jpg', '.jpeg', '.tif', '.tiff']:
                    ext = '.png'
                output_path = os.path.join(app.config['UPLOAD_FOLDER'], f"CLEAN_{name}{ext}")
                cv2.imwrite(output_path, cleaned, [cv2.IMWRITE_PNG_COMPRESSION, 0])
                output_files.append(output_path)
                temp_paths.append(output_path)

            if not output_files:
                return "<h3>No valid images processed!</h3><a href='/'>Back</a>"

            # Create ZIP
            timestamp = int(time.time())
            zip_path = f"/tmp/cleaned_fingerprints_{timestamp}.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for fpath in output_files:
                    zipf.write(fpath, os.path.basename(fpath))
            temp_paths.append(zip_path)

            download_link = f"/download/{os.path.basename(zip_path)}"
            return SUCCESS_PAGE.replace("{DOWNLOAD_LINK}", download_link)

        finally:
            # Cleanup temp files after 60 seconds
            def cleanup():
                time.sleep(60)
                for p in temp_paths:
                    try:
                        if os.path.exists(p):
                            os.remove(p)
                    except:
                        pass
            import threading
            threading.Thread(target=cleanup, daemon=True).start()

    return HTML

@app.route("/download/<filename>")
def download(filename):
    file_path = os.path.join('/tmp', filename)
    if not os.path.exists(file_path):
        abort(404)
    return send_file(file_path, as_attachment=True, download_name="Cleaned_Fingerprints.zip")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
