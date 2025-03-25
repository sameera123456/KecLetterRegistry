from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.blueprints.auth import auth_bp
from app.models.user import User
from app.models.project import Project

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        project_id = request.form.get('project_id')
        remember = request.form.get('remember', False)
        
        user = User.query.filter_by(username=username).first()
        
        if user is None or not user.check_password(password):
            flash('Invalid username or password', 'error')
            return redirect(url_for('auth.login'))
        
        # Check if the user belongs to the selected project or is a head office user
        if user.project_id and int(user.project_id) != int(project_id) and not user.is_head_office:
            flash('You do not have permission to log in from this project.', 'error')
            return redirect(url_for('auth.login'))
            
        # Store project_id in session
        session['project_id'] = project_id
        
        login_user(user, remember=remember)
        next_page = request.args.get('next')
        if not next_page or next_page.startswith('/'):
            next_page = url_for('main.index')
        
        return redirect(next_page)
    
    # Get projects for dropdown - head office first
    projects = Project.query.filter_by(is_head_office=True).all()
    
    # Add other projects
    other_projects = Project.query.filter_by(is_head_office=False).all()
    projects.extend(other_projects)
    
    return render_template('login.html', projects=projects)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        special_code = request.form.get('special_code')
        user_type = request.form.get('user_type', 'regular')
        project_id = request.form.get('project_id')
        
        # Check if admin registration
        is_admin = False
        if user_type == 'admin' and special_code == 'KEC0213ADMIN':
            is_admin = True
        elif user_type == 'regular' and special_code == 'KEC0213':
            is_admin = False
        else:
            flash(f'Invalid registration code for {user_type} user', 'error')
            return redirect(url_for('auth.register'))
        
        # Validate password match
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('auth.register'))
            
        # Validate password length
        if len(password) < 8:
            flash('Password must be at least 8 characters long', 'error')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('auth.register'))
        
        # Validate project selection
        if not project_id:
            flash('Please select a project', 'error')
            return redirect(url_for('auth.register'))
            
        # Create the user
        user = User(
            username=username, 
            email=email, 
            is_admin=is_admin,
            project_id=project_id
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    
    # Get all projects for dropdown
    projects = Project.query.all()
    return render_template('register.html', projects=projects) 