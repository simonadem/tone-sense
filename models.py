from database import db 
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import uuid
import hashlib
import os
from cryptography.fernet import Fernet
fernet_key = os.environ.get('FERNET_KEY')
cipher = Fernet(fernet_key.encode())


# stores users credentials when an account is made 
class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    
    email_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    _email_encrypted = db.Column("email", db.LargeBinary, nullable=False)
    
    psw_hash = db.Column(db.String(255), nullable=False)
    records = db.relationship('AudioData', backref='user', lazy=True, cascade="all, delete-orphan")

    def set_email(self, email: str):
        normalized = email.strip().lower()
        # 1. Create a searchable fingerprint (cannot be reversed)
        self.email_hash = hashlib.sha256(normalized.encode()).hexdigest()
        # 2. Encrypt the email using our cipher (can be reversed)
        self._email_encrypted = cipher.encrypt(normalized.encode())

    def get_email(self) -> str:
        # Decrypts the binary data back into a readable string
        return cipher.decrypt(self._email_encrypted).decode()

    @staticmethod
    def find_by_email(email: str):
        target_hash = hashlib.sha256(email.strip().lower().encode()).hexdigest()
        return User.query.filter_by(email_hash=target_hash).first()

    def set_psw(self, psw: str) -> None:
        self.psw_hash = generate_password_hash(psw, method='pbkdf2:sha256:260000')

    def check_psw(self, psw: str) -> bool:
        return check_password_hash(self.psw_hash, psw)
    
# audit logging for security measures
class AuditLog(db.Model):
    __tablename__='audit_log'
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
def __repr__(self):
    return f'<AuditLog user={self.user_id} action={self.action}>'



# stores audio data for consensual emotion tracking over time
class AudioData(db.Model):
    __tablename__='audio_data'
    id = db.Column(db.Integer, primary_key=True)
    # anonymized public identifier for the specific recording 
    id_anon = db.Column(db.String(36), unique=True,nullable=False,default=lambda: str(uuid.uuid4()))
    # foreign key connected to user
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    prediction = db.Column(db.String(50), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    # recording date and time
    created_at = db.Column(db.DateTime(timezone=True), default= lambda: datetime.now(timezone.utc))
    # debugging
    def __repr__(self):
        return f'<AudioData {self.id_anon} - {self.prediction} ({self.confidence:.0%})>'