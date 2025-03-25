from flask import Flask, flash, request
import os
import logging
from logging.handlers import RotatingFileHandler
from logging import Formatter
from app.extensions import db, login, bcrypt, scheduler

def create_app(config_name='default'):
    """Application factory function to create and configure Flask app"""
    app = Flask(__name__)
    
    # Load configuration
    from config import config
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    
    # Initialize extensions with app
    db.init_app(app)
    login.init_app(app)
    bcrypt.init_app(app)
    scheduler.init_app(app)
    
    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Initialize logging
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Console logger (always works)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    console_handler.setLevel(logging.INFO)
    app.logger.addHandler(console_handler)
    
    # Try to add file handler, but don't crash if it fails
    try:
        log_file = 'logs/letter_registry.log'
        # Check if log file is locked by another process and use a different file if needed
        if os.path.exists(log_file):
            try:
                # Try to open the file to see if it's accessible
                with open(log_file, 'a'):
                    pass
            except PermissionError:
                log_file = 'logs/letter_registry_alt.log'
                app.logger.warning(f"Using alternative log file: {log_file}")
        
        # File logger
        file_handler = RotatingFileHandler(log_file, maxBytes=10240, backupCount=10)
        file_handler.setFormatter(Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.info('Logging initialized successfully')
    except PermissionError:
        app.logger.warning("Could not create file logger due to permission error")
    except Exception as e:
        app.logger.warning(f"Could not create file logger: {str(e)}")
    
    app.logger.setLevel(logging.INFO)
    app.logger.info('Letter Registry startup')
    
    # Register blueprints
    from app.blueprints.main import main_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.projects import projects_bp
    from app.blueprints.letters import letters_bp
    from app.blueprints.database import database_bp
    from app.blueprints.api import api_bp
    from app.errors import bp as errors_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(projects_bp, url_prefix='/projects')
    app.register_blueprint(letters_bp, url_prefix='/letters')
    app.register_blueprint(database_bp, url_prefix='/database')
    app.register_blueprint(api_bp)
    app.register_blueprint(errors_bp)
    
    # Initialize app context specific extensions
    with app.app_context():
        # Start scheduler
        if not scheduler.running:
            scheduler.start()
        
        # Setup database utilities
        from app.utils.database import init_default_settings
        
        # Use before_app_first_request instead of before_first_request (deprecated in Flask 2.0+)
        def init_app_data():
            init_default_settings()
        
        app.before_first_request(init_app_data)
        
        # Make projects available to all templates
        @app.context_processor
        def inject_projects():
            from app.models.project import Project
            projects = Project.query.all()
            return dict(projects=projects)
    
    # Add no-cache headers for JS files to prevent caching issues
    @app.after_request
    def add_no_cache_headers(response):
        if request.path.endswith('.js'):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response
    
    return app 