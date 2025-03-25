from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, login

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(20), default='project_user')  # Role can be 'head_office_admin', 'head_office_user', 'project_admin', 'project_user'
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)  # Admin flag (for backward compatibility)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    
    # Email notification settings
    email_notifications = db.Column(db.Boolean, default=True)
    browser_notifications = db.Column(db.Boolean, default=True)
    email_frequency = db.Column(db.String(20), default='immediate')  # immediate, daily, weekly
    
    notification_settings = db.Column(db.Text)  # JSON string for detailed settings
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    @property
    def is_head_office(self):
        if self.project:
            return self.project.is_head_office
        return False
    
    @property
    def is_head_office_admin(self):
        return self.is_head_office and self.is_admin
    
    @property
    def is_head_office_user(self):
        return self.is_head_office and not self.is_admin
    
    @property
    def is_project_admin(self):
        return not self.is_head_office and self.is_admin
    
    @property
    def is_project_user(self):
        return not self.is_head_office and not self.is_admin
    
    def get_role_display(self):
        if self.is_head_office_admin:
            return "Head Office Admin"
        elif self.is_head_office_user:
            return "Head Office User"
        elif self.is_project_admin:
            return "Project Admin"
        else:
            return "Project User"

@login.user_loader
def load_user(user_id):
    return User.query.get(int(user_id)) 