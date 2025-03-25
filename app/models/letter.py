from datetime import datetime
from app import db

class Letter(db.Model):
    __tablename__ = 'letters'
    
    id = db.Column(db.Integer, primary_key=True)
    letter_number = db.Column(db.String(50), unique=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    object_of = db.Column(db.String(200))
    project_number = db.Column(db.String(4))  # Changed to String to maintain leading zeros
    ho_number = db.Column(db.String(4))      # Changed to String to maintain leading zeros
    description = db.Column(db.Text)
    in_charge = db.Column(db.String(100))
    reference = db.Column(db.String(200))
    remarks = db.Column(db.Text)
    file_name = db.Column(db.String(255))
    is_incoming = db.Column(db.Boolean, default=False)
    letter_content = db.Column(db.LargeBinary)  # For PDF storage
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Additional fields for Excel format
    sender = db.Column(db.String(200))        # Sender's name/organization
    recipient = db.Column(db.String(200))     # Recipient's name/organization
    priority = db.Column(db.String(20))       # Priority level (High/Medium/Low)
    status = db.Column(db.String(20))         # Letter status (Pending/Processed/Archived)
    due_date = db.Column(db.DateTime)         # Due date for action
    action_taken = db.Column(db.Text)         # Action taken on the letter
    department = db.Column(db.String(100))    # Department handling the letter
    category = db.Column(db.String(100))      # Letter category
    tags = db.Column(db.String(200))          # Tags for categorization
    related_letters = db.Column(db.String(200))  # Related letter numbers
    attachments = db.Column(db.Text)          # List of attachments
    tracking_number = db.Column(db.String(50))  # Tracking number for outgoing letters
    delivery_status = db.Column(db.String(50))  # Delivery status for outgoing letters
    acknowledgment = db.Column(db.Text)       # Acknowledgment details
    follow_up_date = db.Column(db.DateTime)   # Follow-up date
    follow_up_notes = db.Column(db.Text)      # Follow-up notes
    archive_location = db.Column(db.String(200))  # Physical archive location
    archive_date = db.Column(db.DateTime)     # Date when letter was archived
    confidential = db.Column(db.Boolean, default=False)  # Confidential flag
    digital_signature = db.Column(db.String(200))  # Digital signature details
    version = db.Column(db.Integer, default=1)  # Version number for letter revisions
    last_reviewed = db.Column(db.DateTime)    # Last review date
    reviewed_by = db.Column(db.String(100))   # Last reviewed by
    review_notes = db.Column(db.Text)         # Review notes
    compliance_status = db.Column(db.String(50))  # Compliance status
    audit_trail = db.Column(db.Text)          # Audit trail information 