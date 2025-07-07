from flask import Blueprint

crms_bp = Blueprint('crms', __name__, template_folder='templates', static_folder='static')

from . import routes  # make sure routes.py exists

