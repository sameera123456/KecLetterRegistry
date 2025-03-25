from flask import Blueprint

letters_bp = Blueprint('letters', __name__)

from app.blueprints.letters import routes 