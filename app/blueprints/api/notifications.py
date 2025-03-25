from flask import jsonify, current_app
from flask_login import current_user, login_required
from app.models.notification import Notification
from app import db
from datetime import datetime
from . import api_bp

@api_bp.route('/notifications')
@login_required
def get_notifications():
    """Get notifications for the current user"""
    try:
        # Get notifications for current user, ordered by creation date descending
        notifications = Notification.query.filter_by(user_id=current_user.id)\
            .order_by(Notification.created_at.desc())\
            .limit(10)\
            .all()
        
        # Count unread notifications for current user
        unread_count = Notification.query.filter_by(user_id=current_user.id, read=False).count()
        
        # Format notifications for response
        formatted_notifications = [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'icon': n.icon,
            'icon_color': n.icon_color,
            'link': n.link,
            'read': n.read,
            'created_at': n.created_at.isoformat()
        } for n in notifications]
        
        return jsonify({
            'notifications': formatted_notifications,
            'unreadCount': unread_count
        })
    except Exception as e:
        current_app.logger.error(f'Error fetching notifications: {str(e)}')
        return jsonify({'error': 'Failed to fetch notifications'}), 500

@api_bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark a specific notification as read"""
    try:
        # Get notification and verify it belongs to current user
        notification = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first_or_404()
        
        notification.read = True
        db.session.commit()
        
        return jsonify({'message': 'Notification marked as read'})
    except Exception as e:
        current_app.logger.error(f'Error marking notification as read: {str(e)}')
        db.session.rollback()
        return jsonify({'error': 'Failed to mark notification as read'}), 500

@api_bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    """Mark all notifications as read for the current user"""
    try:
        # Update only notifications belonging to current user
        Notification.query.filter_by(user_id=current_user.id, read=False)\
            .update({Notification.read: True})
        db.session.commit()
        
        return jsonify({'message': 'All notifications marked as read'})
    except Exception as e:
        current_app.logger.error(f'Error marking all notifications as read: {str(e)}')
        db.session.rollback()
        return jsonify({'error': 'Failed to mark all notifications as read'}), 500

@api_bp.route('/notifications/clear-all', methods=['POST'])
@login_required
def clear_all_notifications():
    """Delete all notifications for the current user"""
    try:
        # Delete only notifications belonging to current user
        Notification.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        
        return jsonify({'message': 'All notifications cleared'})
    except Exception as e:
        current_app.logger.error(f'Error clearing notifications: {str(e)}')
        db.session.rollback()
        return jsonify({'error': 'Failed to clear notifications'}), 500

def format_time_ago(timestamp):
    """Format timestamp as relative time"""
    now = datetime.now()
    diff = now - timestamp
    
    seconds = diff.total_seconds()
    if seconds < 60:
        return 'Just now'
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f'{minutes}m ago'
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f'{hours}h ago'
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f'{days}d ago'
    else:
        return timestamp.strftime('%Y-%m-%d') 