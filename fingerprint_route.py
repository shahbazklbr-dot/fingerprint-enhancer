
import os, time, zipfile
from flask import Blueprint, request, render_template, session, redirect, url_for, send_file, flash
from werkzeug.utils import secure_filename
from models import db, User, Transaction
import cv2, numpy as np

fp_bp = Blueprint('fp', __name__)

COST_PER_IMAGE=1000

def login_required(f):
    from functools import wraps
    @wraps(f)
    def w(*a,**k):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*a,**k)
    return w

def enhance_fingerprint(img):
    return cv2.GaussianBlur(img,(3,3),0)  # placeholder

@fp_bp.route('/', methods=['GET','POST'])
@login_required
def cleaner():
    user=User.query.get(session['user_id'])
    if request.method=='POST':
        files=request.files.getlist('files')
        if not files:
            flash('No files')
            return redirect(url_for('fp.cleaner'))
        if len(files)>5:
            flash('Max 5')
            return redirect(url_for('fp.cleaner'))
        total=COST_PER_IMAGE*len(files)
        if user.balance<total:
            flash('Low balance')
            return redirect(url_for('fp.cleaner'))
        user.balance-=total
        db.session.add(Transaction(user_id=user.id, amount=-total, type='deduct', description='Cleaning'))
        db.session.commit()
        out=[]
        for f in files:
            fn=secure_filename(f.filename)
            p='/tmp/in_'+fn
            f.save(p)
            img=cv2.imread(p,0)
            enh=enhance_fingerprint(img)
            outp='/tmp/CLEAN_'+fn
            cv2.imwrite(outp, enh)
            out.append(outp)
        zipname=f"/mnt/data/cleaned_{int(time.time())}.zip"
        with zipfile.ZipFile(zipname,'w') as z:
            for p in out:
                z.write(p, os.path.basename(p))
        return send_file(zipname, as_attachment=True)
    return render_template('user_dashboard.html', balance=user.balance)
