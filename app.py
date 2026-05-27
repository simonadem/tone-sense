# flask requirements
from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
# importing torch for classification model
import torch
# load env vars 
from dotenv import load_dotenv
# loading API keys from .env file
load_dotenv()
from cryptography.fernet import Fernet  
# necessary for authentication
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer
# necessary for rate limiting 
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
#security for encryption and passwords 
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
# email verification
import resend
# numeric/audio processing
import numpy as np
# temp handling
import tempfile
# regex utils
import re
# unique id
import uuid 
# filesystem
import os 
# importing files
from database import db 
from models import User 
# audio analysis
import librosa
# neccessary for encryption
fernet_key = os.environ.get('FERNET_KEY')
if not fernet_key:
    raise ValueError('FERNET_KEY was not found in the .env file.')
cipher = Fernet(fernet_key.encode())

# creating the app instance
app = Flask(__name__)
# import the model
from model import predict_emotion

# import the admin file 
from admin import admin_bp
app.register_blueprint(admin_bp)

# handles sessions securely 
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# connecting database to the app
db.init_app(app)
# initializing flask login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
# initializing an email rate limiter to minimize the chances of spam
limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri='memory://',
)
# required for password resets 
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
# initialize resend with API key
resend.api_key = os.getenv("RESEND_API_KEY")
print(f"DEBUG: My API Key starts with: {resend.api_key[:5] if resend.api_key else 'NOT FOUND'}")
# handles sessions
@login_manager.user_loader
def load_user(user_id):
    # tells flask where to look for the user in the db by ID
    return User.query.get(int(user_id))


# home page 
@app.route('/')
def home():
    return render_template('home.html')

# implementing password strength requirements
def psw_complexity(psw):
    # no empty strings allowed
    if not psw:
        return False, 'The password field cannot be empty.'
    if len(psw) < 10:
        return False, 'The password must be at least 8 characters long'
    if not re.search(r"\d", psw):
        return False, 'The password must contain at least one number'
    if not re.search(r"[A-Z]", psw):
        return False, 'The password must cotain at least one upper letter'
    if not re.search(r"[ !@$%^&*.?/#{}]", psw):
        return False, 'The password must contain at least one special character'
    return True, ""

# login route 
@app.route('/login',methods=['GET','POST'])
@limiter.limit('3 per minute')
def login():
    if request.method == 'POST':
        email =request.form.get('email')
        password = request.form.get('psw')
        # user in the database
        user = User.find_by_email(email)
        # verifies the user
        if user and user.check_psw(password):
            # login_user bc we are using LoginManager
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.Please try again.', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')


# signup route 
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    # provide email and password 
    if request.method == 'POST':
        email = request.form.get('email')
        psw = request.form.get('psw')
        # checks password strength
        is_strong, message = psw_complexity(psw)
        if not is_strong:
            flash(message)
            return redirect(url_for('signup'))
        # sanity check for empty fields 
        if not email or not psw:
            flash('Please fill in the fields')
            return redirect(url_for('signup'))
        # check if the email exists 
        existing_user = User.find_by_email(email)
        if existing_user:
           flash('The email provided is already in use.Please try again!')
           return redirect(url_for('signup'))
        # new user and hash password
        new_user = User()
        new_user.set_email(email)
        new_user.set_psw(psw)
        # adding the user to the database
        db.session.add(new_user)
        db.session.commit()
        try:
            resend.Emails.send({
                "from": "onboarding@resend.dev",
                "to": [email],
                "subject": "Welcome to Tone Sense!",
                "html": f"""
                    <div style="font-family: Arial, sans-serif; color: #333;">
                        <h2 style="color: #ff85a2;">Welcome to the Dashboard!</h2>
                        <p>Hi there, your account <strong>{email}</strong> has been created.</p>
                        <p>We're excited to help you analyze the emotions behind the voice.</p>
                    </div>
                """
            })
        except Exception as e:
            # print the error to terminal
            # don't flash to user 
            print(f"Resend Error: {e}")
        # automatic redirection to dashboard
        login_user(new_user)
        flash('Account created successfully')
        return redirect(url_for('dashboard'))
    return render_template('signup.html')

# logout route 
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have logged out successfully!')
    return redirect(url_for('home'))

# function to send reset password emails to users
def reset_mail(to_email, reset_url):
    try:
        resend.Emails.send({
            "from": "Tone Sense <onboarding@resend.dev>",
            "to": [to_email],
            "subject": "Password Reset Request",
            "html": f"""
                <div style="font-family: sans-serif; max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px;">
                    <h2 style="color: #333;">Password Reset</h2>
                    <p>You requested to reset your password for Tone Sense. Click the button below to proceed:</p>
                    <a href="{reset_url}" 
                       style="display: inline-block; background-color: #ff85a2; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                       Reset My Password
                    </a>
                    <p style="margin-top: 20px; font-size: 12px; color: #777;">
                        If you didn't request this, you can safely ignore this email. This link expires in 1 hour.
                    </p>
                </div>
            """
        })
        return True
    except Exception as e:
        print(f"Error sending reset email: {e}")
        return False
    

# user requests a password reset
@app.route('/forgotten-password', methods=['GET', 'POST'])
@limiter.limit('10 per minute')
def forgot_psw():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.find_by_email(email=email)
        # if user exists generate a token
        if user:
            token = s.dumps(email, salt='password-reset-salt')
            reset_url = url_for('reset_psw',token=token, _external=True)
            # error handling
            try:
                reset_mail(email,reset_url)
                print(f'The email has been sent to {email}')
            except Exception as e:
                print(f'The reset failed.Details: {e}')
        flash(f'A reset link has been sent.Please check your email!')
        return redirect(url_for('login'))
    return render_template('forgot_psw.html')
# handles errors
@app.errorhandler(429)
def ratelimit_handler(e):
    flash(f'The server has received too many requests from your IP address.Please try again later')
    return redirect(url_for('home'))

# reset password for user
@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_psw(token):
    try:
        # decrypting the email from the token
        email = s.loads(token, salt='password-reset-salt', max_age=1800)
    except:
        flash(f'The reset link is invalid!')
        return redirect(url_for('forgot_psw'))
    if request.method == 'POST':
        new_psw = request.form.get('psw')
        # checks password strength
        is_strong, message = psw_complexity(new_psw)
        if not is_strong:
            flash(message)
            return render_template('reset_psw.html', token=token)
        if not new_psw:
            flash(f'Please enter your new password')
            return render_template('reset_psw.html', token=token)
        user = User.find_by_email(email=email)
        if user:
            # checking that the new password is not the same as the old one 
            if user.check_psw(new_psw):
                flash(f'Your new password cannot be the same as your old one.Please choose a different password.')
                return render_template('reset_psw.html', token=token)
            # if the password is different than the old one then proceed with the reset
            user.set_psw(new_psw)
            db.session.commit()
            flash(f'Your new password has been set successfully!')
            return redirect(url_for('login'))
    return render_template('reset_psw.html', token=token)


@app.route('/dashboard', methods=['POST', 'GET'])
@login_required
def dashboard():
    from models import AudioData
    history = AudioData.query.filter_by(user_id=current_user.id).order_by(AudioData.created_at.desc()).all()
    return render_template('dashboard.html', history=history)


# about us route
@app.route('/about-us', methods=['POST','GET'])
def about_us():
    return render_template('about_us.html')


# my account page 
@app.route('/my-account', methods=['POST', 'GET'])
def settings():
    render_template('my_account.html')

@app.route('/analyze', methods=['POST'])
@login_required
def analyze():
    audio_file = request.files.get('audio')
    if not audio_file:
        return jsonify({'error': 'No audio was received'}), 400
    
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        audio_file.save(tmp.name)
        tmp_path = tmp.name

    try:
        emotion, confidence = predict_emotion(tmp_path)
    finally:
        os.unlink(tmp_path)

    # save to history
    from models import AudioData
    record = AudioData(user_id=current_user.id, prediction=emotion, confidence=confidence)
    db.session.add(record)
    db.session.commit()

    return jsonify({'emotion': emotion.lower(), 'confidence': confidence})

@app.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    user = User.query.get(current_user.id)
    logout_user()
    db.session.delete(user)
    db.session.commit()
    flash('Your account has been deleted.')
    return redirect(url_for('home'))

with app.app_context():
    db.create_all()

if __name__=='__main__':
    app.run(debug=True)

