# This file contains the WSGI configuration required to serve the application on PythonAnywhere
# It imports your Flask application object (the 'app' variable) from app.py

import sys
import os

# Add your project directory to the Python path
path = '/home/yourusername/kecletterregistry'  # IMPORTANT: Replace 'yourusername' with your PythonAnywhere username
if path not in sys.path:
    sys.path.append(path)

# Import your app variable from your app.py module
from app import app as application  # PythonAnywhere looks for the 'application' variable

# The application variable is what WSGI is looking for
# In your PythonAnywhere dashboard, set the WSGI file to /var/www/yourusername_pythonanywhere_com_wsgi.py
# and set the Python version to match your local development environment 