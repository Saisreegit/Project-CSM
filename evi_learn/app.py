from flask import Flask, render_template, request, redirect, url_for, session, flash
import hashlib
import os

# Import configuration, data models, and utility functions
from config import Config
from models import users, trainings, certificates, progress
from utils import login_required, get_current_username

# Import blueprints from the 'routes' package
from routes.admin1_routes import admin1_bp
from routes.admin2_routes import admin2_bp
from routes.user_routes import user_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Register Blueprints
    app.register_blueprint(admin1_bp)
    app.register_blueprint(admin2_bp)
    app.register_blueprint(user_bp)

    # Ensure the upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # --- Central/General Routes ---

    @app.route('/')
    @app.route('/home')
    def home():
        if 'logged_in' in session and session['logged_in']:
            if session.get('role') == 'admin1':
                return redirect(url_for('admin1.admin1_dashboard'))
            elif session.get('role') == 'admin2':
                return redirect(url_for('admin2.admin2_dashboard'))
            elif session.get('role') == 'user':
                return redirect(url_for('user.user_dashboard'))
        return render_template('home.html')

    @app.route('/login', methods=['POST'])
    def login():
        username = request.form['username']
        password = request.form['password']

        user_data = users.get(username)

        if user_data and hashlib.sha256(password.encode()).hexdigest() == user_data['password_hash']:
            session['logged_in'] = True
            session['username'] = username
            session['role'] = user_data['role']
            flash('Logged in successfully!', 'success')
            
            if user_data['role'] == 'admin1':
                return redirect(url_for('admin1.admin1_dashboard'))
            elif user_data['role'] == 'admin2':
                return redirect(url_for('admin2.admin2_dashboard'))
            elif user_data['role'] == 'user':
                return redirect(url_for('user.user_dashboard'))
        else:
            flash('Invalid username or password.', 'error')
            return redirect(url_for('home'))

    @app.route('/logout')
    @login_required() # Ensure only logged-in users can logout
    def logout():
        session.pop('logged_in', None)
        session.pop('username', None)
        session.pop('role', None)
        flash('You have been logged out.', 'info')
        return redirect(url_for('home'))
    
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('error.html', error_code=404, error_message="Page Not Found"), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('error.html', error_code=403, error_message="Forbidden Access"), 403

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('error.html', error_code=500, error_message="Internal Server Error"), 500

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True) # Run in debug mode for development