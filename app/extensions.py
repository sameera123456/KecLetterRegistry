"""Flask extensions module to avoid circular imports."""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_apscheduler import APScheduler

# Initialize extensions
db = SQLAlchemy()
login = LoginManager()
bcrypt = Bcrypt()
scheduler = APScheduler()

# Configure extensions
login.login_view = 'auth.login'
login.login_message = 'Please log in to access this page.' 