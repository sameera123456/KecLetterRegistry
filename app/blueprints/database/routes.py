from flask import render_template, redirect, url_for, flash, request, jsonify, send_from_directory, current_app, make_response
from flask_login import login_required, current_user
import os
import shutil
from datetime import datetime
from app import db
from app.blueprints.database import database_bp
from app.models import Setting
from app.utils.access import head_office_admin_required
from app.utils.database import auto_backup_database

@database_bp.route('/utilities')
@login_required
@head_office_admin_required
def utilities():
    """Database utilities page"""
    selected_tab = request.args.get('tab', 'backup')
    action = request.args.get('action')
    filename = request.args.get('filename')
    
    # Handle restore and delete actions from URL parameters
    if action and filename:
        if action == 'restore':
            try:
                current_app.logger.info(f"Restoring database from backup {filename} via URL parameter")
                restore_result = restore_database_from_file(filename)
                if restore_result['success']:
                    flash(f"Database restored successfully from backup: {filename}", "success")
                else:
                    flash(f"Failed to restore database: {restore_result['error']}", "danger")
            except Exception as e:
                current_app.logger.error(f"Error restoring database from backup {filename}: {str(e)}")
                flash(f"Error restoring database: {str(e)}", "danger")
            return redirect(url_for('database.utilities', tab='backups'))
        
        elif action == 'delete':
            try:
                current_app.logger.info(f"Deleting backup file {filename} via URL parameter")
                delete_result = delete_backup_file(filename)
                if delete_result['success']:
                    flash(f"Backup deleted successfully: {filename}", "success")
                else:
                    flash(f"Failed to delete backup: {delete_result['error']}", "danger")
            except Exception as e:
                current_app.logger.error(f"Error deleting backup {filename}: {str(e)}")
                flash(f"Error deleting backup: {str(e)}", "danger")
            return redirect(url_for('database.utilities', tab='backups'))
    
    # Get auto backup settings
    auto_backup_enabled = Setting.get('auto_backup_enabled', False)
    auto_backup_keep_count = Setting.get('auto_backup_keep_count', 5)
    
    # Check if we need to load the backups for the backups tab
    backups = None
    if selected_tab == 'backups':
        try:
            backups_result = get_backups_list()
            if backups_result['success']:
                backups = backups_result['backups']
        except Exception as e:
            current_app.logger.error(f"Error loading backups for utilities page: {str(e)}")
            flash(f"Error loading backups: {str(e)}", "danger")
    
    return render_template('database_utilities.html', 
                           selected_tab=selected_tab,
                           backups=backups,
                           auto_backup_enabled=auto_backup_enabled,
                           auto_backup_keep_count=auto_backup_keep_count)

# Helper function to get backups list
def get_backups_list():
    try:
        backups_dir = os.path.join(current_app.root_path, 'backups')
        os.makedirs(backups_dir, exist_ok=True)
        
        current_app.logger.debug(f"Looking for backups in: {os.path.abspath(backups_dir)}")
        
        files = []
        for filename in os.listdir(backups_dir):
            if filename.endswith('.db'):
                file_path = os.path.join(backups_dir, filename)
                file_stats = os.stat(file_path)
                
                files.append({
                    'filename': filename,
                    'size': file_stats.st_size,
                    'modified': file_stats.st_mtime,
                    'download_url': url_for('database.download_backup', filename=filename)
                })
        
        # Sort by modification time (newest first)
        files.sort(key=lambda x: x['modified'], reverse=True)
        
        # Convert timestamps to human-readable format
        import datetime
        for file in files:
            file['modified'] = datetime.datetime.fromtimestamp(file['modified']).strftime('%Y-%m-%d %H:%M:%S')
        
        current_app.logger.info(f"Found {len(files)} backup files")
        return {'success': True, 'backups': files}
    
    except Exception as e:
        current_app.logger.error(f"Error listing backups: {str(e)}")
        return {'success': False, 'error': str(e)}

# Helper function to restore database from file
def restore_database_from_file(filename):
    try:
        if not filename.endswith('.db'):
            return {'success': False, 'error': 'Invalid file format. Only .db files are allowed.'}
        
        backup_file_path = os.path.join(current_app.root_path, 'backups', filename)
        
        if not os.path.exists(backup_file_path):
            return {'success': False, 'error': f'Backup file not found: {filename}'}
        
        database_path = os.path.join(current_app.root_path, current_app.config['DATABASE_PATH'])
        
        # Make sure the destination directory exists
        os.makedirs(os.path.dirname(database_path), exist_ok=True)
        
        # Create a temporary backup of the current database
        import shutil
        import datetime
        
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_backup_path = os.path.join(current_app.root_path, 'backups', f'pre_restore_{timestamp}.db')
        
        try:
            if os.path.exists(database_path):
                shutil.copy2(database_path, temp_backup_path)
                current_app.logger.info(f"Created pre-restore backup at {temp_backup_path}")
        except Exception as e:
            current_app.logger.warning(f"Could not create pre-restore backup: {str(e)}")
        
        # Copy the backup file to the database location
        shutil.copy2(backup_file_path, database_path)
        current_app.logger.info(f"Restored database from {backup_file_path} to {database_path}")
        
        return {'success': True}
    
    except Exception as e:
        current_app.logger.error(f"Error restoring database: {str(e)}")
        return {'success': False, 'error': str(e)}

# Helper function to delete backup file
def delete_backup_file(filename):
    try:
        if not filename.endswith('.db'):
            return {'success': False, 'error': 'Invalid file format. Only .db files are allowed.'}
        
        # Make sure filename doesn't have path traversal
        if os.path.sep in filename or (os.path.altsep and os.path.altsep in filename):
            return {'success': False, 'error': 'Invalid filename'}
        
        backup_file_path = os.path.join(current_app.root_path, 'backups', filename)
        
        if not os.path.exists(backup_file_path):
            return {'success': False, 'error': f'Backup file not found: {filename}'}
        
        os.remove(backup_file_path)
        current_app.logger.info(f"Deleted backup file: {backup_file_path}")
        
        return {'success': True}
    
    except Exception as e:
        current_app.logger.error(f"Error deleting backup: {str(e)}")
        return {'success': False, 'error': str(e)}

@database_bp.route('/utilities-scripts')
def utilities_scripts():
    """Serve the JavaScript for the database utilities page."""
    response = make_response('''
// Scripts for database utilities page
document.addEventListener('DOMContentLoaded', function() {
    // Parse URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const tabParam = urlParams.get('tab');
    
    // Switch to the requested tab if specified
    if (tabParam) {
        let tabButton;
        switch(tabParam) {
            case 'backups':
                tabButton = document.getElementById('backups-list-tab');
                break;
            case 'restore':
                tabButton = document.getElementById('restore-tab');
                break;
            case 'settings':
                tabButton = document.getElementById('settings-tab');
                break;
            default:
                tabButton = null;
        }
        
        if (tabButton) {
            tabButton.click();
        }
    }
    
    // Add event listeners to server-rendered restore buttons
    document.querySelectorAll('.restore-backup-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const filename = this.getAttribute('data-filename');
            if (!filename) return;
            
            if (confirm(`WARNING: This will replace all current data with the backup "${filename}". This action cannot be undone. Are you sure you want to continue?`)) {
                // Call the restore function from database-utils.js
                if (typeof restoreFromBackup === 'function') {
                    restoreFromBackup(filename);
                } else {
                    // Fallback if function not loaded
                    window.location.href = '/database/utilities?action=restore&filename=' + encodeURIComponent(filename);
                }
            }
        });
    });
    
    // Add event listeners to server-rendered delete buttons
    document.querySelectorAll('.delete-backup-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const filename = this.getAttribute('data-filename');
            if (!filename) return;
            
            if (confirm(`Are you sure you want to delete the backup "${filename}"? This action cannot be undone.`)) {
                // Call the delete function from database-utils.js
                if (typeof deleteBackup === 'function') {
                    deleteBackup(filename);
                } else {
                    // Fallback if function not loaded
                    window.location.href = '/database/utilities?action=delete&filename=' + encodeURIComponent(filename);
                }
            }
        });
    });
    
    // After successful backup creation, switch to the backups tab
    const successMessage = document.querySelector('.alert-success');
    if (successMessage && successMessage.textContent && successMessage.textContent.includes('backup created successfully')) {
        setTimeout(function() {
            const backupsTab = document.getElementById('backups-list-tab');
            if (backupsTab) {
                backupsTab.click();
            }
        }, 500);
    }
});
''')
    response.headers['Content-Type'] = 'application/javascript'
    return response

@database_bp.route('/backup', methods=['GET', 'POST'])
@login_required
@head_office_admin_required
def backup_database():
    """Create a manual database backup"""
    if request.method == 'GET':
        return redirect(url_for('database.utilities'))
    
    # Check if a backup has been requested
    backup_requested = request.form.get('create_backup') == 'true'
    
    if not backup_requested and request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        # Just a regular form submission without backup request
        return redirect(url_for('database.utilities'))
        
    try:
        # Create backups directory if it doesn't exist
        backup_dir = os.path.join(current_app.root_path, 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            current_app.logger.info(f"Created backups directory: {backup_dir}")
            
        current_app.logger.info(f"Using backups directory: {backup_dir}")
        
        # Generate backup file name with date and time
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        db_uri = current_app.config['SQLALCHEMY_DATABASE_URI']
        
        # Extract database path - handle both relative and absolute paths
        if db_uri.startswith('sqlite:///'):
            if db_uri[10:].startswith('/'):
                # Absolute path
                db_path = db_uri[10:]
            else:
                # Relative path
                db_path = os.path.join(current_app.root_path, db_uri[10:])
                
            current_app.logger.info(f"Database path: {db_path}")
        else:
            current_app.logger.error(f"Unsupported database type: {db_uri}")
            flash('Only SQLite databases are supported for backup', 'error')
            return redirect(url_for('database.utilities'))
        
        if not os.path.exists(db_path):
            current_app.logger.error(f"Database file not found: {db_path}")
            flash(f'Database file not found at path: {db_path}', 'error')
            return redirect(url_for('database.utilities'))
            
        # Create backup filename
        db_name = os.path.basename(db_path)
        backup_filename = f'{db_name}_{timestamp}.db'
        backup_path = os.path.join(backup_dir, backup_filename)
        
        current_app.logger.info(f"Creating backup at: {backup_path}")
        
        # Check if this exact backup already exists (to prevent duplicates)
        if os.path.exists(backup_path):
            current_app.logger.info(f"Backup already exists: {backup_path}")
            flash('This backup already exists', 'info')
            return redirect(url_for('database.utilities'))
        
        # Copy the database file
        try:
            shutil.copy2(db_path, backup_path)
            current_app.logger.info(f"Backup created successfully: {backup_path}")
            
            # Verify the backup was created
            if os.path.exists(backup_path):
                current_app.logger.info(f"Backup file verification successful: {os.path.getsize(backup_path)} bytes")
            else:
                current_app.logger.error(f"Backup file not found after creation: {backup_path}")
                flash('Backup was created but the file could not be verified', 'warning')
                return redirect(url_for('database.utilities'))
        except Exception as copy_error:
            current_app.logger.error(f"Error copying database: {str(copy_error)}")
            flash(f'Error copying database file: {str(copy_error)}', 'error')
            return redirect(url_for('database.utilities'))
        
        flash('Database backup created successfully', 'success')
        return redirect(url_for('database.utilities'))
    except Exception as e:
        current_app.logger.error(f"Error creating backup: {str(e)}")
        flash(f'Error creating backup: {str(e)}', 'error')
        return redirect(url_for('database.utilities'))

@database_bp.route('/backups', methods=['GET'])
@login_required
@head_office_admin_required
def list_backups():
    """List available database backups"""
    try:
        # Create backups directory if it doesn't exist
        backup_dir = os.path.join(current_app.root_path, 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        # Get absolute backups directory path
        abs_backup_dir = os.path.abspath(backup_dir)
        
        # Log for debugging
        current_app.logger.info(f"Looking for backups in: {abs_backup_dir}")
        
        # Simple dictionary approach to ensure uniqueness by filename
        backup_dict = {}
        
        try:
            # List all files in the backup directory
            files_in_dir = os.listdir(abs_backup_dir)
            current_app.logger.info(f"Found {len(files_in_dir)} files in backup directory: {files_in_dir}")
            
            for filename in files_in_dir:
                if not filename.endswith('.db'):
                    continue
                    
                abs_path = os.path.join(abs_backup_dir, filename)
                
                # Only add if it's a file and we haven't seen this filename before
                if os.path.isfile(abs_path) and filename not in backup_dict:
                    stat = os.stat(abs_path)
                    backup_dict[filename] = {
                        'filename': filename,
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                        'timestamp': stat.st_mtime,
                        'download_url': url_for('database.download_backup', filename=filename)
                    }
        except Exception as list_error:
            current_app.logger.error(f"Error listing backup directory: {str(list_error)}")
            
        # Convert the dictionary to a list and sort by timestamp
        backup_files = list(backup_dict.values())
        backup_files.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        
        current_app.logger.info(f"Returning {len(backup_files)} backups")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Set specific JSON content type and ensure no caching
            response = jsonify({'success': True, 'backups': backup_files})
            response.headers['Content-Type'] = 'application/json'
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response
        
        return render_template('database_utilities.html', backups=backup_files)
    except Exception as e:
        current_app.logger.error(f"Error listing backups: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': str(e)})
        flash(f'Error listing backups: {str(e)}', 'error')
        return redirect(url_for('database.utilities'))

@database_bp.route('/backups/<filename>', methods=['GET'])
@login_required
@head_office_admin_required
def download_backup(filename):
    """Download a database backup file"""
    # Validate filename to prevent directory traversal
    if '..' in filename or filename.startswith('/'):
        flash('Invalid backup filename.', 'error')
        return redirect(url_for('database.utilities'))
        
    # Ensure file has .db extension
    if not filename.endswith('.db'):
        flash('Invalid backup file format.', 'error')
        return redirect(url_for('database.utilities'))
        
    try:
        backup_dir = os.path.join(current_app.root_path, 'backups')
        file_path = os.path.join(backup_dir, filename)
        
        # Check if file exists
        if not os.path.exists(file_path):
            flash('Backup file not found.', 'error')
            return redirect(url_for('database.utilities'))
            
        return send_from_directory(backup_dir, filename, as_attachment=True)
    except Exception as e:
        flash(f'Error downloading backup: {str(e)}', 'error')
        return redirect(url_for('database.utilities'))

@database_bp.route('/restore', methods=['POST'])
@login_required
@head_office_admin_required
def restore_database():
    """Restore database from a backup file"""
    try:
        # Check if we have a file upload or a filename
        if 'backup_file' in request.files:
            # Handle file upload
            uploaded_file = request.files['backup_file']
            
            if not uploaded_file or not uploaded_file.filename:
                flash('No file selected', 'error')
                return redirect(url_for('database.utilities'))
                
            # Validate filename
            if not uploaded_file.filename.endswith('.db'):
                flash('Invalid file format. Only .db files are allowed.', 'error')
                return redirect(url_for('database.utilities'))
                
            # Create temp directory for uploaded files if it doesn't exist
            temp_dir = os.path.join(current_app.root_path, 'temp')
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
                
            # Save uploaded file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_filename = f"uploaded_{timestamp}_{uploaded_file.filename}"
            temp_path = os.path.join(temp_dir, safe_filename)
            uploaded_file.save(temp_path)
            
            # Get current database path
            db_uri = current_app.config['SQLALCHEMY_DATABASE_URI']
            
            # Extract database path
            if not db_uri.startswith('sqlite:///'):
                flash('Only SQLite databases are supported for restore', 'error')
                return redirect(url_for('database.utilities'))
                
            if db_uri[10:].startswith('/'):
                db_path = db_uri[10:]
            else:
                db_path = os.path.join(current_app.root_path, db_uri[10:])
            
            # Create backups directory if it doesn't exist
            backup_dir = os.path.join(current_app.root_path, 'backups')
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
                
            # Create a backup of the current database before restoring
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            db_name = os.path.basename(db_path)
            pre_restore_backup = f'pre_restore_{db_name}_{timestamp}.db'
            pre_restore_path = os.path.join(backup_dir, pre_restore_backup)
            
            # Copy current database to pre-restore backup
            shutil.copy2(db_path, pre_restore_path)
            
            # Close database connection
            db.session.close()
            db.engine.dispose()
            
            # Copy uploaded file to database location
            shutil.copy2(temp_path, db_path)
            
            # Clean up temp file
            os.remove(temp_path)
            
            flash('Database restored successfully. Please restart the application.', 'success')
            return redirect(url_for('database.utilities'))
        else:
            # Handle regular form submission with filename
            filename = request.form.get('filename')
            
            # Validate filename
            if not filename or '..' in filename or '/' in filename or '\\' in filename:
                flash('Invalid backup filename.', 'error')
                return redirect(url_for('database.utilities'))
            
            # Get paths
            backup_dir = os.path.join(current_app.root_path, 'backups')
            backup_path = os.path.join(backup_dir, filename)
            
            # Check if backup file exists
            if not os.path.exists(backup_path):
                flash('Backup file not found.', 'error')
                return redirect(url_for('database.utilities'))
            
            # Get current database path
            db_uri = current_app.config['SQLALCHEMY_DATABASE_URI']
            
            # Extract database path - handle both relative and absolute paths
            if db_uri.startswith('sqlite:///'):
                if db_uri[10:].startswith('/'):
                    # Absolute path
                    db_path = db_uri[10:]
                else:
                    # Relative path
                    db_path = os.path.join(current_app.root_path, db_uri[10:])
            else:
                flash('Only SQLite databases are supported for restore', 'error')
                return redirect(url_for('database.utilities'))
            
            # Create a backup of the current database before restoring
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            db_name = os.path.basename(db_path)
            pre_restore_backup = f'pre_restore_{db_name}_{timestamp}.db'
            pre_restore_path = os.path.join(backup_dir, pre_restore_backup)
            
            # Copy current database to pre-restore backup
            shutil.copy2(db_path, pre_restore_path)
            
            # Close database connection
            db.session.close()
            db.engine.dispose()
            
            # Copy backup to current database
            shutil.copy2(backup_path, db_path)
            
            flash('Database restored successfully. Please restart the application.', 'success')
            return redirect(url_for('database.utilities'))
    except Exception as e:
        current_app.logger.error(f"Error restoring database: {str(e)}")
        flash(f'Error restoring database: {str(e)}', 'error')
        return redirect(url_for('database.utilities'))

@database_bp.route('/settings', methods=['GET'])
@login_required
@head_office_admin_required
def get_settings():
    """Get database settings"""
    try:
        # Get requested settings
        keys = request.args.get('keys', '').split(',')
        settings = {}
        
        for key in keys:
            if key.strip():
                settings[key.strip()] = {
                    'value': Setting.get(key.strip())
                }
        
        return jsonify({
            'success': True,
            'settings': settings
        })
    except Exception as e:
        current_app.logger.error(f"Error getting settings: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@database_bp.route('/settings', methods=['POST'])
@login_required
@head_office_admin_required
def update_settings():
    """Update database settings"""
    try:
        if request.is_json:
            data = request.get_json()
            auto_backup_enabled = data.get('auto_backup_enabled', False)
            auto_backup_keep_count = int(data.get('auto_backup_keep_count', 5))
        else:
            auto_backup_enabled = request.form.get('auto_backup_enabled', 'false') == 'true'
            auto_backup_keep_count = int(request.form.get('auto_backup_keep_count', 5))
        
        # Update settings
        Setting.set('auto_backup_enabled', str(auto_backup_enabled).lower(), 'Enable automatic weekly database backups')
        Setting.set('auto_backup_keep_count', str(auto_backup_keep_count), 'Number of automatic backups to keep')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': 'Database settings updated successfully'
            })
        
        flash('Database settings updated successfully', 'success')
        return redirect(url_for('database.utilities'))
    except Exception as e:
        current_app.logger.error(f"Error updating database settings: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'error': str(e)
            })
        flash(f'Error updating database settings: {str(e)}', 'error')
        return redirect(url_for('database.utilities'))

@database_bp.route('/manual-backup')
@login_required
@head_office_admin_required
def manual_auto_backup():
    """Trigger the auto backup process manually"""
    try:
        auto_backup_database()
        flash('Manual backup completed successfully', 'success')
    except Exception as e:
        current_app.logger.error(f"Error during manual backup: {str(e)}")
        flash(f'Error creating manual backup: {str(e)}', 'error')
    
    return redirect(url_for('database.utilities'))

@database_bp.route('/api/backup', methods=['POST'])
@login_required
@head_office_admin_required
def api_backup_database():
    """API endpoint for backup (redirect to main backup route)"""
    return backup_database()

@database_bp.route('/api/backups', methods=['GET'])
@login_required
@head_office_admin_required
def api_list_backups():
    """API endpoint for listing backups (redirect to main backups route)"""
    return list_backups()

@database_bp.route('/api/settings', methods=['GET', 'POST'])
@login_required
@head_office_admin_required
def api_settings():
    """API endpoint for settings (redirect to appropriate settings route)"""
    if request.method == 'GET':
        return get_settings()
    else:
        return update_settings()

@database_bp.route('/restore-from-backup', methods=['POST'])
@login_required
@head_office_admin_required
def restore_from_backup():
    """API endpoint for restoring from backup using JSON"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'})
            
        filename = data.get('filename')
        
        # Validate filename
        if not filename or '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'success': False, 'error': 'Invalid backup filename'})
        
        # Get paths
        backup_dir = os.path.join(current_app.root_path, 'backups')
        backup_path = os.path.join(backup_dir, filename)
        
        # Check if backup file exists
        if not os.path.exists(backup_path):
            return jsonify({'success': False, 'error': 'Backup file not found'})
        
        # Get current database path
        db_uri = current_app.config['SQLALCHEMY_DATABASE_URI']
        
        # Extract database path - handle both relative and absolute paths
        if db_uri.startswith('sqlite:///'):
            if db_uri[10:].startswith('/'):
                # Absolute path
                db_path = db_uri[10:]
            else:
                # Relative path
                db_path = os.path.join(current_app.root_path, db_uri[10:])
        else:
            return jsonify({'success': False, 'error': 'Only SQLite databases are supported for restore'})
        
        # Create a backup of the current database before restoring
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        db_name = os.path.basename(db_path)
        pre_restore_backup = f'pre_restore_{db_name}_{timestamp}.db'
        pre_restore_path = os.path.join(backup_dir, pre_restore_backup)
        
        # Copy current database to pre-restore backup
        shutil.copy2(db_path, pre_restore_path)
        
        # Close database connection
        db.session.close()
        db.engine.dispose()
        
        # Copy backup to current database
        shutil.copy2(backup_path, db_path)
        
        return jsonify({'success': True, 'message': 'Database restored successfully. Please restart the application.'})
    except Exception as e:
        current_app.logger.error(f"Error restoring database: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@database_bp.route('/delete-backup', methods=['POST'])
@login_required
@head_office_admin_required
def delete_backup():
    """API endpoint for deleting backup"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'})
            
        filename = data.get('filename')
        
        # Validate filename
        if not filename or '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'success': False, 'error': 'Invalid backup filename'})
        
        # Ensure file has .db extension
        if not filename.endswith('.db'):
            return jsonify({'success': False, 'error': 'Invalid backup file format'})
            
        # Get backup directory
        backup_dir = os.path.join(current_app.root_path, 'backups')
        file_path = os.path.join(backup_dir, filename)
        
        # Check if file exists
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': 'Backup file not found'})
            
        # Delete file
        os.remove(file_path)
        
        return jsonify({'success': True, 'message': 'Backup deleted successfully'})
    except Exception as e:
        current_app.logger.error(f"Error deleting backup: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

# API Endpoints for compatibility with the frontend
@database_bp.route('/api/database/backup', methods=['POST'])
@login_required
@head_office_admin_required
def api_database_backup():
    """API endpoint for backup that the frontend is accessing"""
    # Set the X-Requested-With header to ensure proper JSON response
    if 'X-Requested-With' not in request.headers:
        request.environ['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
    return backup_database()

@database_bp.route('/api/database/backups', methods=['GET'])
@login_required
@head_office_admin_required
def api_database_backups():
    """API endpoint for listing backups that the frontend is accessing"""
    # Set the X-Requested-With header to ensure proper JSON response
    if 'X-Requested-With' not in request.headers:
        request.environ['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
    return list_backups()

@database_bp.route('/api/database/restore-from-backup', methods=['POST'])
@login_required
@head_office_admin_required
def api_database_restore_from_backup():
    """API endpoint for restoring from backup that the frontend is accessing"""
    # Set the X-Requested-With header to ensure proper JSON response
    if 'X-Requested-With' not in request.headers:
        request.environ['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
    return restore_from_backup()

@database_bp.route('/api/database/delete-backup', methods=['POST'])
@login_required
@head_office_admin_required
def api_database_delete_backup():
    """API endpoint for deleting backup that the frontend is accessing"""
    # Set the X-Requested-With header to ensure proper JSON response
    if 'X-Requested-With' not in request.headers:
        request.environ['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
    return delete_backup() 