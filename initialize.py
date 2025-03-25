#!/usr/bin/env python3
"""
Initialization script for KEC Letter Registry
This script will:
1. Set up necessary directories
2. Initialize the database
3. Create the default Head Office project with code "HO"
4. Create an admin user

Run this script once when deploying to a new environment like PythonAnywhere.
"""

import os
import sys
from pathlib import Path

print("Starting KEC Letter Registry initialization...")

# Ensure we're in the correct directory
PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)

# Create necessary directories
for directory in ['backups', 'logs', 'app/static/uploads', 'instance']:
    path = PROJECT_ROOT / directory
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {directory}")

# Initialize the database
print("\nInitializing database...")
try:
    from reset_db import reset_database
    reset_database()
    print("Database initialized successfully.")
except Exception as e:
    print(f"Error initializing database: {e}")
    sys.exit(1)

print("\n===== INITIALIZATION COMPLETE =====")
print("KEC Letter Registry is now set up and ready to use.")
print("Default admin account:")
print("  Username: admin")
print("  Password: admin123")
print("\nIMPORTANT: Please change the admin password immediately after login.")
print("==============================================") 