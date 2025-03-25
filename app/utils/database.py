import os
import shutil
from datetime import datetime
from flask import current_app
from app import db, scheduler
from app.models.setting import Setting
from app.utils.notifications import create_notification

def auto_backup_database():
    """Create an automatic database backup"""
    # First check if auto-backup is enabled
    if not Setting.get('auto_backup_enabled', False):
        current_app.logger.info("Auto backup is disabled, skipping scheduled backup")
        return
        
    current_app.logger.info("Running scheduled auto-backup")
    try:
        # Get the current database path
        db_uri = current_app.config['SQLALCHEMY_DATABASE_URI']
        if not db_uri.startswith('sqlite:///'):
            current_app.logger.error("Auto-backup only supports SQLite databases")
            return
            
        if db_uri[10:].startswith('/'):
            # Absolute path
            db_path = db_uri[10:]
        else:
            # Relative path
            db_path = os.path.join(current_app.root_path, db_uri[10:])
        
        if not os.path.exists(db_path):
            current_app.logger.error(f"Database file not found at path: {db_path}")
            return
            
        # Create backup filename
        db_name = os.path.basename(db_path)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'auto_{db_name}_{timestamp}.db'
        
        # Create backups directory if it doesn't exist
        backup_dir = os.path.join(current_app.root_path, 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Copy the current database file to the backup directory
        shutil.copy2(db_path, backup_path)
        
        current_app.logger.info(f"Auto backup created: {backup_filename}")
        
        # Create a notification about the auto-backup
        try:
            create_notification(
                title="Auto Database Backup Created",
                message="A scheduled automatic database backup was created",
                icon="fa-database",
                icon_color="bg-info"
            )
        except Exception as e:
            current_app.logger.error(f"Error creating notification for auto-backup: {str(e)}")
            
        # Optional: Cleanup old auto-backups
        cleanup_old_auto_backups()
        
    except Exception as e:
        current_app.logger.error(f"Error during auto-backup: {str(e)}")

def cleanup_old_auto_backups():
    """Remove old auto-backups, keeping only recent ones"""
    try:
        max_backups = int(Setting.get('auto_backup_keep_count', 5))
        backup_dir = os.path.join(current_app.root_path, 'backups')
        
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
                    current_app.logger.info(f"Removed old auto-backup: {os.path.basename(file_path)}")
                except Exception as e:
                    current_app.logger.error(f"Error removing old auto-backup: {str(e)}")
    except Exception as e:
        current_app.logger.error(f"Error cleaning up old auto-backups: {str(e)}")

def allowed_file(filename):
    """Check if the uploaded file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def create_tables():
    """Create all database tables if they don't exist"""
    from app import db
    db.create_all()
    print("Database tables created")

def init_default_settings():
    """Initialize default settings if they don't exist"""
    from app import db
    from app.models.setting import Setting
    
    try:
        # Create tables first in case they don't exist
        create_tables()
        
        # Ensure Head Office project exists
        ensure_head_office_project()
        
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
                print(f"Created default setting: {key}={value}")
        
        db.session.commit()
    except Exception as e:
        print(f"Error initializing settings: {str(e)}")
        db.session.rollback()

def ensure_head_office_project():
    """Ensure Head Office project exists"""
    from app.models.project import Project
    from app.models.user import User
    from app import db
    
    # Check if Head Office project exists
    head_office = Project.query.filter_by(is_head_office=True).first()
    if not head_office:
        head_office = Project(
            name="Head Office",
            project_code="HO1001",
            description="Head Office Administration",
            is_head_office=True,
            address="KEC Main Office"
        )
        db.session.add(head_office)
        db.session.commit()
        print("Created default Head Office project")
    
    # Ensure admin user exists
    admin_user = User.query.filter_by(username="admin").first()
    if not admin_user:
        admin_user = User(
            username="admin",
            email="admin@example.com",
            is_admin=True,
            project_id=head_office.id
        )
        admin_user.set_password("admin123")
        db.session.add(admin_user)
        db.session.commit()
        print("Created default admin user (username: admin, password: admin123)")
    
    return head_office

# Schedule weekly backups - every Monday at 1:00 AM
@scheduler.task('cron', id='auto_backup', day_of_week=0, hour=1, minute=0)
def scheduled_backup():
    auto_backup_database() 