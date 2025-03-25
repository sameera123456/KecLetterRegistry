from flask import Blueprint

database_bp = Blueprint('database', __name__)

from app.blueprints.database import routes 