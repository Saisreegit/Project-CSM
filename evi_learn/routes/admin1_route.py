from flask import Blueprint, render_template, redirect, url_for, flash, session, request, current_app, send_from_directory, jsonify
from werkzeug.utils import secure_filename
import os
import datetime
import uuid
import mimetypes
import json # For passing complex data to JS

# Import data models and utilities from top-level modules
from models import users, trainings, certificates, progress, get_user_training_progress, sanitize_input
from utils import login_required, get_current_username

admin1_bp = Blueprint('admin1', __name__, url_prefix='/admin1')

@admin1_bp.route('/dashboard')
@login_required(role='admin1')
def admin1_dashboard():
    # Calculate completion for all users for each training
    trainings_with_completion = {}
    for title, training_data in trainings.items():
        total_users_completed = 0
        for username, user_progress_data in progress.items():
            if training_data['folder_name'] in user_progress_data:
                user_prog_for_training = get_user_training_progress(username, title)
                total_videos_in_training = len(training_data['videos'])
                videos_watched_by_user = len(user_prog_for_training['videos_watched'])

                is_training_complete_for_user = False
                if total_videos_in_training > 0 and videos_watched_by_user == total_videos_in_training:
                    all_quizzes_passed_for_user = True
                    total_quizzes_for_training = sum(len(v.get('video_quizzes', [])) for v in training_data['videos'])
                    if total_quizzes_for_training > 0:
                        quizzes_passed_count = 0
                        for video_info in training_data['videos']:
                            video_filename = video_info['actual_filename']
                            num_quizzes_for_video = len(video_info.get('video_quizzes', []))
                            if video_filename in user_prog_for_training['video_quiz_scores']:
                                for quiz_idx in range(num_quizzes_for_video):
                                    if quiz_idx in user_prog_for_training['video_quiz_scores'][video_filename] and \
                                       user_prog_for_training['video_quiz_scores'][video_filename][quiz_idx] >= 70:
                                        quizzes_passed_count += 1
                        if quizzes_passed_count != total_quizzes_for_training:
                            all_quizzes_passed_for_user = False
                    else:
                        all_quizzes_passed_for_user = True
                    
                    if all_quizzes_passed_for_user:
                        is_training_complete_for_user = True
                
                if is_training_complete_for_user:
                    total_users_completed += 1
        
        trainings_with_completion[title] = {
            'folder_name': training_data['folder_name'],
            'created_by': training_data.get('created_by', 'N/A'),
            'num_videos': len(training_data['videos']),
            'users_completed': total_users_completed
        }

    return render_template('admin1_dashboard.html', 
                           username=get_current_username(),
                           trainings=trainings_with_completion)

@admin1_bp.route('/create_training_folder', methods=['POST'])
@login_required(role='admin1')
def admin1_create_training_folder():
    training_title = sanitize_input(request.form['training_title'])
    if not training_title:
        flash("Training title cannot be empty.", 'error')
        return redirect(url_for('admin1.admin1_dashboard'))

    if training_title in trainings:
        flash("A training with this title already exists.", 'error')
        return redirect(url_for('admin1.admin1_dashboard'))

    # Use secure_filename for the folder name part to avoid issues with special chars
    folder_name = secure_filename(training_title).lower().replace(' ', '_')
    training_path = os.path.join(current_app.config['UPLOAD_FOLDER'], folder_name)

    try:
        os.makedirs(training_path, exist_ok=True)
        trainings[training_title] = {
            'folder_name': folder_name,
            'created_by': session.get('username'),
            'videos': []
        }
        flash(f"Training folder '{training_title}' created successfully!", 'success')
    except OSError as e:
        flash(f"Error creating training folder: {e}", 'error')
    
    return redirect(url_for('admin1.admin1_dashboard'))

@admin1_bp.route('/manage_training/<title>')
@login_required(role='admin1')
def admin1_manage_training(title):
    training_data = trainings.get(title)
    if not training_data:
        flash("Training not found.", 'error')
        return redirect(url_for('admin1.admin1_dashboard'))

    return render_template('admin1_manage_training.html', 
                           training_title=title, 
                           training_data=training_data,
                           uploads_folder=current_app.config['UPLOAD_FOLDER']) # Pass for direct file access in template

@admin1_bp.route('/upload_video/<training_title>', methods=['POST'])
@login_required(role='admin1')
def admin1_upload_video(training_title):
    training_data = trainings.get(training_title)
    if not training_data:
        flash("Training not found.", 'error')
        return redirect(url_for('admin1.admin1_dashboard'))

    if 'video_file' not in request.files:
        flash('No video file part', 'error')
        return redirect(url_for('admin1.admin1_manage_training', title=training_title))

    file = request.files['video_file']
    display_name = sanitize_input(request.form.get('display_name', ''))

    if file.filename == '' or not display_name:
        flash('No selected file or display name missing.', 'error')
        return redirect(url_for('admin1.admin1_manage_training', title=training_title))

    mime_type = mimetypes.guess_type(file.filename)[0]
    if not mime_type or not mime_type.startswith('video/'):
        flash('Invalid file type. Please upload a video file.', 'error')
        return redirect(url_for('admin1.admin1_manage_training', title=training_title))

    if file:
        original_filename = secure_filename(file.filename)
        # Generate a unique filename to prevent overwrites and improve security
        unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
        
        training_folder_path = os.path.join(current_app.config['UPLOAD_FOLDER'], training_data['folder_name'])
        os.makedirs(training_folder_path, exist_ok=True) # Ensure folder exists
        
        filepath = os.path.join(training_folder_path, unique_filename)
        file.save(filepath)

        training_data['videos'].append({
            'display_name': display_name,
            'actual_filename': unique_filename,
            'upload_date': datetime.date.today().isoformat(),
            'uploaded_by': session.get('username'),
            'video_quizzes': []
        })
        flash(f"Video '{display_name}' uploaded successfully!", 'success')
    else:
        flash("Failed to upload video.", 'error')

    return redirect(url_for('admin1.admin1_manage_training', title=training_title))

@admin1_bp.route('/delete_video/<training_title>/<video_filename>')
@login_required(role='admin1')
def admin1_delete_video(training_title, video_filename):
    training_data = trainings.get(training_title)
    if not training_data:
        flash("Training not found.", 'error')
        return redirect(url_for('admin1.admin1_dashboard'))

    video_found = False
    for i, video in enumerate(training_data['videos']):
        if video['actual_filename'] == video_filename:
            # Delete physical file
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], training_data['folder_name'], video_filename)
            if os.path.exists(filepath):
                os.remove(filepath)
            
            # Remove associated progress data for all users
            for username in progress:
                if training_title in progress[username]:
                    user_training_progress = progress[username][training_title]
                    if video_filename in user_training_progress['video_quiz_scores']:
                        del user_training_progress['video_quiz_scores'][video_filename]
                    if video_filename in user_training_progress['videos_watched']:
                        user_training_progress['videos_watched'].remove(video_filename)

            # Remove video from training data
            training_data['videos'].pop(i)
            video_found = True
            flash(f"Video '{video['display_name']}' and its data deleted.", 'success')
            break
    
    if not video_found:
        flash("Video not found.", 'error')

    return redirect(url_for('admin1.admin1_manage_training', title=training_title))

@admin1_bp.route('/delete_training/<title>')
@login_required(role='admin1')
def admin1_delete_training(title):
    if title not in trainings:
        flash("Training not found.", 'error')
        return redirect(url_for('admin1.admin1_dashboard'))
    
    folder_name = trainings[title]['folder_name']
    training_path = os.path.join(current_app.config['UPLOAD_FOLDER'], folder_name)

    # Delete physical files
    if os.path.exists(training_path):
        for filename in os.listdir(training_path):
            file_path = os.path.join(training_path, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
        os.rmdir(training_path)

    # Delete associated progress data for all users
    for username in list(progress.keys()): # Iterate over a copy to allow modification
        if title in progress[username]:
            del progress[username][title]
            if not progress[username]: # If user has no more progress, remove them
                del progress[username]

    # Delete associated certificates
    certs_to_delete = [cert_id for cert_id, cert_data in certificates.items() if cert_data['training_title'] == title]
    for cert_id in certs_to_delete:
        del certificates[cert_id]

    del trainings[title]
    flash(f"Training '{title}' and all its content deleted successfully!", 'success')
    return redirect(url_for('admin1.admin1_dashboard'))

@admin1_bp.route('/manage_video_quizzes/<training_title>/<video_filename>', methods=['GET', 'POST'])
@login_required(role='admin1')
def admin1_manage_video_quizzes(training_title, video_filename):
    training_data = trainings.get(training_title)
    if not training_data:
        flash("Training not found.", 'error')
        return redirect(url_for('admin1.admin1_dashboard'))

    video_info = next((v for v in training_data['videos'] if v['actual_filename'] == video_filename), None)
    if not video_info:
        flash("Video not found.", 'error')
        return redirect(url_for('admin1.admin1_manage_training', title=training_title))

    if request.method == 'POST':
        if 'add_quiz' in request.form:
            question = sanitize_input(request.form['question'])
            quiz_type = request.form['quiz_type']
            options_raw = request.form.get('options', '')
            correct_answer_text = sanitize_input(request.form.get('correct_answer_text', ''))

            if not question:
                flash("Quiz question cannot be empty.", 'error')
                return redirect(url_for('admin1.admin1_manage_video_quizzes', training_title=training_title, video_filename=video_filename))

            new_quiz = {
                'question': question,
                'type': quiz_type,
            }

            if quiz_type == 'paragraph':
                if not correct_answer_text:
                    flash("Correct answer text is required for paragraph questions.", 'error')
                    return redirect(url_for('admin1.admin1_manage_video_quizzes', training_title=training_title, video_filename=video_filename))
                new_quiz['correct_answer_text'] = correct_answer_text
            else: # single_mcq or multiple_mcq
                options = [sanitize_input(opt.strip()) for opt in options_raw.split('\n') if opt.strip()]
                if not options or len(options) < 2:
                    flash("Please provide at least two options for MCQ questions.", 'error')
                    return redirect(url_for('admin1.admin1_manage_video_quizzes', training_title=training_title, video_filename=video_filename))
                
                new_quiz['options'] = options
                
                if quiz_type == 'single_mcq':
                    try:
                        answer_index = int(request.form['answer'])
                        if not (0 <= answer_index < len(options)):
                            raise ValueError
                        new_quiz['answer'] = answer_index
                    except (ValueError, KeyError):
                        flash("Please select a valid correct option for single choice MCQ.", 'error')
                        return redirect(url_for('admin1.admin1_manage_video_quizzes', training_title=training_title, video_filename=video_filename))
                elif quiz_type == 'multiple_mcq':
                    correct_options = request.form.getlist('correct_options')
                    if not correct_options:
                        flash("Please select at least one correct option for multiple choice MCQ.", 'error')
                        return redirect(url_for('admin1.admin1_manage_video_quizzes', training_title=training_title, video_filename=video_filename))
                    
                    try:
                        new_quiz['correct_options'] = sorted([int(idx) for idx in correct_options])
                    except ValueError:
                        flash("Invalid option selected for multiple choice MCQ.", 'error')
                        return redirect(url_for('admin1.admin1_manage_video_quizzes', training_title=training_title, video_filename=video_filename))
            
            video_info['video_quizzes'].append(new_quiz)
            flash("Quiz added successfully!", 'success')
            return redirect(url_for('admin1.admin1_manage_video_quizzes', training_title=training_title, video_filename=video_filename))

        elif 'edit_quiz' in request.form:
            quiz_index = int(request.form['quiz_index'])
            if not (0 <= quiz_index < len(video_info['video_quizzes'])):
                flash("Invalid quiz index.", 'error')
                return redirect(url_for('admin1.admin1_manage_video_quizzes', training_title=training_title, video_filename=video_filename))
            
            quiz_to_edit = video_info['video_quizzes'][quiz_index]
            
            question = sanitize_input(request.form['question'])
            quiz_type = request.form['quiz_type']
            options_raw = request.form.get('options', '')
            correct_answer_text = sanitize_input(request.form.get('correct_answer_text', ''))

            if not question:
                flash("Quiz question cannot be empty.", 'error')
                return redirect(url_for('admin1.admin1_manage_video_quizzes', training_title=training_title, video_filename=video_filename))
            
            quiz_to_edit['question'] = question
            quiz_to_edit['type'] = quiz_type

            if quiz_type == 'paragraph':
                if not correct_answer_text:
                    flash("Correct answer text is required for paragraph questions.", 'error')
                    return redirect(url_for('admin1.admin1_manage_video_quizzes', training_title=training_title, video_filename=video_filename))
                quiz_to_edit['correct_answer_text'] = correct_answer_text
                quiz_to_edit.pop('options', None)
                quiz_to_edit.pop('answer', None)
                quiz_to_edit.pop('correct_options', None)
            else: # single_mcq or multiple_mcq
                options = [sanitize_input(opt.strip()) for opt in options_raw.split('\n') if opt.strip()]
                if not options or len(options) < 2:
                    flash("Please provide at least two options for MCQ questions.", 'error')
                    return redirect(url_for('admin1.admin1_manage_video_quizzes', training_title=training_title, video_filename=video_filename))
                
                quiz_to_edit['options'] = options
                
                if quiz_type == 'single_mcq':
                    try:
                        answer_index = int(request.form['answer'])
                        if not (0 <= answer_index < len(options)):
                            raise ValueError
                        quiz_to_edit['answer'] = answer_index
                    except (ValueError, KeyError):
                        flash("Please select a valid correct option for single choice MCQ.", 'error')
                        return redirect(url_for('admin1.admin1_manage_video_quizzes', training_title=training_title, video_filename=video_filename))
                    quiz_to_edit.pop('correct_options', None)
                elif quiz_type == 'multiple_mcq':
                    correct_options = request.form.getlist('correct_options')
                    if not correct_options:
                        flash("Please select at least one correct option for multiple choice MCQ.", 'error')
                        return redirect(url_for('admin1.admin1_manage_video_quizzes', training_title=training_title, video_filename=video_filename))
                    
                    try:
                        quiz_to_edit['correct_options'] = sorted([int(idx) for idx in correct_options])
                    except ValueError:
                        flash("Invalid option selected for multiple choice MCQ.", 'error')
                        return redirect(url_for('admin1.admin1_manage_video_quizzes', training_title=training_title, video_filename=video_filename))
                    quiz_to_edit.pop('answer', None)
            
            flash("Quiz updated successfully!", 'success')
            return redirect(url_for('admin1.admin1_manage_video_quizzes', training_title=training_title, video_filename=video_filename))

    return render_template('admin1_manage_quizzes.html',
                           training_title=training_title,
                           video_filename=video_filename,
                           video_info=video_info)

@admin1_bp.route('/delete_quiz/<training_title>/<video_filename>/<int:quiz_index>')
@login_required(role='admin1')
def admin1_delete_quiz(training_title, video_filename, quiz_index):
    training_data = trainings.get(training_title)
    if not training_data:
        flash("Training not found.", 'error')
        return redirect(url_for('admin1.admin1_dashboard'))

    video_info = next((v for v in training_data['videos'] if v['actual_filename'] == video_filename), None)
    if not video_info:
        flash("Video not found.", 'error')
        return redirect(url_for('admin1.admin1_manage_training', title=training_title))

    if not (0 <= quiz_index < len(video_info['video_quizzes'])):
        flash("Invalid quiz index.", 'error')
        return redirect(url_for('admin1.admin1_manage_video_quizzes', training_title=training_title, video_filename=video_filename))
    
    deleted_quiz_question = video_info['video_quizzes'][quiz_index]['question']

    # Remove associated quiz scores for all users for this specific quiz
    for username in progress:
        if training_title in progress[username] and \
           video_filename in progress[username][training_title]['video_quiz_scores'] and \
           quiz_index in progress[username][training_title]['video_quiz_scores'][video_filename]:
            del progress[username][training_title]['video_quiz_scores'][video_filename][quiz_index]
            # Optional: if no more quizzes for this video, clean up the video entry
            if not progress[username][training_title]['video_quiz_scores'][video_filename]:
                del progress[username][training_title]['video_quiz_scores'][video_filename]
    
    video_info['video_quizzes'].pop(quiz_index)
    flash(f"Quiz '{deleted_quiz_question}' deleted successfully!", 'success')
    return redirect(url_for('admin1.admin1_manage_video_quizzes', training_title=training_title, video_filename=video_filename))

@admin1_bp.route('/uploads/<folder_name>/<filename>')
def uploaded_file(folder_name, filename):
    # This route serves static files from the UPLOAD_FOLDER
    return send_from_directory(os.path.join(current_app.config['UPLOAD_FOLDER'], folder_name), filename)