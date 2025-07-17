from flask import Blueprint

fsrm_bp = Blueprint(
'fsrm_bp',
name,
template_folder='Templates',
static_folder='static'
)
from fsrm import app # This will import routes defined in fsrm/app.py