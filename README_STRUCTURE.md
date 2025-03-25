# KEC Letter Registry - Scalable Flask Structure

This document explains the updated structure of the KEC Letter Registry application, which has been refactored to follow Flask best practices for scalability and maintainability.

## Application Structure

```
KecLetterRegistry/
├── app/                     # Main application package
│   ├── blueprints/          # Feature-based blueprints
│   │   ├── auth/            # Authentication blueprint
│   │   ├── database/        # Database utilities blueprint
│   │   ├── letters/         # Letter management blueprint
│   │   ├── main/            # Main application blueprint
│   │   ├── projects/        # Project management blueprint
│   │   └── sites/           # Site management blueprint
│   ├── models/              # Database models
│   │   ├── letter.py        # Letter model
│   │   ├── notification.py  # Notification model
│   │   ├── project.py       # Project model
│   │   ├── setting.py       # Setting model
│   │   ├── site.py          # Site model
│   │   └── user.py          # User model
│   ├── static/              # Static assets (CSS, JS, images)
│   ├── templates/           # Jinja2 templates
│   ├── utils/               # Utility functions
│   │   ├── access.py        # Access control utilities
│   │   ├── database.py      # Database utilities
│   │   └── notifications.py # Notification utilities
│   └── __init__.py          # Application factory
├── migrations/              # Alembic database migrations
├── tests/                   # Test suite
├── config.py                # Configuration settings
├── wsgi.py                  # WSGI entry point
├── requirements.txt         # Python dependencies
└── README.md                # Project documentation
```

## Key Architectural Improvements

1. **Application Factory Pattern**
   - The app is created using an application factory pattern in `app/__init__.py`
   - This allows for multiple instances of the application (e.g., for testing)
   - Extensions are initialized in a modular way

2. **Blueprints for Feature Modules**
   - Each major feature is separated into its own blueprint
   - Routes are organized by functionality (auth, projects, letters, etc.)
   - Promotes separation of concerns and code organization

3. **Model Separation**
   - Each database model is in its own file under `app/models/`
   - Cleaner code organization and easier maintenance
   - Better import patterns and reduced circular dependencies

4. **Configuration Management**
   - Environment-specific configuration (development, testing, production)
   - Settings loaded from environment variables
   - Different database URIs for different environments

5. **Utility Functions**
   - Common utilities separated into logical modules
   - Access control, database operations, and notifications
   - Reusable across different parts of the application

## Deployment Considerations

1. **Development Mode**
   ```
   export FLASK_ENV=development
   python wsgi.py
   ```

2. **Production Mode**
   ```
   export FLASK_ENV=production
   gunicorn wsgi:app
   ```

3. **Testing**
   ```
   export FLASK_ENV=testing
   pytest
   ```

## Benefits of the New Structure

- **Scalability**: Easy to add new features as separate blueprints
- **Maintainability**: Clear organization and reduced complexity
- **Testability**: Easier to write unit and integration tests
- **Collaboration**: Multiple developers can work on different blueprints simultaneously
- **Flexibility**: Easier to swap out components (e.g., database, auth system) 