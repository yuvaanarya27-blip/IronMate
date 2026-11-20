"""
wsgi.py - Production WSGI Entrypoint for IronMate
Ready for PythonAnywhere, Gunicorn, uWSGI, or any WSGI host.
"""
import sys
import os

# Add current project root to Python module search path
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Load environment variables from .env if present
from dotenv import load_dotenv
env_path = os.path.join(project_home, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

# Import the Flask application as 'application' (standard WSGI convention)
from app import app as application
