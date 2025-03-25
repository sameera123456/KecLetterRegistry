from flask import render_template, flash, redirect, url_for, request, session, current_app, jsonify
from flask_login import login_required, current_user
from app import db
from app.blueprints.main import main_bp
from app.models.project import Project
from app.models.letter import Letter
from app.utils.access import get_user_project_id
from app.models.notification import Notification

@main_bp.route('/')
@login_required
def index():
    # Get statistics
    project_id = get_user_project_id()
    
    try:
        # Filter by project unless head office
        if current_user.is_head_office:
            total_projects = Project.query.count()
            total_letters = Letter.query.count()
            incoming_letters = Letter.query.filter_by(is_incoming=True).count()
            outgoing_letters = Letter.query.filter_by(is_incoming=False).count()
            recent_letters = Letter.query.order_by(Letter.created_at.desc()).limit(5).all()
        else:
            # Get project info
            current_project = Project.query.get(project_id)
            
            # Get statistics for this project
            if current_project:
                total_projects = 1
                letters_query = Letter.query.filter_by(project_id=current_project.id)
                total_letters = letters_query.count()
                incoming_letters = letters_query.filter_by(is_incoming=True).count()
                outgoing_letters = letters_query.filter_by(is_incoming=False).count()
                recent_letters = letters_query.order_by(Letter.created_at.desc()).limit(5).all()
            else:
                total_projects = 0
                total_letters = 0
                incoming_letters = 0
                outgoing_letters = 0
                recent_letters = []
    except Exception as e:
        current_app.logger.error(f"Error in index route: {str(e)}")
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
    
    # Get current project info
    current_project = Project.query.get(project_id) if project_id else None
    
    # Get projects for user dropdown in base template
    if current_user.is_head_office:
        all_projects = Project.query.all()
    else:
        all_projects = [current_project] if current_project else []
    
    return render_template('index.html', recent_letters=recent_letters, stats=stats, 
                          current_project=current_project, projects=all_projects)

@main_bp.route('/notifications')
@login_required
def notifications():
    """Display all notifications for the current user"""
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template('notifications.html', notifications=notifications)

@main_bp.route('/help')
@login_required
def help_page():
    return render_template('help.html') 