import os

# --- Flask App Configuration ---
UPLOAD_FOLDER = 'uploads'
SECRET_KEY = 'your_very_secret_key_here' # CHANGE THIS IN PRODUCTION!

# --- Email Configuration ---
# IMPORTANT: Replace with your actual email details.
# If using Gmail, you MUST generate an "App Password" if you have 2-Step Verification enabled.
# Your regular Gmail password WILL NOT work.
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
EMAIL_SENDER = 'adarshadarsh96126@gmail.com' # Replace with YOUR Gmail email address
# >>> SECURITY WARNING: HARDCODED PASSWORD <<<
# In a production environment, NEVER hardcode sensitive information like passwords.
# Use environment variables (e.g., os.environ.get('EMAIL_PASSWORD')),
# a dedicated secrets management service, or a configuration file excluded from version control.
EMAIL_PASSWORD = 'cngq pvzc bmci cpws' # Replace with YOUR generated Gmail App Password