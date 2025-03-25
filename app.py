import os
from dotenv import load_dotenv
from app import create_app

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

# Create app instance with the specified environment
# This is the application object that PythonAnywhere will use
app = create_app(os.getenv('FLASK_ENV', 'production'))

# Only run the development server if this file is executed directly
# PythonAnywhere ignores this part and uses the 'app' variable above
if __name__ == '__main__':
    # For local development only
    app.run(debug=True, host='0.0.0.0', port=5000) 