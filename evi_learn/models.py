import hashlib
import datetime
import functools

# --- In-memory "Databases" (Dictionaries acting as data stores) ---

# Users data: username -> { password_hash: str, role: str }
users = {
    'admin1_user': {'password_hash': hashlib.sha256('admin1pass'.encode()).hexdigest(), 'role': 'admin1'},
    'admin2_user_a': {'password_hash': hashlib.sha256('admin2pass'.encode()).hexdigest(), 'role': 'admin2'},
    'admin2_user_b': {'password_hash': hashlib.sha256('admin2pass'.encode()).hexdigest(), 'role': 'admin2'},
    'user_a': {'password_hash': hashlib.sha256('userpass'.encode()).hexdigest(), 'role': 'user'},
    'user_b': {'password_hash': hashlib.sha256('userpass'.encode()).hexdigest(), 'role': 'user'}
}

# Trainings data: training_title (string) -> { ...training details... }
# Each training has a list of videos, and each video can have a list of quizzes.
trainings = {
    'Introduction to Python': {
        'folder_name': 'introduction_to_python',
        'created_by': 'admin1_user',
        'videos': [
            {
                'display_name': 'Python Basics',
                'actual_filename': 'python_basics_placeholder.mp4', # Placeholder
                'upload_date': datetime.date(2024, 1, 15).isoformat(),
                'uploaded_by': 'admin1_user',
                'video_quizzes': [
                    {'question': 'What is Python?', 'type': 'single_mcq', 'options': ['A snake', 'A programming language', 'A type of food'], 'answer': 1},
                    {'question': 'Is Python dynamically typed?', 'type': 'single_mcq', 'options': ['Yes', 'No'], 'answer': 0},
                ]
            },
            {
                'display_name': 'Data Structures in Python',
                'actual_filename': 'data_structures_placeholder.mp4', # Placeholder
                'upload_date': datetime.date(2024, 1, 20).isoformat(),
                'uploaded_by': 'admin1_user',
                'video_quizzes': [
                     {'question': 'Which of these is a mutable data type in Python?', 'type': 'multiple_mcq', 'options': ['Tuple', 'List', 'String', 'Dictionary'], 'correct_options': [1, 3]},
                     {'question': 'Explain the difference between a list and a tuple.', 'type': 'paragraph', 'correct_answer_text': 'Lists are mutable, tuples are immutable.'}
                ]
            }
        ]
    },
    'Web Development with Flask': {
        'folder_name': 'web_dev_flask',
        'created_by': 'admin2_user_a',
        'videos': [
            {
                'display_name': 'Flask Intro',
                'actual_filename': 'flask_intro_placeholder.mp4',
                'upload_date': datetime.date(2024, 2, 1).isoformat(),
                'uploaded_by': 'admin2_user_a',
                'video_quizzes': []
            }
        ]
    }
}

# Certificates data: certificate_id (string UUID) -> { completion_date: str, training_title: str, username: str }
certificates = {}

# User progress data: username (string) -> { training_title: { videos_watched: set, video_quiz_scores: dict } }
# `videos_watched` stores filenames of videos watched.
# `video_quiz_scores` stores { video_filename: { quiz_index: score } }.
progress = {}

# --- Helper Functions for Data Access/Manipulation ---

def get_user_training_progress(username, training_title):
    """
    Ensures the progress structure exists for a given user and training,
    then returns it.
    """
    if username not in progress:
        progress[username] = {}
    if training_title not in progress[username]:
        progress[username][training_title] = {
            'videos_watched': set(),
            'video_quiz_scores': {}
        }
    return progress[username][training_title]

def sanitize_input(input_string):
    """
    Basic input sanitization to prevent Cross-Site Scripting (XSS).
    Replaces common HTML special characters with their entities.
    For production, consider using a dedicated HTML sanitization library (e.g., Bleach).
    """
    if isinstance(input_string, str):
        return input_string.replace('<', '&lt;').replace('>', '&gt;').strip()
    return input_string