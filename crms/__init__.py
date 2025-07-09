from flask import Flask
from crms.routes import crms_bp

def init_app():
    app = Flask(__name__)
    app.secret_key = "your_secret_key"
    app.register_blueprint(crms_bp)
    return app
