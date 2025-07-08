from flask import Blueprint, render_template, redirect, url_for, flash, session, request, current_app, send_from_directory
import datetime
import uuid
import json # For quizzes

# Import data models and utilities from top-level modules
from models import users, trainings, certificates, progress, get_user_training_progress, sanitize_input
from utils import login_required, get_current_username

user_bp = Blueprint('user', __name__, url_prefix='/user')

@user_bp.route('/dashboard')
@login_required(role='user')
def user_dashboard():
    current_username = get_current_username()
    user_progress = progress.get(current_username, {})

    trainings_status = []
    for title, training_data in trainings.items():
        user_prog_for_training = get_user_training_progress(current_username, title)
        
        total_videos = len(training_data['videos'])
        videos_watched = len(user_prog_for_training['videos_watched'])

        completion_percentage = 0
        if total_videos > 0:
            completion_percentage = int((videos_watched / total_videos) * 100)

        # Determine quiz completion status
        all_quizzes_passed = False
        total_quizzes_in_training = sum(len(v.get('video_quizzes', [])) for v in training_data['videos'])
        quizzes_passed_count = 0

        if total_quizzes_in_training > 0:
            for video_info in training_data['videos']:
                video_filename = video_info['actual_filename']
                if video_filename in user_prog_for_training['video_quiz_scores']:
                    for quiz_idx, score in user_prog_for_training['video_quiz_scores'][video_filename].items():
                        if score >= 70: # Assuming 70% is passing score
                            quizzes_passed_count += 1
            if quizzes_passed_count == total_quizzes_in_training:
                all_quizzes_passed = True
        else: # No quizzes, so they are "passed" by default
            all_quizzes_passed = True
        
        is_completed = (videos_watched == total_videos and total_videos > 0) and all_quizzes_passed

        trainings_status.append({
            'title': title,
            'completion_percentage': completion_percentage,
            'is_completed': is_completed
        })
    
    # Get user's certificates
    user_certificates = [
        cert for cert_id, cert in certificates.items() if cert['username'] == current_username
    ]

    return render_template('user_dashboard.html', 
                           username=current_username,
                           trainings_status=trainings_status,
                           user_certificates=user_certificates)

@user_bp.route('/training/<training_title>')
@login_required(role='user')
def user_training_details(training_title):
    training_data = trainings.get(training_title)
    if not training_data:
        flash("Training not found.", 'error')
        return redirect(url_for('user.user_dashboard'))
    
    current_username = get_current_username()
    user_prog = get_user_training_progress(current_username, training_title)

    videos_for_template = []
    for video in training_data['videos']:
        video_filename = video['actual_filename']
        is_watched = video_filename in user_prog['videos_watched']

        quiz_status = []
        for i, quiz in enumerate(video.get('video_quizzes', [])):
            score = user_prog['video_quiz_scores'].get(video_filename, {}).get(i)
            quiz_status.append({
                'index': i,
                'question': quiz['question'],
                'type': quiz['type'],
                'score': score,
                'passed': score is not None and score >= 70 # Assuming 70% pass mark
            })

        videos_for_template.append({
            'display_name': video['display_name'],
            'actual_filename': video['actual_filename'],
            'is_watched': is_watched,
            'quizzes': quiz_status
        })

    return render_template('user_training_details.html',
                           training_title=training_title,
                           training_data=training_data,
                           videos=videos_for_template,
                           current_username=current_username,
                           uploads_folder=current_app.config['UPLOAD_FOLDER'])

@user_bp.route('/mark_watched/<training_title>/<video_filename>')
@login_required(role='user')
def user_mark_watched(training_title, video_filename):
    training_data = trainings.get(training_title)
    if not training_data:
        flash("Training not found.", 'error')
        return redirect(url_for('user.user_dashboard'))

    video_info = next((v for v in training_data['videos'] if v['actual_filename'] == video_filename), None)
    if not video_info:
        flash("Video not found in this training.", 'error')
        return redirect(url_for('user.user_training_details', training_title=training_title))

    current_username = get_current_username()
    user_prog = get_user_training_progress(current_username, training_title)
    user_prog['videos_watched'].add(video_filename)
    flash(f"'{video_info['display_name']}' marked as watched!", 'success')

    # Check for overall training completion after marking video watched
    total_videos = len(training_data['videos'])
    videos_watched = len(user_prog['videos_watched'])

    all_videos_watched = (videos_watched == total_videos and total_videos > 0)
    
    # Check quiz completion
    all_quizzes_passed = True
    total_quizzes_in_training = sum(len(v.get('video_quizzes', [])) for v in training_data['videos'])
    
    if total_quizzes_in_training > 0:
        quizzes_passed_count = 0
        for vid_info in training_data['videos']:
            vid_filename = vid_info['actual_filename']
            if vid_filename in user_prog['video_quiz_scores']:
                for quiz_score in user_prog['video_quiz_scores'][vid_filename].values():
                    if quiz_score >= 70:
                        quizzes_passed_count += 1
        if quizzes_passed_count != total_quizzes_in_training:
            all_quizzes_passed = False
    
    if all_videos_watched and all_quizzes_passed:
        if not any(c['username'] == current_username and c['training_title'] == training_title for c in certificates.values()):
            certificate_id = str(uuid.uuid4())
            certificates[certificate_id] = {
                'completion_date': datetime.date.today().isoformat(),
                'training_title': training_title,
                'username': current_username
            }
            flash(f"Congratulations! You completed '{training_title}' and earned a certificate!", 'success')

    return redirect(url_for('user.user_training_details', training_title=training_title))

@user_bp.route('/take_quiz/<training_title>/<video_filename>/<int:quiz_index>', methods=['GET', 'POST'])
@login_required(role='user')
def user_take_quiz(training_title, video_filename, quiz_index):
    training_data = trainings.get(training_title)
    if not training_data:
        flash("Training not found.", 'error')
        return redirect(url_for('user.user_dashboard'))

    video_info = next((v for v in training_data['videos'] if v['actual_filename'] == video_filename), None)
    if not video_info:
        flash("Video not found in this training.", 'error')
        return redirect(url_for('user.user_training_details', training_title=training_title))

    if not (0 <= quiz_index < len(video_info.get('video_quizzes', []))):
        flash("Quiz not found.", 'error')
        return redirect(url_for('user.user_training_details', training_title=training_title))

    quiz = video_info['video_quizzes'][quiz_index]
    current_username = get_current_username()
    user_prog = get_user_training_progress(current_username, training_title)

    if request.method == 'POST':
        score = 0
        if quiz['type'] == 'single_mcq':
            try:
                user_answer = int(request.form.get('answer'))
                if user_answer == quiz['answer']:
                    score = 100
            except (ValueError, TypeError):
                pass # Invalid input, score remains 0
        elif quiz['type'] == 'multiple_mcq':
            user_answers = [int(x) for x in request.form.getlist('answers') if x.isdigit()]
            correct_options = quiz['correct_options']
            
            # Simple scoring: 100 if all correct and no incorrect selected
            if set(user_answers) == set(correct_options):
                score = 100
            else:
                score = 0 # Any deviation means 0 for now
        elif quiz['type'] == 'paragraph':
            user_answer_text = sanitize_input(request.form.get('answer_text', '')).lower()
            correct_answer_text = quiz['correct_answer_text'].lower()
            
            # Simple check for exact match or significant keyword presence.
            # In a real app, use NLP techniques for robust scoring.
            if user_answer_text == correct_answer_text or \
               (len(user_answer_text.split()) > 0 and all(word in user_answer_text for word in correct_answer_text.split())):
                score = 100
            else:
                score = 0 # For simplicity, a simple match for now

        # Store score
        if video_filename not in user_prog['video_quiz_scores']:
            user_prog['video_quiz_scores'][video_filename] = {}
        user_prog['video_quiz_scores'][video_filename][quiz_index] = score

        if score >= 70:
            flash(f"Quiz completed! You scored {score}%. You passed!", 'success')
        else:
            flash(f"Quiz completed! You scored {score}%. You need 70% to pass. Please retry.", 'error')
        
        # Check for overall training completion after quiz
        total_videos = len(training_data['videos'])
        videos_watched = len(user_prog['videos_watched'])

        all_videos_watched = (videos_watched == total_videos and total_videos > 0)
        
        all_quizzes_passed = True
        total_quizzes_in_training = sum(len(v.get('video_quizzes', [])) for v in training_data['videos'])
        
        if total_quizzes_in_training > 0:
            quizzes_passed_count = 0
            for vid_info in training_data['videos']:
                vid_filename = vid_info['actual_filename']
                if vid_filename in user_prog['video_quiz_scores']:
                    for quiz_score in user_prog['video_quiz_scores'][vid_filename].values():
                        if quiz_score >= 70:
                            quizzes_passed_count += 1
            if quizzes_passed_count != total_quizzes_in_training:
                all_quizzes_passed = False
        
        if all_videos_watched and all_quizzes_passed:
            if not any(c['username'] == current_username and c['training_title'] == training_title for c in certificates.values()):
                certificate_id = str(uuid.uuid4())
                certificates[certificate_id] = {
                    'completion_date': datetime.date.today().isoformat(),
                    'training_title': training_title,
                    'username': current_username
                }
                flash(f"Congratulations! You completed '{training_title}' and earned a certificate!", 'success')

        return redirect(url_for('user.user_training_details', training_title=training_title))

    return render_template('user_take_quiz.html',
                           training_title=training_title,
                           video_filename=video_filename,
                           quiz_index=quiz_index,
                           quiz=quiz,
                           current_username=current_username,
                           previous_score=user_prog['video_quiz_scores'].get(video_filename, {}).get(quiz_index))

@user_bp.route('/view_certificate/<certificate_id>')
@login_required(role='user')
def user_view_certificate(certificate_id):
    certificate = certificates.get(certificate_id)
    if not certificate or certificate['username'] != get_current_username():
        flash("Certificate not found or you don't have permission to view it.", 'error')
        return redirect(url_for('user.user_dashboard'))
    
    return render_template('user_view_certificate.html', certificate=certificate)

@user_bp.route('/uploads/<folder_name>/<filename>')
def uploaded_file_user(folder_name, filename): # Renamed for clarity, but could be shared
    return send_from_directory(os.path.join(current_app.config['UPLOAD_FOLDER'], folder_name), filename)