import functools
from flask import session, flash, redirect, url_for

# --- Session-based Helpers ---

def get_current_user_role():
    """Returns the role of the currently logged-in user."""
    return session.get('role')

def get_current_username():
    """Returns the username of the currently logged-in user."""
    return session.get('username')

# --- Authentication/Authorization Decorators ---

def login_required(role=None):
    """
    A decorator to enforce login and optional role-based access.
    Usage:
    @login_required()          # Requires any logged-in user
    @login_required(role='admin1') # Requires logged-in admin1
    """
    def decorator(f):
        @functools.wraps(f) # Preserves original function metadata
        def decorated_function(*args, **kwargs):
            if 'logged_in' not in session or not session['logged_in']:
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('home')) 
            if role and session.get('role') != role:
                flash(f'Access denied. You must be a {role}.', 'error')
                return redirect(url_for('home')) 
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def any_admin_required():
    """
    A decorator to enforce that the logged-in user is either 'admin1' or 'admin2'.
    """
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            if 'logged_in' not in session or not session['logged_in']:
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('home'))
            if session.get('role') not in ['admin1', 'admin2']:
                flash('Access denied. You must be an administrator.', 'error')
                return redirect(url_for('home'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator