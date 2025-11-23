
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import db, User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        email=request.form['email']
        password=request.form['password']
        user=User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id']=user.id
            session['role']=user.role
            return redirect(url_for('fp.cleaner'))
        flash('Invalid login')
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        email=request.form['email']
        password=request.form['password']
        name=request.form.get('name')
        if User.query.filter_by(email=email).first():
            flash('Email exists')
            return redirect(url_for('auth.register'))
        u=User(email=email, name=name)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        flash('Account created')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
