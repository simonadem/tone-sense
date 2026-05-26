from flask import Flask, Blueprint, render_template
from models import User, AudioData
from flask_login import login_required
from utils.decorators import admin_required

# creating an admin blueprint 
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# admin dashboard
@admin_bp.route('/')
@login_required
@admin_required
def admin_dash():
    return 'Admin Only'


# admin views users
@admin_bp.route('/users')
@login_required
@admin_required
def view_users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)


# admin views audio data 
@admin_bp.route('/audio')
@login_required
@admin_required
def view_data():
    data = AudioData.query.all()
    return render_template('admin/audio.html', data=data)