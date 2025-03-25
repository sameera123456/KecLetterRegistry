from datetime import datetime
from app import db

class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String(500), nullable=False)
    description = db.Column(db.String(200))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Setting {self.key}={self.value}>'
    
    @classmethod
    def get(cls, key, default=None):
        """Get a setting value by key with optional default"""
        setting = cls.query.filter_by(key=key).first()
        if setting:
            # Try to convert to appropriate type
            if setting.value.lower() in ('true', 'false'):
                return setting.value.lower() == 'true'
            try:
                if '.' in setting.value:
                    return float(setting.value)
                return int(setting.value)
            except ValueError:
                return setting.value
        return default
    
    @classmethod
    def set(cls, key, value, description=None):
        """Set a setting value, create if doesn't exist"""
        setting = cls.query.filter_by(key=key).first()
        if setting:
            setting.value = str(value)
            setting.updated_at = datetime.utcnow()
            if description:
                setting.description = description
        else:
            setting = cls(key=key, value=str(value), description=description)
            db.session.add(setting)
        db.session.commit()
        return setting 