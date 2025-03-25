import os
from app import db, create_app
from app.models.user import User
from app.models.project import Project
from app.utils.database import create_tables

def reset_database():
    """Reset and initialize the database with essential data"""
    # Create app context
    app = create_app('production')
    with app.app_context():
        # Drop all tables
        db.drop_all()
        print("All tables dropped")
        
        # Create tables
        db.create_all()
        print("Tables recreated")
        
        # Create Head Office project
        head_office = Project(
            name="Head Office",
            project_code="HO",  # Default project code is set to "HO"
            description="Head Office Administration",
            is_head_office=True,
            address="KEC Main Office"
        )
        db.session.add(head_office)
        db.session.flush()  # Get ID without committing
        print(f"Created Head Office project with code: {head_office.project_code}")
        
        # Create admin user
        admin = User(
            username="admin",
            email="admin@example.com",
            is_admin=True,
            project_id=head_office.id
        )
        admin.set_password("admin123")
        db.session.add(admin)
        print(f"Created admin user (username: admin, password: admin123)")
        
        # Commit changes
        db.session.commit()
        print("Database initialization complete")

if __name__ == "__main__":
    # Backup the database first if it exists
    if os.path.exists('letter_registry.db'):
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'backup_before_init_{timestamp}.db'
        backup_dir = 'backups'
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Create a copy of the database
        with open('letter_registry.db', 'rb') as src, open(backup_path, 'wb') as dst:
            dst.write(src.read())
        
        print(f"Database backup created at {backup_path}")
    
    # Run database initialization without confirmation (for automated deployment)
    reset_database() 