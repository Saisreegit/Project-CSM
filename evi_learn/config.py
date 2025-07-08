import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a_super_secret_key_that_is_very_hard_to_guess_12345'
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
    # MAX_CONTENT_LENGTH = 16 * 1024 * 1024 # Optional: 16 MB limit for uploads