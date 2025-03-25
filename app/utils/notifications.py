from datetime import datetime
from flask import current_app
from flask_login import current_user
from app import db
from app.models.notification import Notification

def create_notification(title, message, user_id=None, icon="fa-bell", icon_color="bg-primary", link=None):
    """
    Create a notification for a user or for all users
    If user_id is None, creates notification for the current user
    """
    try:
        if user_id is None and current_user.is_authenticated:
            user_id = current_user.id
        
        if not user_id:
            current_app.logger.warning("No user specified for notification")
            return None
            
        # Check for duplicates to prevent spam
        existing = Notification.query.filter_by(
            user_id=user_id,
            title=title,
            message=message,
            read=False
        ).first()
        
        if existing:
            current_app.logger.info(f"Duplicate notification blocked: {title}")
            return existing
            
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            icon=icon,
            icon_color=icon_color,
            link=link,
            created_at=datetime.now()
        )
        
        db.session.add(notification)
        db.session.commit()
        current_app.logger.info(f"Notification created for user {user_id}: {title}")
        return notification
        
    except Exception as e:
        current_app.logger.error(f"Error creating notification: {str(e)}")
        db.session.rollback()
        return None

def create_notification_for_all_admins(title, message, icon="fa-bell", icon_color="bg-primary", link=None):
    """Create a notification for all admin users"""
    from app.models.user import User
    
    try:
        # Get all active admin users (both head office and project admins)
        admins = User.query.filter_by(is_admin=True, is_active=True).all()
        notifications = []
        
        for admin in admins:
            notification = create_notification(
                title=title,
                message=message,
                user_id=admin.id,
                icon=icon,
                icon_color=icon_color,
                link=link
            )
            if notification:
                notifications.append(notification)
                
        return notifications
    except Exception as e:
        current_app.logger.error(f"Error creating notifications for admins: {str(e)}")
        return []

def create_notification_for_project_users(title, message, project_id, icon="fa-bell", icon_color="bg-primary", link=None):
    """Create a notification for all users associated with a specific project"""
    from app.models.user import User
    
    try:
        # Get all active users associated with the project (including admins)
        project_users = User.query.filter_by(project_id=project_id, is_active=True).all()
        notifications = []
        
        for user in project_users:
            notification = create_notification(
                title=title,
                message=message,
                user_id=user.id,
                icon=icon,
                icon_color=icon_color,
                link=link
            )
            if notification:
                notifications.append(notification)
                
        return notifications
    except Exception as e:
        current_app.logger.error(f"Error creating notifications for project users: {str(e)}")
        return []

def create_notification_for_all_users(title, message, icon="fa-bell", icon_color="bg-primary", link=None):
    """Create a notification for all active users in the system"""
    from app.models.user import User
    
    try:
        # Get all active users
        users = User.query.filter_by(is_active=True).all()
        notifications = []
        
        for user in users:
            notification = create_notification(
                title=title,
                message=message,
                user_id=user.id,
                icon=icon,
                icon_color=icon_color,
                link=link
            )
            if notification:
                notifications.append(notification)
                
        return notifications
    except Exception as e:
        current_app.logger.error(f"Error creating notifications for all users: {str(e)}")
        return [] 