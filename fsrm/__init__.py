from flask import Blueprint

fsrm_bp = Blueprint('fsrm', __name__, template_folder='templates', static_folder='static')

from . import app  # This will import your fsrm/app.py where routes are defined
