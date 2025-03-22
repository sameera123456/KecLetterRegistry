from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, send_file, send_from_directory, abort, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user, login_required
from datetime import datetime, timedelta
import os
import uuid
import secrets
import shutil
import io
from functools import wraps
import json
import logging
from logging.handlers import RotatingFileHandler
from logging import Formatter
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_bcrypt import Bcrypt

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'letter_registry.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # 64MB max file size (increased from 16MB)
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Initialize Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize logging
if not os.path.exists('logs'):
    os.makedirs('logs')
    
# File logger
file_handler = RotatingFileHandler('logs/letter_registry.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Letter Registry startup')

# Add Flask-APScheduler for automated backups
from flask_apscheduler import APScheduler
scheduler = APScheduler()
scheduler.init_app(app)

def auto_backup_database():
    """Create an automatic database backup"""
    # First check if auto-backup is enabled
    if not Setting.get('auto_backup_enabled', False):
        app.logger.info("Auto backup is disabled, skipping scheduled backup")
        return
        
    app.logger.info("Running scheduled auto-backup")
    try:
        # Get the current database path
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        if not db_uri.startswith('sqlite:///'):
            app.logger.error("Auto-backup only supports SQLite databases")
            return
            
        if db_uri[10:].startswith('/'):
            # Absolute path
            db_path = db_uri[10:]
        else:
            # Relative path
            db_path = os.path.join(app.root_path, db_uri[10:])
        
        if not os.path.exists(db_path):
            app.logger.error(f"Database file not found at path: {db_path}")
            return
            
        # Create backup filename
        db_name = os.path.basename(db_path)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'auto_{db_name}_{timestamp}.db'
        
        # Create backups directory if it doesn't exist
        backup_dir = os.path.join(app.root_path, 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Copy the current database file to the backup directory
        shutil.copy2(db_path, backup_path)
        
        app.logger.info(f"Auto backup created: {backup_filename}")
        
        # Create a notification about the auto-backup
        try:
            create_notification(
                title="Auto Database Backup Created",
                message=f"A scheduled automatic database backup was created",
                icon="fa-database",
                icon_color="bg-info"
            )
        except Exception as e:
            app.logger.error(f"Error creating notification for auto-backup: {str(e)}")
            
        # Optional: Cleanup old auto-backups
        cleanup_old_auto_backups()
        
    except Exception as e:
        app.logger.error(f"Error during auto-backup: {str(e)}")

def cleanup_old_auto_backups():
    """Remove old auto-backups, keeping only recent ones"""
    try:
        max_backups = int(Setting.get('auto_backup_keep_count', 5))
        backup_dir = os.path.join(app.root_path, 'backups')
        
        # Get all auto-backup files sorted by modification time (oldest first)
        auto_backups = []
        for filename in os.listdir(backup_dir):
            if filename.startswith('auto_') and filename.endswith('.db'):
                file_path = os.path.join(backup_dir, filename)
                if os.path.isfile(file_path):
                    auto_backups.append((file_path, os.path.getmtime(file_path)))
        
        # Sort by modification time (oldest first)
        auto_backups.sort(key=lambda x: x[1])
        
        # Remove old backups if we have more than max_backups
        if len(auto_backups) > max_backups:
            for file_path, _ in auto_backups[:-max_backups]:
                try:
                    os.remove(file_path)
                    app.logger.info(f"Removed old auto-backup: {os.path.basename(file_path)}")
                except Exception as e:
                    app.logger.error(f"Error removing old auto-backup: {str(e)}")
    except Exception as e:
        app.logger.error(f"Error cleaning up old auto-backups: {str(e)}")

# Schedule weekly backups - every Monday at 1:00 AM
@scheduler.task('cron', id='auto_backup', day_of_week=0, hour=1, minute=0)
def scheduled_backup():
    with app.app_context():
        auto_backup_database()

# Initialize default settings if they don't exist
def init_default_settings():
    with app.app_context():
        # Set default settings if they don't exist
        settings = [
            ('auto_backup_enabled', 'true', 'Enable automatic weekly database backups'),
            ('auto_backup_keep_count', '5', 'Number of automatic backups to keep')
        ]
        
        for key, value, description in settings:
            setting = Setting.query.filter_by(key=key).first()
            if not setting:
                setting = Setting(key=key, value=value, description=description)
                db.session.add(setting)
                app.logger.info(f"Created default setting: {key}={value}")
        
        db.session.commit()

# Start the scheduler
scheduler.start()

# Initialize default settings when the app starts
@app.before_first_request
def before_first_request():
    init_default_settings()

# Helper Functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Models
class Site(db.Model):
    __tablename__ = 'sites'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.Text)
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    users = db.relationship('User', backref='site', lazy='dynamic')
    projects = db.relationship('Project', backref='site', lazy='dynamic')
    letters = db.relationship('Letter', backref='site', lazy='dynamic')
    
    def __repr__(self):
        return f'<Site {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name
        }

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(20), default='user')  # Role can be 'admin' or 'user'
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)  # Admin flag
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'))
    
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
        if self.site:
            return self.site.name == 'Head Office'
        return False

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    icon = db.Column(db.String(50), default='fa-envelope')
    icon_color = db.Column(db.String(50), default='bg-primary')
    link = db.Column(db.String(255))
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relationship with user
    user = db.relationship('User', backref=db.backref('notifications', lazy=True))

class Project(db.Model):
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    project_code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'))
    
    # Relationships
    letters = db.relationship('Letter', backref='project', lazy='dynamic')

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
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'))
    
    # New fields for Excel format
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

# User Loader
@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

# Admin Required Decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('You do not have permission to access this feature.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Site Access Control Helper Functions
def get_user_site_id():
    """Get the site ID from the session or current user"""
    site_id = session.get('site_id')
    if not site_id and current_user.is_authenticated:
        site_id = current_user.site_id
    return site_id

def site_query_filter(query, model):
    """Filter query by site_id unless user is from Head Office"""
    site_id = get_user_site_id()
    
    if current_user.is_authenticated and current_user.is_head_office:
        return query  # Head Office users can see all data
    
    if model == Letter:
        try:
            # Get project IDs for the current site
            project_ids = [p.id for p in Project.query.filter_by(site_id=site_id).all()]
            if project_ids:
                return query.filter(Letter.project_id.in_(project_ids))
            # If no projects found, return no results
            return query.filter(Letter.id < 0)
        except Exception as e:
            print(f"Error in site_query_filter for Letter: {str(e)}")
            # Return a query that yields no results as a fallback
            return query.filter(Letter.id < 0)
    
    if hasattr(model, 'site_id'):
        return query.filter(model.site_id == site_id)
    
    return query

# Routes
@app.route('/')
@login_required
def index():
    # Get statistics
    site_id = get_user_site_id()
    
    try:
        # Filter by site unless head office
        if current_user.is_head_office:
            total_projects = Project.query.count()
            total_letters = Letter.query.count()
            incoming_letters = Letter.query.filter_by(is_incoming=True).count()
            outgoing_letters = Letter.query.filter_by(is_incoming=False).count()
            recent_letters = Letter.query.order_by(Letter.created_at.desc()).limit(5).all()
        else:
            # Get site info
            current_site = Site.query.get(site_id)
            print(f"Dashboard for site: {current_site.name if current_site else 'Unknown'}, ID: {site_id}")
            
            # Get projects for this site
            site_projects = Project.query.filter_by(site_id=site_id).all()
            total_projects = len(site_projects)
            
            # Debug the projects
            print(f"Found {total_projects} projects for site {site_id}")
            for project in site_projects:
                print(f"Project: {project.project_code} - {project.name}")
                
            # Get project IDs
            project_ids = [p.id for p in site_projects]
            
            # Get letters for these projects
            if project_ids:
                letters_query = Letter.query.filter(Letter.project_id.in_(project_ids))
                total_letters = letters_query.count()
                incoming_letters = letters_query.filter_by(is_incoming=True).count()
                outgoing_letters = letters_query.filter_by(is_incoming=False).count()
                recent_letters = letters_query.order_by(Letter.created_at.desc()).limit(5).all()
            else:
                total_letters = 0
                incoming_letters = 0
                outgoing_letters = 0
                recent_letters = []
                print("No projects found for this site, so no letters to display")
    except Exception as e:
        print(f"Error in index route: {str(e)}")
        import traceback
        traceback.print_exc()
        total_projects = 0
        total_letters = 0
        incoming_letters = 0
        outgoing_letters = 0
        recent_letters = []
    
    stats = {
        'total_projects': total_projects,
        'total_letters': total_letters,
        'incoming_letters': incoming_letters,
        'outgoing_letters': outgoing_letters
    }
    
    # Get current site info
    current_site = Site.query.get(site_id) if site_id else None
    
    # Get projects for user dropdown in base template
    all_projects = Project.query.all()
    
    return render_template('index.html', recent_letters=recent_letters, stats=stats, 
                          current_site=current_site, projects=all_projects)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        site_id = request.form.get('site_id')
        remember = request.form.get('remember', False)
        
        user = User.query.filter_by(username=username).first()
        
        if user is None or not user.check_password(password):
            flash('Invalid username or password', 'error')
            return redirect(url_for('login'))
        
        # Check if the user belongs to the selected site or is a head office user
        if user.site_id and int(user.site_id) != int(site_id) and not user.is_head_office:
            flash('You do not have permission to log in from this site.', 'error')
            return redirect(url_for('login'))
            
        # Store site_id in session
        session['site_id'] = site_id
        
        login_user(user, remember=remember)
        next_page = request.args.get('next')
        if not next_page or next_page.startswith('/'):
            next_page = url_for('index')
        
        return redirect(next_page)
    
    # Get Head Office site
    head_office = Site.query.filter_by(name='Head Office').first()
    sites = []
    
    # Add head office first if it exists
    if head_office:
        sites.append(head_office)
    
    # Get projects instead of sites
    projects = Project.query.all()
    
    # Create a combined list of Head Office and all projects for login dropdown
    login_options = []
    
    # Add head office first if it exists (for admin access)
    if head_office:
        login_options.append(head_office)
    
    # Add projects for project-specific access
    for project in projects:
        # We'll create a Site-like object with the necessary properties for the template
        class ProjectOption:
            def __init__(self, id, name):
                self.id = id
                self.name = name
                
        project_option = ProjectOption(
            id=project.site_id, 
            name=f"{project.project_code} - {project.name}"
        )
        login_options.append(project_option)
    
    return render_template('login.html', sites=login_options)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        special_code = request.form.get('special_code')
        user_type = request.form.get('user_type', 'regular')
        site_id = request.form.get('site_id')
        
        # Check if admin registration
        is_admin = False
        if user_type == 'admin' and special_code == 'KEC0213ADMIN':
            is_admin = True
        elif user_type == 'regular' and special_code == 'KEC0213':
            is_admin = False
        else:
            flash(f'Invalid registration code for {user_type} user', 'error')
            return redirect(url_for('register'))
        
        # Validate password match
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('register'))
            
        # Validate password length
        if len(password) < 8:
            flash('Password must be at least 8 characters long', 'error')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('register'))
        
        # Validate site selection
        if not site_id:
            flash('Please select a site', 'error')
            return redirect(url_for('register'))
            
        # Create the user
        user = User(
            username=username, 
            email=email, 
            is_admin=is_admin,
            site_id=site_id
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Account created successfully! You can now log in.', 'success')
        return redirect(url_for('login'))
    
    # Get all sites for dropdown
    sites = Site.query.all()
    return render_template('register.html', sites=sites)

@app.route('/dashboard')
@login_required
def dashboard():
    user_projects = Project.query.filter_by(created_by=current_user.id).all()
    
    recent_activity = Letter.query.filter_by(created_by=current_user.id)\
        .order_by(Letter.created_at.desc())\
        .limit(10)\
        .all()
    
    return render_template('index.html', projects=user_projects, recent_activity=recent_activity)

@app.route('/notifications')
@login_required
def view_notifications():
    # Get all notifications for the current user
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    
    # Mark all as read
    for notification in notifications:
        notification.read = True
    db.session.commit()
    
    return render_template('notifications.html', notifications=notifications)

@app.route('/projects')
@login_required
def projects():
    search_term = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    site_id = get_user_site_id()
    
    try:
        # Print debug info
        site = Site.query.get(site_id) if site_id else None
        print(f"Projects route - User: {current_user.username}, Site: {site.name if site else 'Unknown'}, Site ID: {site_id}")
        
        # Debug all sites and projects in database
        all_sites = Site.query.all()
        print(f"All sites: {[(s.id, s.name, s.code) for s in all_sites]}")
        
        all_projects = Project.query.all()
        print(f"All projects: {[(p.id, p.project_code, p.site_id) for p in all_projects]}")
        
        # Start with base query
        query = Project.query
        
        # Filter by site
        if not current_user.is_head_office and site_id:
            print(f"Filtering projects by site_id: {site_id}")
            query = query.filter_by(site_id=site_id)
            
            # Check if any projects match the filter
            filtered_projects = query.all()
            if not filtered_projects and site:
                print(f"No projects found with site_id {site_id}, trying to match by code: {site.code}")
                # If no projects found by site_id, try to find by site code match
                query = Project.query.filter(Project.project_code.startswith(site.code))
                projects_by_code = query.all()
                print(f"Projects found by code: {[(p.id, p.project_code) for p in projects_by_code]}")
                
                # Update these projects to have the correct site_id
                for project in projects_by_code:
                    if project.site_id != site_id:
                        print(f"Updating project {project.project_code} site_id from {project.site_id} to {site_id}")
                        project.site_id = site_id
                db.session.commit()
        
        # Apply search filtering if provided
        if search_term:
            query = query.filter(
                db.or_(
                    Project.name.ilike(f'%{search_term}%'),
                    Project.project_code.ilike(f'%{search_term}%'),
                    Project.description.ilike(f'%{search_term}%')
                )
            )
        
        # Order by created_at in descending order
        projects = query.order_by(Project.created_at.desc()).all()
        
        # Debug output - projects found
        print(f"Found {len(projects)} projects")
        
        # Get letter counts for each project
        for project in projects:
            try:
                # Get all letters for this project
                project_letters = Letter.query.filter_by(project_id=project.id).all()
                project.letter_count = len(project_letters)
                project.incoming_count = sum(1 for l in project_letters if l.is_incoming)
                project.outgoing_count = sum(1 for l in project_letters if not l.is_incoming)
                
                print(f"Project: {project.project_code} - {project.name}, Letters: {project.letter_count} (In: {project.incoming_count}, Out: {project.outgoing_count})")
            except Exception as e:
                print(f"Error counting letters for project {project.project_code}: {str(e)}")
                project.letter_count = 0
                project.incoming_count = 0
                project.outgoing_count = 0
        
    except Exception as e:
        print(f"Error in projects route: {str(e)}")
        import traceback
        traceback.print_exc()
        projects = []
    
    # Get current site info
    current_site = Site.query.get(site_id) if site_id else None
    
    return render_template('projects.html', projects=projects, current_site=current_site)

@app.route('/projects/create', methods=['GET', 'POST'])
@login_required
def create_project():
    # Check if user is a head office admin
    if not (current_user.is_admin and current_user.is_head_office):
        flash('Only Head Office administrators can create projects.', 'error')
        return redirect(url_for('projects'))
        
    if request.method == 'POST':
        project_code = request.form.get('project_code')
        name = request.form.get('name')
        description = request.form.get('description')
        
        # Validate project code uniqueness
        existing_project = Project.query.filter_by(project_code=project_code).first()
        if existing_project:
            flash('Project code already exists. Please use a different code.', 'error')
            return redirect(url_for('create_project'))
        
        site_id = get_user_site_id()
        
        # Create new project
        new_project = Project(
            project_code=project_code,
            name=name,
            description=description,
            created_by=current_user.id,
            site_id=site_id
        )
        
        db.session.add(new_project)
        db.session.commit()
        
        # Create notification for project creation
        create_notification(
            title="New Project Created",
            message=f"A new project ({project_code}: {name}) has been created",
            icon="fa-project-diagram",
            icon_color="bg-success",
            link=f"/view_project/{new_project.id}"
        )
        
        flash('Project created successfully!', 'success')
        return redirect(url_for('projects'))
    
    # Get current site info
    site_id = get_user_site_id()
    current_site = Site.query.get(site_id) if site_id else None
    
    return render_template('create_project.html', current_site=current_site)

@app.route('/projects/<int:project_id>')
@login_required
def view_project(project_id):
    project = Project.query.get_or_404(project_id)
    letters = Letter.query.filter_by(project_id=project_id).order_by(Letter.created_at.desc()).all()
    
    # Calculate statistics
    total_letters = len(letters)
    incoming_letters = sum(1 for letter in letters if letter.is_incoming)
    outgoing_letters = total_letters - incoming_letters
    
    stats = {
        'total_letters': total_letters,
        'incoming_letters': incoming_letters,
        'outgoing_letters': outgoing_letters
    }
    
    return render_template('view_project.html',
                         project=project,
                         letters=letters,
                         stats=stats)

@app.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    # Check if user is a head office admin
    if not (current_user.is_admin and current_user.is_head_office):
        flash('Only Head Office administrators can edit projects.', 'error')
        return redirect(url_for('view_project', project_id=project_id))
        
    project = Project.query.get_or_404(project_id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        project.name = name
        project.description = description
        project.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Project updated successfully!', 'success')
        return redirect(url_for('view_project', project_id=project.id))
    
    return render_template('edit_project.html', project=project)

@app.route('/projects/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    # Check if user is a head office admin
    if not (current_user.is_admin and current_user.is_head_office):
        flash('Only Head Office administrators can delete projects.', 'error')
        return redirect(url_for('view_project', project_id=project_id))
        
    project = Project.query.get_or_404(project_id)
    
    # Check if project has letters
    letter_count = Letter.query.filter_by(project_id=project_id).count()
    if letter_count > 0:
        flash(f'Cannot delete project with letters. This project has {letter_count} letters. Please delete all letters first.', 'error')
        return redirect(url_for('view_project', project_id=project_id))
    
    try:
        db.session.delete(project)
        db.session.commit()
        flash('Project deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting project: {str(e)}', 'error')
        return redirect(url_for('view_project', project_id=project_id))
    
    return redirect(url_for('projects'))

@app.route('/letters')
@login_required
def letters():
    search_term = request.args.get('search', '')
    letter_type = request.args.get('type', 'all')
    project_code = request.args.get('project_code', '')  # Get project code from query params
    site_id = get_user_site_id()
    
    try:
        print(f"Letters request - User: {current_user.username}, Site ID: {site_id}, Project Code: {project_code}, Type: {letter_type}")
        
        # Start with base query
        query = Letter.query
        
        # Get projects for this site
        if not current_user.is_head_office:
            # For project site users, directly query for projects matching their site code
            site = Site.query.get(site_id)
            if site:
                print(f"Current site: {site.name}, Code: {site.code}")
                
                # Debug all projects in the database
                all_projects = Project.query.all()
                print(f"All projects in database: {[(p.id, p.project_code, p.site_id) for p in all_projects]}")
                
                # Find projects matching this site code
                site_projects = Project.query.filter_by(site_id=site_id).all()
                
                print(f"Projects for site {site_id}: {[(p.id, p.project_code) for p in site_projects]}")
                
                if site_projects:
                    project_ids = [p.id for p in site_projects]
                    project_codes = [p.project_code for p in site_projects]
                    print(f"Found {len(project_ids)} projects for site {site_id}: {project_codes}")
                    
                    # Debug all letters in database
                    all_letters = Letter.query.all()
                    print(f"All letters in database: {[(l.id, l.letter_number, l.project_id) for l in all_letters]}")
                    
                    # Filter by project IDs - direct relationship to show all letters for this site's projects
                    query = query.filter(Letter.project_id.in_(project_ids))
                    
                    # Filter by specific project code if provided
                    if project_code:
                        project = Project.query.filter_by(project_code=project_code).first()
                        if project:
                            print(f"Filtering by project code: {project_code} (ID: {project.id})")
                            query = query.filter(Letter.project_id == project.id)
                else:
                    print(f"No projects found for site {site_id}")
                    # Instead of returning empty result, we'll check if there are any projects for this site's code
                    site_code_projects = Project.query.filter(Project.project_code.startswith(site.code)).all()
                    if site_code_projects:
                        print(f"Found projects matching site code {site.code}: {[(p.id, p.project_code) for p in site_code_projects]}")
                        project_ids = [p.id for p in site_code_projects]
                        query = query.filter(Letter.project_id.in_(project_ids))
                    else:
                        query = query.filter(Letter.id < 0)  # Return empty result if no projects found
            else:
                print(f"No site found with ID {site_id}")
                query = query.filter(Letter.id < 0)  # Return empty result
        elif project_code:  # Head office user with project code filter
            project = Project.query.filter_by(project_code=project_code).first()
            if project:
                print(f"Head office filtering by project code: {project_code} (ID: {project.id})")
                query = query.filter(Letter.project_id == project.id)
        
        # Apply letter type filtering
        if letter_type == 'incoming':
            query = query.filter_by(is_incoming=True)
        elif letter_type == 'outgoing':
            query = query.filter_by(is_incoming=False)
        
        # Apply search filtering if provided
        if search_term:
            query = query.filter(
                db.or_(
                    Letter.letter_number.ilike(f'%{search_term}%'),
                    Letter.object_of.ilike(f'%{search_term}%'),
                    Letter.description.ilike(f'%{search_term}%'),
                    Letter.sender.ilike(f'%{search_term}%'),
                    Letter.recipient.ilike(f'%{search_term}%')
                )
            )
        
        # Order by created_at in descending order
        letters = query.order_by(Letter.created_at.desc()).all()
        
        # Print each letter found for debugging
        print(f"Found {len(letters)} letters:")
        for letter in letters:
            project = Project.query.get(letter.project_id)
            print(f"Letter ID: {letter.id}, Number: {letter.letter_number}, Project: {project.project_code if project else 'Unknown'}")
        
        # Get projects for filtering dropdown
        if current_user.is_head_office:
            projects = Project.query.all()
        else:
            projects = Project.query.filter_by(site_id=site_id).all()
            if not projects:
                # If no projects found by site_id, try to find by site code match
                site = Site.query.get(site_id)
                if site:
                    projects = Project.query.filter(Project.project_code.startswith(site.code)).all()
        
        # Get current site info
        current_site = Site.query.get(site_id) if site_id else None
        
        return render_template('letters.html', letters=letters, projects=projects, 
                              letter_type=letter_type, current_site=current_site,
                              project_code=project_code)
                            
    except Exception as e:
        print(f"Error in letters route: {str(e)}")
        import traceback
        traceback.print_exc()
        # Return an empty result in case of error
        return render_template('letters.html', letters=[], projects=[], 
                              letter_type=letter_type, current_site=None,
                              project_code=project_code)

def create_notification(title, message, users=None, icon='fa-envelope', icon_color='bg-primary', link=None):
    """Create a notification for specified users or all users"""
    try:
        if users is None:
            # Get all active users
            users = User.query.filter_by(is_active=True).all()
        elif not isinstance(users, list):
            users = [users]  # Convert single user to list
        
        # Current timestamp for all notifications we're creating
        current_time = datetime.now()
        # Track how many notifications we added
        notifications_added = 0
        
        for user in users:
            # Check for recent duplicate notification (within last 5 minutes)
            recent_duplicate = Notification.query.filter_by(
                user_id=user.id, 
                title=title,
                message=message
            ).filter(
                Notification.created_at > (current_time - timedelta(minutes=5))
            ).first()
            
            if recent_duplicate:
                app.logger.info(f"Skipping duplicate notification for user {user.id}: {title}")
                continue
                
            # Create notification
            notification = Notification(
                user_id=user.id,
                title=title,
                message=message,
                icon=icon,
                icon_color=icon_color,
                link=link,
                read=False,
                created_at=current_time
            )
            db.session.add(notification)
            notifications_added += 1
        
        # Commit all notifications at once if any were added
        if notifications_added > 0:
            db.session.commit()
            app.logger.info(f"Created {notifications_added} notifications: {title}")
        
        return notifications_added
    except Exception as e:
        app.logger.error(f"Error creating notification: {str(e)}")
        db.session.rollback()
        return 0

@app.route('/create_letter', methods=['GET', 'POST'])
@login_required
def create_letter():
    letter_type = request.args.get('letter_type', 'incoming')
    is_incoming = letter_type == 'incoming'
    
    if request.method == 'POST':
        project_id = request.form.get('project_id')
        date_str = request.form.get('date')
        object_of = request.form.get('object_of')
        ho_number = request.form.get('ho_number')
        project_number = request.form.get('project_number')
        description = request.form.get('description')
        in_charge = request.form.get('in_charge')
        reference = request.form.get('reference')
        remarks = request.form.get('remarks')
        sender = request.form.get('sender')
        recipient = request.form.get('recipient')
        priority = request.form.get('priority')
        status = request.form.get('status')
        
        letter_type = request.form.get('letter_type', 'incoming')
        is_incoming = letter_type == 'incoming'
        
        # Check if project exists
        project = Project.query.get(project_id)
        if not project:
            flash('Project not found', 'error')
            return redirect(url_for('create_letter'))
        
        # Convert date string to date object
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')
        except:
            date = datetime.now()
        
        # Generate letter number
        letter_type_code = "IN" if is_incoming else "OU"
        current_year = datetime.now().strftime('%y')
        letter_number = f"KEC/{project.project_code}/{letter_type_code}/{current_year}-{ho_number}-{project_number}"
        
        # Check if letter with the same number already exists
        existing_letter = Letter.query.filter_by(letter_number=letter_number).first()
        if existing_letter:
            flash('Letter with this number already exists', 'error')
            return redirect(url_for('create_letter'))
        
        # Get the file
        if 'letter_file' in request.files and request.files['letter_file'].filename:
            file = request.files['letter_file']
            if file and allowed_file(file.filename):
                file_content = file.read()
                file_name = secure_filename(file.filename)
            else:
                file_content = None
                file_name = None
        else:
            file_content = None
            file_name = None
        
        # Create letter
        letter = Letter(
            letter_number=letter_number,
            project_id=project_id,
            date=date,
            object_of=object_of,
            ho_number=ho_number,
            project_number=project_number,
            description=description,
            in_charge=in_charge,
            reference=reference,
            remarks=remarks,
            file_name=file_name,
            letter_content=file_content,
            is_incoming=is_incoming,
            created_by=current_user.id,
            sender=sender,
            recipient=recipient,
            priority=priority,
            status=status,
            site_id=project.site_id  # Set the letter's site_id to the project's site_id
        )
        
        db.session.add(letter)
        db.session.commit()
        
        # Create notification for letter creation
        create_notification(
            title="New Letter Created",
            message=f"A new {'incoming' if is_incoming else 'outgoing'} letter ({letter_number}) was registered for project {project.project_code}",
            icon="fa-envelope",
            icon_color="bg-primary" if is_incoming else "bg-warning",
            link=f"/letters/{letter.id}"
        )
        
        flash('Letter created successfully!', 'success')
        return redirect(url_for('letters'))
    
    # Get user's site ID
    site_id = get_user_site_id()
    
    # Filter projects by site if not Head Office
    if current_user.is_head_office:
        projects = Project.query.all()
        project_id = None
    else:
        # For non-head office users, get only projects for their site
        projects = Project.query.filter_by(site_id=site_id).all()
        # Pre-select the first project if available
        project_id = projects[0].id if projects else None
        
    # Format today's date for form
    today_date = datetime.now().strftime('%Y-%m-%d')
    
    return render_template('create_letter.html', projects=projects, today_date=today_date, 
                          letter_type=letter_type, is_incoming=is_incoming, project_id=project_id)

@app.route('/letters/<int:letter_id>')
@login_required
def view_letter(letter_id):
    letter = Letter.query.get_or_404(letter_id)
    project = Project.query.get(letter.project_id)
    
    # Get user's site ID
    user_site_id = get_user_site_id()
    
    # Add debug logs
    print(f"View letter request - Letter ID: {letter_id}, User: {current_user.username}, User Site ID: {user_site_id}")
    print(f"Letter details - Project ID: {letter.project_id}, Letter Site ID: {letter.site_id}")
    if project:
        print(f"Project details - Code: {project.project_code}, Project Site ID: {project.site_id}")
    
    # Check if user has access to this letter:
    # 1. Head office users can view all letters
    # 2. Site users can view letters from their site
    # 3. Site users can view letters from projects associated with their site
    has_access = (
        current_user.is_head_office or
        letter.site_id == user_site_id or
        (project and project.site_id == user_site_id) or
        (project and project.project_code.startswith(current_user.site.code if current_user.site else ''))
    )
    
    if not has_access:
        flash("You don't have permission to view this letter", "error")
        return redirect(url_for('letters'))
    
    return render_template('view_letter.html', letter=letter, project=project)

@app.route('/letters/<int:letter_id>/view_pdf')
@login_required
def view_pdf(letter_id):
    letter = Letter.query.get_or_404(letter_id)
    project = Project.query.get(letter.project_id)
    
    # Get user's site ID
    user_site_id = get_user_site_id()
    
    # Check if user has access to this letter
    has_access = (
        current_user.is_head_office or
        letter.site_id == user_site_id or
        (project and project.site_id == user_site_id) or
        (project and project.project_code.startswith(current_user.site.code if current_user.site else ''))
    )
    
    if not has_access:
        flash("You don't have permission to view this letter", "error")
        return redirect(url_for('letters'))
    
    if not letter.letter_content:
        flash('No PDF attached to this letter.', 'error')
        return redirect(url_for('view_letter', letter_id=letter.id))
    
    # Return the PDF content directly
    return send_file(
        io.BytesIO(letter.letter_content),
        mimetype='application/pdf',
        as_attachment=False,
        download_name=letter.file_name if letter.file_name else f'letter_{letter.id}.pdf'
    )

@app.route('/letters/<int:letter_id>/download')
@login_required
def download_letter(letter_id):
    letter = Letter.query.get_or_404(letter_id)
    project = Project.query.get(letter.project_id)
    
    # Get user's site ID
    user_site_id = get_user_site_id()
    
    # Check if user has access to this letter
    has_access = (
        current_user.is_head_office or
        letter.site_id == user_site_id or
        (project and project.site_id == user_site_id) or
        (project and project.project_code.startswith(current_user.site.code if current_user.site else ''))
    )
    
    if not has_access:
        flash("You don't have permission to download this letter", "error")
        return redirect(url_for('letters'))
    
    if not letter.letter_content:
        flash('No PDF attached to this letter.', 'error')
        return redirect(url_for('view_letter', letter_id=letter.id))
    
    inline = request.args.get('inline', type=int)
    
    # Determine if the file should be displayed inline or downloaded
    attachment = not bool(inline)
    
    # Return the PDF content for download
    return send_file(
        io.BytesIO(letter.letter_content),
        mimetype='application/pdf',
        as_attachment=attachment,
        download_name=letter.file_name if letter.file_name else f'letter_{letter.id}.pdf'
    )

@app.route('/letters/<int:letter_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_letter(letter_id):
    letter = Letter.query.get_or_404(letter_id)
    project = Project.query.get(letter.project_id)
    
    # Get user's site ID
    user_site_id = get_user_site_id()
    
    # Add debug logs
    print(f"Edit letter request - Letter ID: {letter_id}, User: {current_user.username}, User Site ID: {user_site_id}")
    if project:
        print(f"Project details - Code: {project.project_code}, Project Site ID: {project.site_id}")
    
    # Check if user has access to edit this letter:
    # 1. Admin users can edit all letters
    # 2. Site admins can edit letters from their site or projects
    has_access = (
        current_user.is_admin and (
            current_user.is_head_office or
            letter.site_id == user_site_id or
            (project and project.site_id == user_site_id) or
            (project and project.project_code.startswith(current_user.site.code if current_user.site else ''))
        )
    )
    
    if not has_access:
        flash("You don't have permission to edit this letter", "error")
        return redirect(url_for('letters'))
    
    if request.method == 'POST':
        letter.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d')
        letter.object_of = request.form.get('object_of')
        letter.project_number = request.form.get('project_number')
        letter.ho_number = request.form.get('ho_number')
        letter.description = request.form.get('description')
        letter.in_charge = request.form.get('in_charge')
        letter.reference = request.form.get('reference')
        letter.remarks = request.form.get('remarks')
        
        # Add the missing fields from the edit form
        letter.sender = request.form.get('sender')
        letter.recipient = request.form.get('recipient')
        letter.priority = request.form.get('priority')
        letter.status = request.form.get('status')
        
        # Handle attachment deletions
        if 'delete_current_file' in request.form:
            letter.file_name = None
            letter.letter_content = None
        
        # Handle existing attachments
        if 'delete_attachments' in request.form:
            delete_attachments = request.form.getlist('delete_attachments')
            if letter.attachments:
                current_attachments = [att.strip() for att in letter.attachments.split(',') if att.strip()]
                kept_attachments = [att for att in current_attachments if att not in delete_attachments]
                letter.attachments = ','.join(kept_attachments) if kept_attachments else None
        
        # Handle new attachments
        if 'attachments' in request.files:
            attachment_files = request.files.getlist('attachments')
            if attachment_files and attachment_files[0].filename:
                new_attachments = []
                for file in attachment_files:
                    if file and allowed_file(file.filename):
                        new_attachments.append(secure_filename(file.filename))
                
                if new_attachments:
                    if letter.attachments:
                        current_attachments = [att.strip() for att in letter.attachments.split(',') if att.strip()]
                        current_attachments.extend(new_attachments)
                        letter.attachments = ','.join(current_attachments)
                    else:
                        letter.attachments = ','.join(new_attachments)
        
        # Handle file upload - ONLY update if a new file is actually being uploaded
        if 'letter_file' in request.files and request.files['letter_file'].filename:
            file = request.files['letter_file']
            if file and allowed_file(file.filename):
                print(f"Uploading new file: {file.filename}")
                file_content = file.read()
                file_name = secure_filename(file.filename)
                # Only update file content if there's a new file
                letter.file_name = file_name
                letter.letter_content = file_content
            else:
                print(f"Invalid file upload attempt: {file.filename if file else 'No file'}")
        else:
            print(f"No new file uploaded, keeping existing file: {letter.file_name}")
            # Don't modify the existing file_name and letter_content
        
        db.session.commit()
        
        # Create notification for letter update
        create_notification(
            title="Letter Updated",
            message=f"Letter {letter.letter_number} has been updated",
            icon="fa-edit",
            icon_color="bg-info",
            link=f"/view_letter/{letter.id}"
        )
        
        flash('Letter updated successfully!', 'success')
        return redirect(url_for('view_letter', letter_id=letter.id))
    
    # Get all projects for the form
    if current_user.is_head_office:
        projects = Project.query.all()
    else:
        # For site admin, only show projects associated with their site
        projects = Project.query.filter_by(site_id=user_site_id).all()
        
    return render_template('edit_letter.html', letter=letter, projects=projects)

@app.route('/letters/<int:letter_id>/delete', methods=['POST'])
@login_required
def delete_letter(letter_id):
    letter = Letter.query.get_or_404(letter_id)
    project = Project.query.get(letter.project_id)
    project_id = letter.project_id
    is_incoming = letter.is_incoming
    source = request.form.get('source', 'project')  # Default to project view if source not specified
    
    # Get user's site ID
    user_site_id = get_user_site_id()
    
    # Add debug logs
    print(f"Delete letter request - Letter ID: {letter_id}, User: {current_user.username}, User Site ID: {user_site_id}, Source: {source}")
    if project:
        print(f"Project details - Code: {project.project_code}, Project Site ID: {project.site_id}")
    
    # Check if user has access to delete this letter:
    # 1. Admin users can delete all letters
    # 2. Site admins can delete letters from their site or projects
    has_access = (
        current_user.is_admin and (
            current_user.is_head_office or
            letter.site_id == user_site_id or
            (project and project.site_id == user_site_id) or
            (project and project.project_code.startswith(current_user.site.code if current_user.site else ''))
        )
    )
    
    if not has_access:
        flash("You don't have permission to delete this letter", "error")
        return redirect(url_for('letters'))
    
    try:
        db.session.delete(letter)
        db.session.commit()
        flash('Letter deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting letter: {str(e)}', 'error')
    
    # Redirect based on source
    if source == 'incoming':
        return redirect(url_for('letters', type='incoming'))
    elif source == 'outgoing':
        return redirect(url_for('letters', type='outgoing'))
    elif source == 'letters':
        return redirect(url_for('letters'))
    else:  # Default to project view
        return redirect(url_for('view_project', project_id=project_id))

@app.route('/generate_ho_number')
@login_required
def generate_ho_number():
    # Get the last HO number from the database
    last_letter = Letter.query.filter(Letter.ho_number.isnot(None)).order_by(Letter.ho_number.desc()).first()
    if last_letter and last_letter.ho_number:
        try:
            next_number = int(last_letter.ho_number) + 1
        except ValueError:
            next_number = 1
    else:
        next_number = 1
    return jsonify({'ho_number': str(next_number)})

@app.route('/generate_project_number')
@login_required
def generate_project_number():
    # Get the last project number from the database
    last_letter = Letter.query.filter(Letter.project_number.isnot(None)).order_by(Letter.project_number.desc()).first()
    if last_letter and last_letter.project_number:
        try:
            next_number = int(last_letter.project_number) + 1
        except ValueError:
            next_number = 1
    else:
        next_number = 1
    return jsonify({'project_number': str(next_number)})

@app.route('/generate_numbers')
@login_required
def generate_numbers():
    # Get letter type from request
    is_incoming_param = request.args.get('is_incoming', '0')
    is_incoming = is_incoming_param == '1'
    
    # Get project ID from request
    project_id = request.args.get('project_id')
    
    print(f"Generating numbers for {'incoming' if is_incoming else 'outgoing'} letter for project_id {project_id}. Param value: {is_incoming_param}")
    
    # Get the last HO number from the database for the appropriate letter type
    last_ho_letter = Letter.query.filter(
        Letter.ho_number.isnot(None),
        Letter.is_incoming == is_incoming
    ).order_by(Letter.ho_number.desc()).first()
    
    if last_ho_letter and last_ho_letter.ho_number:
        try:
            next_ho_number = int(last_ho_letter.ho_number) + 1
            if next_ho_number > 9999:
                next_ho_number = 1
            print(f"Found last HO number: {last_ho_letter.ho_number}, next: {next_ho_number}")
        except ValueError:
            next_ho_number = 1
            print(f"Error converting HO number: {last_ho_letter.ho_number}, using 1")
    else:
        next_ho_number = 1
        print("No previous HO number found, using 1")

    # Get the last project number from the database for the specific project and letter type
    project_number_query = Letter.query.filter(
        Letter.project_number.isnot(None),
        Letter.is_incoming == is_incoming
    )
    
    # Add project filter if a project is selected
    if project_id and project_id.isdigit():
        project_number_query = project_number_query.filter(Letter.project_id == int(project_id))
    
    last_project_letter = project_number_query.order_by(Letter.project_number.desc()).first()
    
    if last_project_letter and last_project_letter.project_number:
        try:
            next_project_number = int(last_project_letter.project_number) + 1
            if next_project_number > 9999:
                next_project_number = 1
            print(f"Found last project number: {last_project_letter.project_number}, next: {next_project_number}")
        except ValueError:
            next_project_number = 1
            print(f"Error converting project number: {last_project_letter.project_number}, using 1")
    else:
        next_project_number = 1
        print("No previous project number found, using 1")
    
    # Format numbers with leading zeros
    ho_number = str(next_ho_number).zfill(4)
    project_number = str(next_project_number).zfill(4)
    
    # Check if letter number already exists
    if project_id and project_id.isdigit():
        year = datetime.now().strftime('%y')
        project = Project.query.get(int(project_id))
        if project:
            project_code = project.project_code
            letter_type_code = "IN" if is_incoming else "OU"
            letter_number = f"KEC/{project_code}/{letter_type_code}/{year}-{ho_number}-{project_number}"
            
            existing_letter = Letter.query.filter_by(letter_number=letter_number).first()
            if existing_letter:
                # If exists, increment HO number until unique
                ho_num = next_ho_number
                while existing_letter:
                    ho_num += 1
                    letter_number = f"KEC/{project_code}/{letter_type_code}/{year}-{str(ho_num).zfill(4)}-{project_number}"
                    existing_letter = Letter.query.filter_by(letter_number=letter_number).first()
                ho_number = str(ho_num).zfill(4)

    response_data = {
        'ho_number': ho_number,
        'project_number': project_number
    }
    
    print(f"Returning numbers: {response_data}")
    return jsonify(response_data)

# User Management API Routes for Admin
@app.route('/api/users', methods=['GET'])
@login_required
def get_users():
    # Check if user is a head office admin
    if not (current_user.is_admin and current_user.is_head_office):
        return jsonify({'error': 'Only Head Office administrators can manage users'}), 403
        
    users = User.query.all()
    user_list = []
    
    for user in users:
        user_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_admin': user.is_admin,
            'is_active': user.is_active,
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M')
        }
        user_list.append(user_data)
    
    return jsonify({'users': user_list})

@app.route('/api/users/<int:user_id>', methods=['GET'])
@login_required
def get_user(user_id):
    # Check if user is a head office admin
    if not (current_user.is_admin and current_user.is_head_office):
        return jsonify({'error': 'Only Head Office administrators can manage users'}), 403
        
    user = User.query.get_or_404(user_id)
    
    user_data = {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'is_admin': user.is_admin,
        'is_active': user.is_active,
        'created_at': user.created_at.strftime('%Y-%m-%d %H:%M')
    }
    
    return jsonify({'user': user_data})

@app.route('/api/users', methods=['POST'])
@login_required
def create_user():
    # Check if user is a head office admin
    if not (current_user.is_admin and current_user.is_head_office):
        return jsonify({'error': 'Only Head Office administrators can manage users'}), 403
        
    data = request.json
    
    # Validate input
    if not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({'success': False, 'message': 'Username, email, and password are required'}), 400
    
    # Check if username or email already exists
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'success': False, 'message': 'Username already exists'}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'success': False, 'message': 'Email already exists'}), 400
    
    # Validate password length
    if len(data['password']) < 8:
        return jsonify({'success': False, 'message': 'Password must be at least 8 characters long'}), 400
    
    # Get site_id from project if needed
    site_id = None
    if data.get('project_id'):
        project = Project.query.get(data['project_id'])
        if project:
            site_id = project.site_id
    
    # Create new user
    user = User(
        username=data['username'],
        email=data['email'],
        is_admin=bool(data.get('is_admin')),
        is_active=bool(data.get('is_active', True)),
        site_id=site_id)
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': 'User created successfully',
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_admin': user.is_admin,
            'is_active': user.is_active,
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M')
        }
    })

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
def update_user(user_id):
    # Check if user is a head office admin
    if not (current_user.is_admin and current_user.is_head_office):
        return jsonify({'error': 'Only Head Office administrators can manage users'}), 403
        
    user = User.query.get_or_404(user_id)
    data = request.json
    
    try:
        if 'username' in data:
            # Check if username already exists for another user
            existing = User.query.filter(User.username == data['username'], User.id != user_id).first()
            if existing:
                return jsonify({'error': 'Username already taken'}), 400
            user.username = data['username']
            
        if 'email' in data:
            # Check if email already exists for another user
            existing = User.query.filter(User.email == data['email'], User.id != user_id).first()
            if existing:
                return jsonify({'error': 'Email already exists'}), 400
            user.email = data['email']
            
        if 'is_admin' in data:
            # Only let head office make other users admins
            if current_user.is_head_office:
                user.is_admin = bool(data['is_admin'])
                
        if 'is_active' in data:
            user.is_active = bool(data['is_active'])
            
        if 'password' in data and data['password']:
            user.set_password(data['password'])
            
        if 'project_id' in data:
            # Get site_id from project
            project = Project.query.get(data['project_id'])
            if project:
                user.site_id = project.site_id
                
        db.session.commit()
        return jsonify({'message': 'User updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    # Check if user is a head office admin
    if not (current_user.is_admin and current_user.is_head_office):
        return jsonify({'error': 'Only Head Office administrators can manage users'}), 403
        
    user = User.query.get_or_404(user_id)
    
    # Prevent self-deletion
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot delete your own account'}), 400
        
    try:
        db.session.delete(user)
        db.session.commit()
        return jsonify({'message': 'User deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/notifications/settings', methods=['GET', 'POST'])
@login_required
def notification_settings():
    if request.method == 'POST':
        data = request.json
        
        # Update global settings
        current_user.email_notifications = data.get('email_global', False)
        current_user.browser_notifications = data.get('browser_global', False)
        current_user.email_frequency = data.get('email_frequency', 'immediate')
        
        # Create a JSON string for detailed notification settings
        settings = {
            'letter_created': {
                'email': data.get('letter_created_email', False),
                'browser': data.get('letter_created_browser', False)
            },
            'letter_updated': {
                'email': data.get('letter_updated_email', False),
                'browser': data.get('letter_updated_browser', False)
            },
            'letter_due': {
                'email': data.get('letter_due_email', False),
                'browser': data.get('letter_due_browser', False)
            },
            'project_created': {
                'email': data.get('project_created_email', False),
                'browser': data.get('project_created_browser', False)
            },
            'project_updated': {
                'email': data.get('project_updated_email', False),
                'browser': data.get('project_updated_browser', False)
            },
            'mentions': {
                'email': data.get('mentions_email', False),
                'browser': data.get('mentions_browser', False)
            }
        }
        
        current_user.notification_settings = json.dumps(settings)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Notification settings saved successfully'})
    else:
        # Get notification settings
        settings_json = current_user.notification_settings or '{}'
        settings = json.loads(settings_json)
        
        # Return as JSON
        return jsonify({
            'email_global': current_user.email_notifications,
            'browser_global': current_user.browser_notifications,
            'email_frequency': current_user.email_frequency,
            'settings': settings
        })
        
@app.route('/api/notifications', methods=['GET'])
@login_required
def get_notifications():
    # Get user notifications
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(10).all()
    
    result = []
    for notification in notifications:
        result.append({
            'id': notification.id,
            'title': notification.title,
            'text': notification.message,
            'time': notification.created_at.strftime('%Y-%m-%d %H:%M'),
            'timeAgo': get_time_ago(notification.created_at),
            'icon': notification.icon,
            'iconColor': notification.icon_color,
            'link': notification.link,
            'read': notification.read
        })
    
    return jsonify({
        'notifications': result,
        'unreadCount': Notification.query.filter_by(user_id=current_user.id, read=False).count()
    })

@app.route('/api/notifications/mark-read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    
    # Ensure the notification belongs to the current user
    if notification.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Notification not found'}), 404
    
    notification.read = True
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    # Mark all notifications for the current user as read
    notifications = Notification.query.filter_by(user_id=current_user.id, read=False).all()
    for notification in notifications:
        notification.read = True
    
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/notifications/clear-all', methods=['POST'])
@login_required
def clear_all_notifications():
    # Delete all notifications for the current user
    Notification.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'All notifications cleared successfully'})

@app.route('/api/database/backup', methods=['GET', 'POST'])
@login_required
def backup_database():
    # Check if user is a head office admin
    if not (current_user.is_admin and current_user.is_head_office):
        return jsonify({'success': False, 'error': 'Only Head Office administrators can perform database operations'}), 403
        
    try:
        # Create backups directory if it doesn't exist
        backup_dir = os.path.join(app.root_path, 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        # Generate backup file name with date and time
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        
        # Extract database path - handle both relative and absolute paths
        if db_uri.startswith('sqlite:///'):
            if db_uri[10:].startswith('/'):
                # Absolute path
                db_path = db_uri[10:]
            else:
                # Relative path
                db_path = os.path.join(app.root_path, db_uri[10:])
        else:
            return jsonify({'success': False, 'message': 'Only SQLite databases are supported for backup'}), 400
        
        if not os.path.exists(db_path):
            return jsonify({'success': False, 'message': f'Database file not found at path: {db_path}'}), 500
            
        # Create backup filename
        db_name = os.path.basename(db_path)
        backup_filename = f'{db_name}_{timestamp}.db'
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Check if this exact backup already exists (to prevent duplicates)
        if os.path.exists(backup_path):
            app.logger.warning(f"Backup file already exists: {backup_filename}")
            return jsonify({
                'success': True,
                'message': 'Backup already exists',
                'filename': backup_filename,
                'timestamp': timestamp,
                'download_url': url_for('download_backup', filename=backup_filename)
            })
        
        # Copy the current database file to the backup directory
        shutil.copy2(db_path, backup_path)
        
        # Log the backup creation
        app.logger.info(f"Created backup: {backup_filename}")
        
        # Create a notification about the backup - use a function that checks for duplicates
        try:
            create_notification(
                title="Database Backup Created",
                message=f"A database backup was created by {current_user.username}",
                icon="fa-database",
                icon_color="bg-success"
            )
        except Exception as e:
            app.logger.error(f"Error creating notification: {str(e)}")
        
        # Create a response with success message
        return jsonify({
            'success': True,
            'message': 'Database backup created successfully',
            'filename': backup_filename,
            'timestamp': timestamp,
            'download_url': url_for('download_backup', filename=backup_filename)
        })
    except Exception as e:
        app.logger.error(f"Error creating backup: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/database/backups', methods=['GET'])
@login_required
def list_backups():
    # Check if user is a head office admin
    if not (current_user.is_admin and current_user.is_head_office):
        return jsonify({'success': False, 'error': 'Only Head Office administrators can access database backups'}), 403
        
    try:
        # Create backups directory if it doesn't exist
        backup_dir = os.path.join(app.root_path, 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        # Get absolute backups directory path
        abs_backup_dir = os.path.abspath(backup_dir)
        app.logger.info(f"Listing backups from directory: {abs_backup_dir}")
        
        # Simple dictionary approach to ensure uniqueness by filename
        backup_dict = {}
        
        for filename in os.listdir(abs_backup_dir):
            if not filename.endswith('.db'):
                continue
                
            abs_path = os.path.join(abs_backup_dir, filename)
            
            # Only add if it's a file and we haven't seen this filename before
            if os.path.isfile(abs_path) and filename not in backup_dict:
                stat = os.stat(abs_path)
                backup_dict[filename] = {
                    'filename': filename,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'timestamp': stat.st_mtime,
                    'download_url': url_for('download_backup', filename=filename)
                }
                app.logger.info(f"Added backup file: {filename}")
            elif filename in backup_dict:
                app.logger.warning(f"Skipping duplicate filename: {filename}")
        
        # Convert the dictionary to a list and sort by timestamp
        backup_files = list(backup_dict.values())
        backup_files.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        
        # Remove timestamp field as it's only needed for sorting
        for backup in backup_files:
            backup.pop('timestamp', None)
        
        app.logger.info(f"Returning {len(backup_files)} unique backup files")
        
        return jsonify({
            'success': True, 
            'backups': backup_files
        })
    except Exception as e:
        app.logger.error(f"Error listing backups: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/backups/<filename>', methods=['GET'])
@login_required
def download_backup(filename):
    # Check if user is a head office admin
    if not (current_user.is_admin and current_user.is_head_office):
        flash('Only Head Office administrators can download database backups.', 'error')
        return redirect(url_for('index'))
    
    # Validate filename to prevent directory traversal
    if '..' in filename or filename.startswith('/'):
        flash('Invalid backup filename.', 'error')
        return redirect(url_for('index'))
        
    # Ensure file has .db extension
    if not filename.endswith('.db'):
        flash('Invalid backup file format.', 'error')
        return redirect(url_for('index'))
        
    try:
        backup_dir = os.path.join(app.root_path, 'backups')
        file_path = os.path.join(backup_dir, filename)
        
        # Check if file exists
        if not os.path.exists(file_path):
            flash('Backup file not found.', 'error')
            return redirect(url_for('index'))
            
        return send_from_directory(backup_dir, filename, as_attachment=True)
    except Exception as e:
        flash(f'Error downloading backup: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/api/database/restore', methods=['POST'])
@login_required
def restore_database():
    # Check if user is a head office admin
    if not (current_user.is_admin and current_user.is_head_office):
        return jsonify({'success': False, 'error': 'Only Head Office administrators can restore the database'}), 403
        
    try:
        # Check if a file was uploaded
        if 'backup_file' not in request.files:
            return jsonify({'success': False, 'message': 'No backup file provided'}), 400
        
        file = request.files['backup_file']
        
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        # Validate file is a SQLite database
        if not file.filename.endswith('.db'):
            return jsonify({'success': False, 'message': 'Invalid file format. Only .db files are supported'}), 400
        
        # Create a temporary file to save the uploaded backup
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            temp_path = temp.name
            file.save(temp_path)
            
            # Verify it's a valid SQLite database
            import sqlite3
            try:
                conn = sqlite3.connect(temp_path)
                # Check if it has the required tables
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                required_tables = ['users', 'projects', 'letters']
                for table in required_tables:
                    if table not in tables:
                        os.unlink(temp_path)
                        return jsonify({'success': False, 'message': f'Invalid backup file. Missing {table} table'}), 400
                
                conn.close()
            except sqlite3.Error as e:
                os.unlink(temp_path)
                return jsonify({'success': False, 'message': f'Invalid SQLite database file: {str(e)}'}), 400
            
            # Get the path to the current database file
            db_uri = app.config['SQLALCHEMY_DATABASE_URI']
            if db_uri.startswith('sqlite:///'):
                if db_uri[10:].startswith('/'):
                    # Absolute path
                    db_path = db_uri[10:]
                else:
                    # Relative path
                    db_path = os.path.join(app.root_path, db_uri[10:])
                
                # Create a backup of the current database
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                pre_restore_backup = f"pre_restore_backup_{timestamp}.db"
                backup_path = os.path.join(app.root_path, 'backups')
                os.makedirs(backup_path, exist_ok=True)
                
                # Make a backup before restoration
                shutil.copy2(db_path, os.path.join(backup_path, pre_restore_backup))
                
                # Close all database connections before replacing the file
                db.session.close_all()
                
                # Replace the current database with the uploaded backup
                shutil.copy2(temp_path, db_path)
                
                # Clean up the temp file
                os.unlink(temp_path)
                
                # Create a notification about the restore
                create_notification(
                    title="Database Restored",
                    message=f"The database was restored from a backup file by {current_user.username}",
                    icon="fa-database",
                    icon_color="bg-warning"
                )
                
                return jsonify({
                    'success': True, 
                    'message': 'Database restored successfully. Please restart the application for changes to take effect.'
                })
            else:
                os.unlink(temp_path)
                return jsonify({'success': False, 'message': 'Only SQLite database restores are supported'}), 400
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error restoring database: {str(e)}'}), 500

@app.route('/api/database/restore-from-backup', methods=['POST'])
@login_required
def restore_from_existing_backup():
    # Check if user is a head office admin
    if not (current_user.is_admin and current_user.is_head_office):
        return jsonify({'success': False, 'error': 'Only Head Office administrators can perform database operations'}), 403
    
    # Get filename from request
    data = request.get_json()
    if not data or 'filename' not in data:
        return jsonify({'success': False, 'error': 'Filename is required'}), 400
    
    filename = data['filename']
    
    # Validate filename (basic security check to prevent path traversal)
    if '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({'success': False, 'error': 'Invalid filename'}), 400
    
    # Ensure the file exists in the backups directory
    backups_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')
    backup_path = os.path.join(backups_dir, filename)
    
    if not os.path.exists(backup_path):
        return jsonify({'success': False, 'error': f'Backup file not found: {filename}'}), 404
    
    try:
        # Get the current database path
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        if db_uri.startswith('sqlite:///'):
            db_path = db_uri[10:]  # Remove 'sqlite:///'
            if not os.path.isabs(db_path):
                # If it's a relative path, make it absolute
                db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)
        else:
            return jsonify({'success': False, 'error': 'Only SQLite databases are supported for backup/restore'}), 400
        
        # Create a backup of the current database before restoring
        backup_filename = f"pre_restore_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        current_backup_path = os.path.join(backups_dir, backup_filename)
        
        os.makedirs(os.path.dirname(current_backup_path), exist_ok=True)
        shutil.copy2(db_path, current_backup_path)
        
        # Close all database connections
        db.session.close()
        db.engine.dispose()
        
        # Replace the current database with the backup
        shutil.copy2(backup_path, db_path)
        
        # Add a notification
        notification_text = f"Database restored from backup: {filename}"
        note = Notification(text=notification_text, user_id=current_user.id, is_system=True)
        db.session.add(note)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Database restored successfully. The application will need to be restarted for changes to take effect.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def get_time_ago(timestamp):
    """Helper function to format timestamp as time ago"""
    now = datetime.now()
    diff = now - timestamp
    
    if diff.days > 0:
        if diff.days == 1:
            return "1 day ago"
        elif diff.days < 7:
            return f"{diff.days} days ago"
        elif diff.days < 30:
            weeks = diff.days // 7
            return f"{weeks} week{'s' if weeks > 1 else ''} ago"
        elif diff.days < 365:
            months = diff.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        else:
            years = diff.days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
    else:
        if diff.seconds < 60:
            return "just now"
        elif diff.seconds < 3600:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"

# Site Management Routes
@app.route('/sites')
@login_required
@admin_required
def sites():
    # This route is removed - kept only for function signature to avoid breaking existing references
    return redirect(url_for('index'))

@app.route('/create_site', methods=['GET', 'POST'])
@login_required
@admin_required
def create_site():
    # This route is removed - kept only for function signature to avoid breaking existing references
    return redirect(url_for('index'))

@app.route('/edit_site/<int:site_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_site(site_id):
    # This route is removed - kept only for function signature to avoid breaking existing references
    return redirect(url_for('index'))

@app.route('/delete_site/<int:site_id>', methods=['POST'])
@login_required
@admin_required
def delete_site(site_id):
    # This route is removed - kept only for function signature to avoid breaking existing references
    return redirect(url_for('index'))

# Database Initialization Function
def initialize_database():
    db.create_all()
    
    # Check if 'Head Office' site exists, if not create it
    if not Site.query.filter_by(name='Head Office').first():
        head_office = Site(
            name='Head Office',
            code='HO',
            description='Main headquarters office with access to all sites data',
            address='Head Office Address'
        )
        db.session.add(head_office)
        db.session.commit()
        
        print("Created 'Head Office' site")
    
    # Create SGP site if not exists
    if not Site.query.filter_by(code='SGP').first():
        sgp_site = Site(
            name='SGP Site',
            code='SGP',
            description='SGP Project Site',
            address='SGP Site Address'
        )
        db.session.add(sgp_site)
        db.session.commit()
        print("Created 'SGP Site'")
    
    # Create admin user if not exists
    if not User.query.filter_by(username='admin').first():
        admin_user = User(
            username='admin',
            email='admin@example.com',
            is_admin=True,
            site_id=Site.query.filter_by(name='Head Office').first().id
        )
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        db.session.commit()
        
        print("Created default admin user")
    
    # Make sure SGP projects are associated with SGP site
    sgp_site = Site.query.filter_by(code='SGP').first()
    if sgp_site:
        sgp_projects = Project.query.filter(Project.project_code.startswith('SGP')).all()
        updated = False
        for project in sgp_projects:
            if project.site_id != sgp_site.id:
                project.site_id = sgp_site.id
                updated = True
                print(f"Updated project {project.project_code} to be associated with SGP site")
        
        if updated:
            db.session.commit()

# Use Flask's built-in way to run code before the first request
with app.app_context():
    initialize_database()

@app.route('/settings')
@login_required
def settings():
    # Get current site if not head office
    site_id = get_user_site_id()
    current_site = Site.query.get(site_id) if site_id else None
    
    # Get all sites for admin users
    sites = []
    if current_user.is_admin:
        sites = Site.query.all()
    
    # Get all projects for user dropdown
    projects = Project.query.all()
    
    return render_template('settings.html', sites=sites, current_site=current_site, projects=projects)

# Context processor to add common variables to all templates
@app.context_processor
def inject_common_data():
    """Add common variables to all templates"""
    # Add all sites and projects to every template context for dropdowns
    sites = Site.query.all()
    all_projects = Project.query.all()
    
    # Get unread notification count for current user
    notification_count = 0
    if current_user.is_authenticated:
        notification_count = Notification.query.filter_by(user_id=current_user.id, read=False).count()
    
    return {
        'sites': sites, 
        'projects': all_projects,
        'notification_count': notification_count
    }

@app.route('/database-utilities')
@login_required
def database_utilities():
    # Check if user is a head office admin
    if not (current_user.is_admin and current_user.is_head_office):
        flash('Only Head Office administrators can access database utilities.', 'error')
        return redirect(url_for('index'))
        
    return render_template('database_utilities.html')

@app.route('/help')
@login_required
def help_page():
    """Display the help documentation for users"""
    return render_template('help.html')

@app.route('/api/database/delete-backup', methods=['POST'])
@login_required
def delete_backup():
    # Check if user is a head office admin
    if not (current_user.is_admin and current_user.is_head_office):
        return jsonify({'success': False, 'error': 'Only Head Office administrators can delete database backups'}), 403
        
    # Get filename from request
    data = request.get_json()
    if not data or 'filename' not in data:
        return jsonify({'success': False, 'error': 'Filename is required'}), 400
    
    filename = data['filename']
    
    # Validate filename (basic security check to prevent path traversal)
    if '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({'success': False, 'error': 'Invalid filename'}), 400
    
    # Ensure the file exists in the backups directory
    backups_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')
    backup_path = os.path.join(backups_dir, filename)
    
    if not os.path.exists(backup_path):
        return jsonify({'success': False, 'error': f'Backup file not found: {filename}'}), 404
    
    try:
        # Delete the backup file
        os.remove(backup_path)
        app.logger.info(f"Deleted backup: {filename}")
        
        # Create a notification about the deletion
        create_notification(
            title="Database Backup Deleted",
            message=f"A database backup was deleted by {current_user.username}",
            icon="fa-trash",
            icon_color="bg-danger"
        )
        
        return jsonify({'success': True, 'message': f'Backup deleted successfully: {filename}'})
    except Exception as e:
        app.logger.error(f"Error deleting backup: {str(e)}")
        return jsonify({'success': False, 'message': f'Error deleting backup: {str(e)}'}), 500

@app.route('/api/database/debug-backups', methods=['GET'])
@login_required
def debug_backups():
    # Check if user is a head office admin
    if not (current_user.is_admin and current_user.is_head_office):
        return jsonify({'success': False, 'error': 'Only Head Office administrators can access this debug endpoint'}), 403
        
    try:
        # Get the backups directory
        backup_dir = os.path.join(app.root_path, 'backups')
        if not os.path.exists(backup_dir):
            return jsonify({'success': True, 'message': 'Backups directory does not exist', 'files': []})
        
        # List all files in the directory with details
        files = []
        for filename in os.listdir(backup_dir):
            file_path = os.path.join(backup_dir, filename)
            file_info = {
                'filename': filename,
                'size': os.path.getsize(file_path),
                'modified': datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S'),
                'is_file': os.path.isfile(file_path),
                'is_db': filename.endswith('.db'),
                'path': file_path
            }
            files.append(file_info)
            
        # Also check if there's a possible hidden duplicate
        raw_dir_listing = str(os.listdir(backup_dir))
        
        return jsonify({
            'success': True,
            'backup_dir': backup_dir,
            'files': files,
            'raw_listing': raw_dir_listing
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/settings', methods=['GET'])
@login_required
def get_settings():
    # Check if user is a head office admin
    if not (current_user.is_admin and current_user.is_head_office):
        return jsonify({'success': False, 'error': 'Only Head Office administrators can access settings'}), 403
    
    try:
        # Get all settings or specific settings by keys
        keys = request.args.get('keys', None)
        if keys:
            keys = keys.split(',')
            settings = Setting.query.filter(Setting.key.in_(keys)).all()
        else:
            settings = Setting.query.all()
        
        settings_dict = {}
        for setting in settings:
            # Convert value to appropriate type
            value = setting.value
            if value.lower() in ('true', 'false'):
                value = value.lower() == 'true'
            elif value.isdigit():
                value = int(value)
            
            settings_dict[setting.key] = {
                'value': value,
                'description': setting.description,
                'updated_at': setting.updated_at.strftime('%Y-%m-%d %H:%M:%S') if setting.updated_at else None
            }
        
        return jsonify({'success': True, 'settings': settings_dict})
    except Exception as e:
        app.logger.error(f"Error getting settings: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/settings', methods=['POST'])
@login_required
def update_settings():
    # Check if user is a head office admin
    if not (current_user.is_admin and current_user.is_head_office):
        return jsonify({'success': False, 'error': 'Only Head Office administrators can update settings'}), 403
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No settings provided'}), 400
        
        updated_settings = {}
        for key, value in data.items():
            # Update the setting
            Setting.set(key, value)
            updated_settings[key] = value
        
        app.logger.info(f"Updated settings: {updated_settings}")
        
        # Create a notification
        create_notification(
            title="System Settings Updated",
            message=f"System settings were updated by {current_user.username}",
            icon="fa-cog",
            icon_color="bg-primary"
        )
        
        return jsonify({'success': True, 'message': 'Settings updated successfully', 'updated': updated_settings})
    except Exception as e:
        app.logger.error(f"Error updating settings: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Main application run
if __name__ == '__main__':
    # Configure server to handle larger file uploads
    from werkzeug.serving import run_simple
    app.jinja_env.auto_reload = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    run_simple('0.0.0.0', 5000, app, use_reloader=True, use_debugger=True)
    # app.run(debug=True, host='0.0.0.0', port=5000) 