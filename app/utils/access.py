from functools import wraps
from flask import session, flash, redirect, url_for
from flask_login import current_user
from app.models.project import Project
from app.models.letter import Letter

def admin_required(f):
    """Decorator to restrict access to admin users only (project_admin or head_office_admin)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('You do not have permission to access this feature.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def head_office_required(f):
    """Decorator to restrict access to head office users only (both admin and regular)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_head_office:
            flash('Only Head Office users can access this feature.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def head_office_admin_required(f):
    """Decorator to restrict access to head office admin users only"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_head_office_admin:
            flash('Only Head Office administrators can access this feature.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def project_admin_required(f):
    """Decorator to restrict access to project admin users only"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_project_admin:
            flash('Only Project administrators can access this feature.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def crud_permission_required(f):
    """Decorator to restrict access to users who can perform CRUD operations (project_admin or head_office_admin)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not (current_user.is_head_office_admin or current_user.is_project_admin):
            flash('You do not have permission to modify data.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def get_user_project_id():
    """Get the project ID from the session or current user"""
    project_id = session.get('project_id')
    if not project_id and current_user.is_authenticated:
        project_id = current_user.project_id
    return project_id

def project_query_filter(query, model):
    """Filter query by project unless user is from Head Office"""
    project_id = get_user_project_id()
    
    if current_user.is_authenticated and current_user.is_head_office:
        return query  # Head Office users can see all data
    
    if model == Letter:
        if project_id:
            return query.filter(Letter.project_id == project_id)
        # If no project found, return no results
        return query.filter(Letter.id < 0)
    
    if hasattr(model, 'project_id'):
        return query.filter(model.project_id == project_id)
    
    return query

def can_modify_project(project_id):
    """Check if user can modify a specific project"""
    if current_user.is_head_office_admin:
        return True  # Head office admin can modify any project
    
    if current_user.is_project_admin and current_user.project_id == project_id:
        return True  # Project admin can modify their own project
    
    return False

def can_modify_letter(letter):
    """Check if user can modify a specific letter"""
    if current_user.is_head_office_admin:
        return True  # Head office admin can modify any letter
    
    if current_user.is_project_admin and letter.project_id == current_user.project_id:
        return True  # Project admin can modify letters in their project
    
    return False 