from flask import render_template, redirect, url_for, flash, request, jsonify, send_from_directory, current_app, abort
from flask_login import login_required, current_user
import os
from datetime import datetime
from werkzeug.utils import secure_filename
import uuid
from app import db
from app.blueprints.letters import letters_bp
from app.models.letter import Letter
from app.models.project import Project
from app.utils.access import get_user_project_id, project_query_filter, crud_permission_required
from app.utils.database import allowed_file
from app.utils.notifications import (
    create_notification,
    create_notification_for_all_admins,
    create_notification_for_project_users,
    create_notification_for_all_users
)

@letters_bp.route('/')
@login_required
def list_letters():
    project_id = get_user_project_id()
    
    # Get filters
    is_incoming_param = request.args.get('is_incoming')
    filter_project_id = request.args.get('project_id')
    filter_project_code = request.args.get('project_code')
    search_term = request.args.get('search', '')
    
    # Determine letter type for template
    letter_type = 'all'
    if is_incoming_param is not None:
        letter_type = 'incoming' if is_incoming_param.lower() == 'true' else 'outgoing'
    
    # Base query
    query = Letter.query
    
    # Filter by project (unless head office)
    query = project_query_filter(query, Letter)
    
    # Apply filters
    if is_incoming_param is not None:
        is_incoming_bool = is_incoming_param.lower() == 'true'
        query = query.filter_by(is_incoming=is_incoming_bool)
    
    if filter_project_id:
        query = query.filter_by(project_id=filter_project_id)
    elif filter_project_code:
        # Find project by code and filter by its ID
        project = Project.query.filter_by(project_code=filter_project_code).first()
        if project:
            query = query.filter_by(project_id=project.id)
    
    if search_term:
        search = f"%{search_term}%"
        query = query.filter(
            (Letter.letter_number.like(search)) |
            (Letter.description.like(search)) |
            (Letter.object_of.like(search)) |
            (Letter.sender.like(search)) |
            (Letter.recipient.like(search))
        )
    
    # Get letters
    letters = query.order_by(Letter.date.desc()).all()
    
    # Get all projects for filter dropdown
    if current_user.is_head_office:
        projects = Project.query.all()
    else:
        projects = Project.query.filter_by(id=project_id).all()
    
    # Pass the selected project_code to the template
    selected_project_code = filter_project_code
    
    return render_template('letters.html', 
                          letters=letters, 
                          projects=projects, 
                          letter_type=letter_type,
                          project_code=selected_project_code)

@letters_bp.route('/create', methods=['GET', 'POST'])
@login_required
@crud_permission_required
def create_letter():
    user_project_id = get_user_project_id()
    
    if request.method == 'POST':
        project_id = request.form.get('project_id')
        letter_type = request.form.get('letter_type')
        is_incoming = letter_type == 'incoming'
        date = request.form.get('date')
        object_of = request.form.get('object_of')
        description = request.form.get('description')
        sender = request.form.get('sender')
        recipient = request.form.get('recipient')
        
        # Validate required fields
        if not project_id or not date or not object_of:
            flash('Project, Date, and Subject are required fields', 'error')
            return redirect(url_for('letters.create_letter'))
        
        # Check if the project exists and user has access
        project = Project.query.get(project_id)
        if not project:
            flash('Selected project does not exist', 'error')
            return redirect(url_for('letters.create_letter'))
        
        if not current_user.is_head_office and int(project_id) != current_user.project_id:
            flash('You do not have permission to add letters to this project', 'error')
            return redirect(url_for('letters.create_letter'))
        
        # Format date
        try:
            letter_date = datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            flash('Invalid date format', 'error')
            return redirect(url_for('letters.create_letter'))
        
        # Get HO and project numbers
        project_number = request.form.get('project_number', '0')
        ho_number = request.form.get('ho_number', '0')
        
        # Validate project and HO numbers (must be numeric)
        if not project_number.isdigit() or not ho_number.isdigit():
            # Generate new numbers using the same logic as in generate_numbers
            next_ho_number = 1
            next_project_number = 1
            
            # Get the last HO number
            last_ho_letter = Letter.query.filter(
                Letter.ho_number.isnot(None),
                Letter.is_incoming == is_incoming
            ).order_by(Letter.ho_number.desc()).first()
            
            if last_ho_letter and last_ho_letter.ho_number and last_ho_letter.ho_number.isdigit():
                next_ho_number = int(last_ho_letter.ho_number) + 1
                if next_ho_number > 9999:
                    next_ho_number = 1
            
            # Get the last project number
            project_number_query = Letter.query.filter(
                Letter.project_number.isnot(None),
                Letter.is_incoming == is_incoming,
                Letter.project_id == project_id
            ).order_by(Letter.project_number.desc()).first()
            
            if project_number_query and project_number_query.project_number and project_number_query.project_number.isdigit():
                next_project_number = int(project_number_query.project_number) + 1
                if next_project_number > 9999:
                    next_project_number = 1
            
            project_number = str(next_project_number).zfill(4)
            ho_number = str(next_ho_number).zfill(4)
        
        # Generate letter number using the previous format
        year = datetime.now().strftime('%y')
        letter_type_code = "IN" if is_incoming else "OU"
        letter_number = f"KEC/{project.project_code}/{letter_type_code}/{year}-{ho_number}-{project_number}"
        
        # Check if letter number already exists
        if Letter.query.filter_by(letter_number=letter_number).first():
            flash('Letter number already exists. Please refresh to get a new number.', 'error')
            return redirect(url_for('letters.create_letter'))
        
        # Check if a file was uploaded
        letter_file = None
        file_name = None
        
        if 'letter_file' in request.files:
            file = request.files['letter_file']
            if file and file.filename and allowed_file(file.filename):
                try:
                    filename = secure_filename(file.filename)
                    # Generate unique filename
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
                    file.save(file_path)
                    file_name = unique_filename
                    
                    # Read the file content for storage
                    with open(file_path, 'rb') as f:
                        letter_file = f.read()
                except Exception as e:
                    current_app.logger.error(f"Error saving file: {str(e)}")
                    flash(f'Error saving file: {str(e)}', 'error')
                    return redirect(url_for('letters.create_letter'))
            elif file.filename and not allowed_file(file.filename):
                flash('File type not allowed. Please upload a PDF file.', 'error')
                return redirect(url_for('letters.create_letter'))
        else:
            flash('Letter file is required', 'error')
            return redirect(url_for('letters.create_letter'))
        
        # Create letter
        letter = Letter(
            letter_number=letter_number,
            project_id=project_id,
            date=letter_date,
            object_of=object_of,
            project_number=project_number,
            ho_number=ho_number,
            description=description,
            in_charge=request.form.get('in_charge'),
            reference=request.form.get('reference'),
            remarks=request.form.get('remarks'),
            file_name=file_name,
            is_incoming=is_incoming,
            letter_content=letter_file,
            created_by=current_user.id,
            sender=sender,
            recipient=recipient,
            priority=request.form.get('priority'),
            status=request.form.get('status', 'Pending'),
            department=request.form.get('department'),
            category=request.form.get('category'),
            tags=request.form.get('tags')
        )
        
        try:
            db.session.add(letter)
            db.session.commit()
            flash('Letter created successfully', 'success')
            
            # Get project details for notification
            project = Project.query.get(project_id)
            letter_type = "incoming" if is_incoming else "outgoing"
            
            # Create notification for all users
            if current_user.is_head_office:
                # If head office user creates a letter, notify everyone
                create_notification_for_all_users(
                    title=f"New {letter_type.title()} Letter",
                    message=f"Letter {letter.letter_number} has been added by Head Office for project {project.project_code}",
                    icon="fa-envelope",
                    icon_color="bg-info",
                    link=url_for('letters.view_letter', letter_id=letter.id)
                )
            else:
                # If project user creates a letter:
                # 1. Notify all users in their project
                create_notification_for_project_users(
                    title=f"New {letter_type.title()} Letter",
                    message=f"Letter {letter.letter_number} has been added by {current_user.username}",
                    project_id=project_id,
                    icon="fa-envelope",
                    icon_color="bg-info",
                    link=url_for('letters.view_letter', letter_id=letter.id)
                )
                
                # 2. Notify all head office users and admins
                create_notification_for_all_admins(
                    title=f"New {letter_type.title()} Letter",
                    message=f"Letter {letter.letter_number} has been added by {current_user.username} for project {project.project_code}",
                    icon="fa-envelope-open",
                    icon_color="bg-info",
                    link=url_for('letters.view_letter', letter_id=letter.id)
                )
            
            return redirect(url_for('letters.view_letter', letter_id=letter.id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating letter: {str(e)}")
            flash(f'Error creating letter: {str(e)}', 'error')
            return redirect(url_for('letters.create_letter'))
    
    # GET request handling
    # Get default letter type from query param
    default_letter_type = request.args.get('letter_type', 'incoming')
    
    # Get all projects for dropdown
    if current_user.is_head_office:
        projects = Project.query.all()
    else:
        projects = Project.query.filter_by(id=user_project_id).all()
    
    return render_template('create_letter.html', projects=projects, default_letter_type=default_letter_type)

@letters_bp.route('/<int:letter_id>')
@login_required
def view_letter(letter_id):
    letter = Letter.query.get_or_404(letter_id)
    
    # Check if user has access to this letter by comparing with their project_id
    user_project_id = get_user_project_id()
    
    # Head office users can view any letter
    if current_user.is_head_office:
        pass  # No restriction for head office users
    # Project users can only view letters from their own project
    elif user_project_id is None or int(letter.project_id) != int(user_project_id):
        flash('You do not have permission to view this letter', 'error')
        return redirect(url_for('letters.list_letters'))
    
    return render_template('view_letter.html', letter=letter)

@letters_bp.route('/<int:letter_id>/edit', methods=['GET', 'POST'])
@login_required
@crud_permission_required
def edit_letter(letter_id):
    letter = Letter.query.get_or_404(letter_id)
    
    # Check if user has access to this letter by comparing with their project_id
    user_project_id = get_user_project_id()
    
    # Head office users can edit any letter
    if current_user.is_head_office:
        pass  # No restriction for head office users
    # Project users can only edit letters from their own project
    elif user_project_id is None or int(letter.project_id) != int(user_project_id):
        flash('You do not have permission to edit this letter', 'error')
        return redirect(url_for('letters.list_letters'))
    
    if request.method == 'POST':
        # Update fields
        letter.object_of = request.form.get('object_of')
        letter.description = request.form.get('description')
        letter.in_charge = request.form.get('in_charge')
        letter.reference = request.form.get('reference')
        letter.remarks = request.form.get('remarks')
        letter.sender = request.form.get('sender')
        letter.recipient = request.form.get('recipient')
        letter.priority = request.form.get('priority')
        letter.status = request.form.get('status')
        letter.department = request.form.get('department')
        letter.category = request.form.get('category')
        letter.tags = request.form.get('tags')
        
        # Format date if provided
        date = request.form.get('date')
        if date:
            try:
                letter.date = datetime.strptime(date, '%Y-%m-%d')
            except ValueError:
                flash('Invalid date format', 'error')
                return redirect(url_for('letters.edit_letter', letter_id=letter.id))
        
        # Check if a new file was uploaded
        if 'letter_file' in request.files:
            file = request.files['letter_file']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Generate unique filename
                unique_filename = f"{uuid.uuid4()}_{filename}"
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(file_path)
                
                # Delete old file if exists
                if letter.file_name:
                    old_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], letter.file_name)
                    if os.path.exists(old_file_path):
                        os.remove(old_file_path)
                
                letter.file_name = unique_filename
                
                # Read the file content for storage
                with open(file_path, 'rb') as f:
                    letter.letter_content = f.read()
        
        db.session.commit()
        flash('Letter updated successfully', 'success')
        
        # Create notification for the user
        create_notification(
            title="Letter Updated",
            message=f"Letter {letter.letter_number} has been updated successfully",
            user_id=current_user.id,
            icon="fa-edit",
            icon_color="bg-primary",
            link=url_for('letters.view_letter', letter_id=letter.id)
        )
        
        # Notify admins if user is not admin
        if not current_user.is_admin:
            create_notification_for_all_admins(
                title="Letter Updated",
                message=f"Letter {letter.letter_number} has been modified by {current_user.username}",
                icon="fa-edit",
                icon_color="bg-warning",
                link=url_for('letters.view_letter', letter_id=letter.id)
            )
            
        return redirect(url_for('letters.view_letter', letter_id=letter.id))
    
    # Get all projects for dropdown
    projects = Project.query.all()
    
    return render_template('edit_letter.html', letter=letter, projects=projects)

@letters_bp.route('/<int:letter_id>/delete', methods=['POST'])
@login_required
@crud_permission_required
def delete_letter(letter_id):
    letter = Letter.query.get_or_404(letter_id)
    
    # Check if user has access to this letter by comparing with their project_id
    user_project_id = get_user_project_id()
    
    # Head office users can delete any letter
    if current_user.is_head_office:
        pass  # No restriction for head office users
    # Project users can only delete letters from their own project
    elif user_project_id is None or int(letter.project_id) != int(user_project_id):
        flash('You do not have permission to delete this letter', 'error')
        return redirect(url_for('letters.list_letters'))
    
    # Delete file if exists
    if letter.file_name:
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], letter.file_name)
        if os.path.exists(file_path):
            os.remove(file_path)
    
    db.session.delete(letter)
    db.session.commit()
    
    # Get letter information before it's lost after deletion
    letter_number = letter.letter_number
    
    # Create notification for the user
    create_notification(
        title="Letter Deleted",
        message=f"Letter {letter_number} has been deleted successfully",
        user_id=current_user.id,
        icon="fa-trash",
        icon_color="bg-danger"
    )
    
    # Notify admins if user is not admin
    if not current_user.is_admin:
        create_notification_for_all_admins(
            title="Letter Deleted",
            message=f"Letter {letter_number} has been deleted by {current_user.username}",
            icon="fa-trash",
            icon_color="bg-danger"
        )
    
    flash('Letter deleted successfully', 'success')
    return redirect(url_for('letters.list_letters'))

@letters_bp.route('/download/<int:letter_id>')
@login_required
def download_letter(letter_id):
    letter = Letter.query.get_or_404(letter_id)
    
    # Check if user has access to this letter by comparing with their project_id
    user_project_id = get_user_project_id()
    
    # Head office users can view any letter
    if current_user.is_head_office:
        pass  # No restriction for head office users
    # Project users can only view letters from their own project
    elif user_project_id is None or int(letter.project_id) != int(user_project_id):
        flash('You do not have permission to download this letter', 'error')
        return redirect(url_for('letters.list_letters'))
    
    if not letter.file_name:
        flash('No file available for this letter', 'error')
        return redirect(url_for('letters.view_letter', letter_id=letter.id))
    
    try:
        # Check if the request is for inline viewing or download
        inline = request.args.get('inline', '0') == '1'
        
        # Set the appropriate Content-Disposition header
        download_name = f"Letter_{letter.letter_number}.pdf"
        attachment_header = "inline" if inline else "attachment"
        
        return send_from_directory(
            current_app.config['UPLOAD_FOLDER'],
            letter.file_name,
            as_attachment=not inline,
            download_name=download_name
        )
    except Exception as e:
        current_app.logger.error(f"Error downloading letter: {str(e)}")
        flash('Error downloading file', 'error')
        return redirect(url_for('letters.view_letter', letter_id=letter.id))

@letters_bp.route('/generate_numbers')
@login_required
@crud_permission_required
def generate_numbers():
    # Get letter type from request
    is_incoming_param = request.args.get('is_incoming', '0')
    is_incoming = is_incoming_param == '1'
    
    # Get project ID from request
    project_id = request.args.get('project_id')
    
    current_app.logger.info(f"Generating numbers for {'incoming' if is_incoming else 'outgoing'} letter for project_id {project_id}. Param value: {is_incoming_param}")
    
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
            current_app.logger.debug(f"Found last HO number: {last_ho_letter.ho_number}, next: {next_ho_number}")
        except ValueError:
            next_ho_number = 1
            current_app.logger.debug(f"Error converting HO number: {last_ho_letter.ho_number}, using 1")
    else:
        next_ho_number = 1
        current_app.logger.debug("No previous HO number found, using 1")

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
            current_app.logger.debug(f"Found last project number: {last_project_letter.project_number}, next: {next_project_number}")
        except ValueError:
            next_project_number = 1
            current_app.logger.debug(f"Error converting project number: {last_project_letter.project_number}, using 1")
    else:
        next_project_number = 1
        current_app.logger.debug("No previous project number found, using 1")
    
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
    
    current_app.logger.info(f"Returning numbers: {response_data}")
    return jsonify(response_data) 