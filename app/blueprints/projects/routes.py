from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.blueprints.projects import projects_bp
from app.models.project import Project
from app.models.letter import Letter
from app.utils.access import admin_required, get_user_project_id, project_query_filter, head_office_required

@projects_bp.route('/')
@login_required
def list_projects():
    # Filter projects by head office status
    if current_user.is_head_office:
        projects = Project.query.all()
    else:
        projects = Project.query.filter_by(id=current_user.project_id).all()
    
    return render_template('projects.html', projects=projects)

@projects_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_project():
    if request.method == 'POST':
        name = request.form.get('name')
        project_code = request.form.get('project_code')
        description = request.form.get('description')
        address = request.form.get('address')
        is_head_office = 'is_head_office' in request.form
        
        # Validate
        if not name or not project_code:
            flash('Project name and project code are required', 'error')
            return redirect(url_for('projects.create_project'))
        
        # Check for duplicate project code
        existing_project = Project.query.filter_by(project_code=project_code).first()
        if existing_project:
            flash('Project code already exists', 'error')
            return redirect(url_for('projects.create_project'))
        
        # Create project
        project = Project(
            name=name,
            project_code=project_code,
            description=description,
            address=address,
            is_head_office=is_head_office,
            created_by=current_user.id
        )
        
        db.session.add(project)
        db.session.commit()
        
        flash('Project created successfully', 'success')
        return redirect(url_for('projects.list_projects'))
    
    return render_template('create_project.html')

@projects_bp.route('/<int:project_id>')
@login_required
def view_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    # Check if user has access to this project
    if not current_user.is_head_office and project.id != current_user.project_id:
        flash('You do not have permission to view this project', 'error')
        return redirect(url_for('projects.list_projects'))
    
    # Get letters for this project
    letters = Letter.query.filter_by(project_id=project.id).all()
    
    # Calculate letter statistics
    total_letters = len(letters)
    incoming_letters = sum(1 for letter in letters if letter.is_incoming)
    outgoing_letters = total_letters - incoming_letters
    
    stats = {
        'total_letters': total_letters,
        'incoming_letters': incoming_letters,
        'outgoing_letters': outgoing_letters
    }
    
    return render_template('view_project.html', project=project, letters=letters, stats=stats)

@projects_bp.route('/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    # Check if user has access to this project
    if not current_user.is_head_office and project.id != current_user.project_id:
        flash('You do not have permission to edit this project', 'error')
        return redirect(url_for('projects.list_projects'))
    
    if request.method == 'POST':
        project.name = request.form.get('name')
        project.description = request.form.get('description')
        project.address = request.form.get('address')
        project.is_head_office = 'is_head_office' in request.form
        
        # Don't allow modifying the codes as they may be referenced elsewhere
        
        db.session.commit()
        flash('Project updated successfully', 'success')
        return redirect(url_for('projects.view_project', project_id=project.id))
    
    return render_template('edit_project.html', project=project)

@projects_bp.route('/<int:project_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    # Check if user has access to this project
    if not current_user.is_head_office and project.id != current_user.project_id:
        flash('You do not have permission to delete this project', 'error')
        return redirect(url_for('projects.list_projects'))
    
    # Check if project has letters
    if Letter.query.filter_by(project_id=project.id).count() > 0:
        flash('Cannot delete project with existing letters', 'error')
        return redirect(url_for('projects.view_project', project_id=project.id))
        
    # Check if users are assigned to this project
    if project.users.count() > 0:
        flash('Cannot delete project with assigned users', 'error')
        return redirect(url_for('projects.view_project', project_id=project.id))
    
    db.session.delete(project)
    db.session.commit()
    
    flash('Project deleted successfully', 'success')
    return redirect(url_for('projects.list_projects')) 