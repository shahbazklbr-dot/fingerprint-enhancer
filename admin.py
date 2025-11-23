
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import db, User, Transaction
from functools import wraps

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def w(*a,**k):
        if session.get('role')!='superadmin':
            flash('Admin only')
            return redirect(url_for('auth.login'))
        return f(*a,**k)
    return w

@admin_bp.route('/')
@admin_required
def dashboard():
    users=User.query.all()
    return render_template('admin_dashboard.html', users=users)

@admin_bp.route('/topup/<int:user_id>', methods=['POST'])
@admin_required
def topup(user_id):
    amount=int(request.form['amount'])
    u=User.query.get_or_404(user_id)
    u.balance+=amount
    txn=Transaction(user_id=u.id, amount=amount, type='add', description='Admin top-up')
    db.session.add(txn)
    db.session.commit()
    flash('Balance updated')
    return redirect(url_for('admin.dashboard'))
