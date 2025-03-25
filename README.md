# KEC Letter Registry System

A comprehensive web-based letter management system built with Flask that allows users to manage projects and their associated letters. The system supports both incoming and outgoing letters with PDF attachments, automated backups, and dark mode.

## Features

- **User Authentication System**
  - Role-based access control (Admin, Head Office, Site users)
  - Secure registration with invitation codes
  - User profile management
  
- **Project Management**
  - Create, view, edit, and delete projects
  - Project statistics and overview
  - Project-specific permissions
  
- **Letter Management**
  - Support for both incoming and outgoing letters
  - PDF file attachments and previews
  - Automatic letter numbering system
  - Letter categorization by project
  - Advanced search and filtering options
  
- **Database Utilities**
  - Manual and automatic database backups
  - Database restoration
  - Scheduled weekly backups
  - Backup rotation and management
  
- **Notification System**
  - Real-time notifications for users
  - Activity tracking and logging
  - Duplicate notification prevention
  
- **UI Features**
  - Dark/Light mode toggle
  - Responsive design for all devices
  - Modern Bootstrap-based interface
  - Grid and list view options

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Virtual environment (recommended)
- Web browser with JavaScript enabled

## Installation

1. Clone the repository:
```bash
git clone https://github.com/your-username/KecLetterRegistry.git
cd KecLetterRegistry
```

2. Create and activate a virtual environment:
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file in the root directory with the following content:
```
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///letter_registry.db
ADMIN_CODE=your-admin-registration-code
```

## Running the Application

1. Start the application:
```bash
python app.py
```

2. Open your web browser and navigate to:
```
http://localhost:5000
```

3. For production deployment, use Gunicorn:
```bash
gunicorn app:app
```

## Usage

### User Management
- **Registration**: Use the provided registration code to create a new account
- **Login**: Authenticate with your username and password
- **User Types**: Regular users, Administrators, and Head Office administrators

### Project Management
- Create and manage projects with detailed information
- Track project progress and statistics
- Assign projects to specific sites

### Letter Management
- Register incoming and outgoing letters
- Attach PDF files to letters
- Generate automatic letter numbers
- Search and filter letters by various criteria

### Database Management
- Create manual backups of the database
- Restore from existing backups
- Enable/disable automatic weekly backups
- Configure backup retention settings

## Project Structure

```
KecLetterRegistry/
├── static/
│   ├── css/
│   ├── js/
│   └── uploads/
├── templates/
├── backups/
├── logs/
├── app.py
├── requirements.txt
├── .env
└── README.md
```

## Security Features

- All routes require authentication
- Role-based access control
- Passwords are hashed with bcrypt
- CSRF protection on all forms
- Secure file upload validation
- SQL injection prevention through SQLAlchemy
- Regular database backups

## Deployment Notes

For production deployment:
1. Use a production WSGI server like Gunicorn
2. Set up a reverse proxy with Nginx or Apache
3. Use a proper database server instead of SQLite
4. Enable HTTPS with SSL/TLS certificates
5. Implement proper logging and monitoring

## License

This project is licensed under the MIT License - see the LICENSE file for details. 