from flask import jsonify, request
from flask_login import login_required, current_user
from app import db
from app.blueprints.api import api_bp
from app.models.user import User
from app.utils.access import head_office_admin_required
from app.models.project import Project
from datetime import datetime

@api_bp.route('/users', methods=['GET'])
@login_required
@head_office_admin_required
def get_users():
    users = User.query.all()
    user_list = []
    
    for user in users:
        user_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_active': user.is_active,
            'is_admin': user.is_admin,
            'is_head_office': user.is_head_office,
            'project_id': user.project_id,
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M')
        }
        user_list.append(user_data)
    
    return jsonify({'success': True, 'users': user_list})

@api_bp.route('/users/<int:user_id>', methods=['GET'])
@login_required
@head_office_admin_required
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    
    user_data = {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'is_active': user.is_active,
        'is_admin': user.is_admin,
        'is_head_office': user.is_head_office,
        'project_id': user.project_id,
        'created_at': user.created_at.strftime('%Y-%m-%d %H:%M')
    }
    
    return jsonify({'success': True, 'user': user_data})

@api_bp.route('/users', methods=['POST'])
@login_required
@head_office_admin_required
def create_user():
    data = request.get_json()
    
    # Validate required fields
    if not data.get('username') or not data.get('email') or not data.get('password') or not data.get('project_id'):
        return jsonify({'success': False, 'message': 'Username, email, password, and project ID are required'}), 400
    
    # Check if username already exists
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'success': False, 'message': 'Username already exists'}), 400
    
    # Check if email already exists
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'success': False, 'message': 'Email already exists'}), 400
    
    # Validate project
    project = Project.query.get(data['project_id'])
    if not project:
        return jsonify({'success': False, 'message': 'Invalid project ID'}), 400
    
    try:
        # Determine role
        is_admin = data.get('is_admin', False)
        role = 'project_user'
        
        if project.is_head_office and is_admin:
            role = 'head_office_admin'
        elif project.is_head_office and not is_admin:
            role = 'head_office_user'
        elif not project.is_head_office and is_admin:
            role = 'project_admin'
        else:
            role = 'project_user'
            
        # Create new user
        new_user = User(
            username=data['username'],
            email=data['email'],
            is_admin=is_admin,
            role=role,
            is_active=data.get('is_active', True),
            project_id=data['project_id'],
            created_at=datetime.now()
        )
        
        new_user.set_password(data['password'])
        
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'User created successfully',
            'user_id': new_user.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error creating user: {str(e)}'}), 500

@api_bp.route('/users/<int:user_id>', methods=['PUT'])
@login_required
@head_office_admin_required
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    # Check if email exists and belongs to another user
    if data.get('email') and data['email'] != user.email:
        existing_user = User.query.filter_by(email=data['email']).first()
        if existing_user and existing_user.id != user.id:
            return jsonify({'error': 'Email already exists'}), 400
    
    # Update user fields
    if data.get('email'):
        user.email = data['email']
    
    # Project change requires role recalculation
    project_id_changed = False
    if data.get('project_id') and int(data['project_id']) != user.project_id:
        project = Project.query.get(data['project_id'])
        if not project:
            return jsonify({'error': 'Invalid project ID'}), 400
        user.project_id = int(data['project_id'])
        project_id_changed = True
    
    # Admin status change requires role recalculation
    admin_status_changed = False
    if 'is_admin' in data and data['is_admin'] != user.is_admin:
        user.is_admin = data['is_admin']
        admin_status_changed = True
    
    # Recalculate role if project or admin status changed
    if project_id_changed or admin_status_changed:
        project = Project.query.get(user.project_id)
        if project.is_head_office and user.is_admin:
            user.role = 'head_office_admin'
        elif project.is_head_office and not user.is_admin:
            user.role = 'head_office_user'
        elif not project.is_head_office and user.is_admin:
            user.role = 'project_admin'
        else:
            user.role = 'project_user'
    
    if 'is_active' in data:
        user.is_active = data['is_active']
    
    # Update password if provided
    if data.get('password'):
        user.set_password(data['password'])
    
    db.session.commit()
    
    return jsonify({
        'message': 'User updated successfully',
    })

@api_bp.route('/users/<int:user_id>', methods=['DELETE'])
@login_required
@head_office_admin_required
def delete_user(user_id):
    # Prevent deleting yourself
    if user_id == current_user.id:
        return jsonify({
            'success': False,
            'message': 'You cannot delete your own account'
        }), 400
    
    user = User.query.get_or_404(user_id)
    
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'User {user.username} deleted successfully'
    })

@api_bp.route('/projects', methods=['GET'])
@login_required
@head_office_admin_required
def get_projects():
    projects = Project.query.all()
    project_list = []
    
    for project in projects:
        project_data = {
            'id': project.id,
            'project_code': project.project_code,
            'name': project.name,
            'is_head_office': project.is_head_office
        }
        project_list.append(project_data)
    
    return jsonify({'success': True, 'projects': project_list}) 