from datetime import datetime
from app import db

class Project(db.Model):
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    project_code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Site specific fields (migrated from Site model)
    address = db.Column(db.Text)
    is_head_office = db.Column(db.Boolean, default=False)
    
    # Relationships
    letters = db.relationship('Letter', backref='project', lazy='dynamic')
    users = db.relationship('User', foreign_keys='User.project_id', backref='project', lazy='dynamic')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_projects')
    
    def __repr__(self):
        return f'<Project {self.name}>'
        
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'project_code': self.project_code
        } 