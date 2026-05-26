from database import db
from models import AuditLog

# logs user's activity
def log_action(user, action):
    try:
        log=AuditLog(user_id=user.id if user else None, action=action)
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()

