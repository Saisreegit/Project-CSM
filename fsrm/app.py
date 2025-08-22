from flask import Flask
from config import UPLOAD_FOLDER, SECRET_KEY, SMTP_SERVER, SMTP_PORT, EMAIL_SENDER, EMAIL_PASSWORD
app = Flask(__name__)
app.secret_key = SECRET_KEY
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from flask import request, render_template, send_from_directory, redirect, url_for, jsonify, flash, g
from datetime import datetime
import helpers
from helpers import read_docx  # only if you're using read_docx
#helpers.some_function()

from . import fsrm_bp # This is the blueprint you defined in fsrm/init.py
@fsrm_bp.route('/fsrm_home')
def fsrm_home():
    return render_template('fsrm/fsrm_home.html')

# Import functions from helpers.py
from helpers import (
    log_action, detect_type, save_file, send_email,
    read_excel_sheets_with_names, read_docx, read_ppt,
    compare_documents_side_by_side
)
# --- Flask App Setup ---
app.secret_key = SECRET_KEY

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- IMPORTANT: Data Storage ---
# This dictionary stores all document and comment data IN MEMORY.
# !!! CRITICAL ISSUE: ALL DATA IS LOST WHEN THE FLASK SERVER RESTARTS. !!!
# For persistent data, a database (like SQLite, PostgreSQL, etc.) is REQUIRED.
reviews = {}

# --- In-memory Audit Log (for demonstration purposes, also lost on restart) ---
audit_log = [] # Simple log of actions

# --- Flask Routes ---

@fsrm_bp.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serves uploaded files."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@fsrm_bp.route('/index')
def fsrm_index():
    """Default route, redirect to owner dashboard."""
    return redirect(url_for('fsrm.owner_dashboard'))

@fsrm_bp.route('/owner_dashboard')
def owner_dashboard():
    """Owner's dashboard (main page for uploading and viewing their documents)."""
    current_owner_email = request.args.get('email', '')
    owner_docs = {doc_id: doc for doc_id, doc in reviews.items() if doc['owner_email'] == current_owner_email}
    return render_template("owner_dashboard.html", reviews=owner_docs, request=request, current_owner_email=current_owner_email)

@fsrm_bp.route('/reviewer_dashboard')
def reviewer_dashboard():
    """Reviewer's dashboard (lists documents assigned to a specific reviewer)."""
    reviewer_email = request.args.get('email')
    if not reviewer_email:
        flash("Reviewer email is required to view this dashboard. Please use a URL like `/reviewer_dashboard?email=your_email@example.com`", "info")
        return render_template("reviewer_dashboard.html", reviewer_docs={}, reviewer_email="")

    reviewer_docs = {doc_id: doc for doc_id, doc in reviews.items() if doc['assigned_reviewer_email'] == reviewer_email}
    return render_template("reviewer_dashboard.html", reviewer_docs=reviewer_docs, reviewer_email=reviewer_email, request=request)


@fsrm_bp.route('/upload', methods=['POST'])
def upload():
    """Handles document upload by the owner."""
    owner_name = request.form.get('owner_name', '').strip()
    owner_email = request.form.get('owner_email', '').strip()
    assigned_reviewer_email = request.form.get('assigned_reviewer_email', '').strip()

    if not all([owner_name, owner_email, assigned_reviewer_email]):
        flash("All owner name, email, and reviewer email are required.", "error")
        return redirect(url_for('owner_dashboard', email=owner_email))

    if 'file' not in request.files:
        flash("No file part in the request.", "error")
        return redirect(url_for('owner_dashboard', email=owner_email))

    f = request.files['file']
    if f.filename == '':
        flash("No selected file.", "error")
        return redirect(url_for('owner_dashboard', email=owner_email))

    fname, path = save_file(f, app.config['UPLOAD_FOLDER']) # Pass UPLOAD_FOLDER
    ftype = detect_type(fname)
    doc_id = f"{fname.replace('.', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}" # More unique ID

    reviews[doc_id] = {
        'doc_id': doc_id,
        'filename': fname,
        'path': path,
        'type': ftype,
        'version': "1.0",
        'versions': [{'version_id': "1.0", 'filename': fname, 'path': path, 'timestamp': datetime.now().isoformat()}], # Store historical versions
        'status': 'Pending Review', # Initial status
        'owner_name': owner_name,
        'owner_email': owner_email,
        'assigned_reviewer_email': assigned_reviewer_email,
        'comments': [], # List to store review comments
        'doc_chats': [], # NEW: List to store document-level chat messages
        'deadline': None, # Initial deadline for the document, can be set by reviewer
        'needs_re_review': False # New flag to highlight if document needs re-review
    }
    log_action(audit_log, f"Document '{fname}' ({doc_id}) uploaded by {owner_name} ({owner_email}). Assigned to {assigned_reviewer_email}.")
    flash(f"Document '{fname}' uploaded successfully and assigned to {assigned_reviewer_email}.", "success")

    # --- THE KEY CHANGE FOR THE EMAIL LINK IS HERE ---
    # Instead of linking to the specific document_view, link to the general reviewer_dashboard.
    # This prevents "Document not found" errors if the server restarts and data is lost.
    reviewer_link = url_for('reviewer_dashboard', email=assigned_reviewer_email, _external=True)
    subject = f"[New Document Available] {fname}"
    body = f"""
Dear Reviewer,

A new document "{fname}" has been uploaded by {owner_name} for your review.
It is now available on your reviewer dashboard.

Please access your dashboard here: {reviewer_link}

Regards,
Document Owner
"""
    send_email(assigned_reviewer_email, subject, body, SMTP_SERVER, SMTP_PORT, EMAIL_SENDER, EMAIL_PASSWORD)

    # Redirect owner back to their dashboard
    return redirect(url_for('owner_dashboard', email=owner_email))


@fsrm_bp.route('/edit_document/<doc_id>', methods=['GET', 'POST'])
def edit_document(doc_id):
    doc = reviews.get(doc_id)
    if not doc:
        flash("Document not found. It might have been cleared due to server restart.", "error")
        return redirect(url_for('owner_dashboard', email=request.args.get('email', '')))

    current_owner_email = request.args.get('email')

    # Basic Authorization: Insecure for production, replace with proper auth.
    if not (current_owner_email == doc['owner_email']):
        flash("Access Denied: You are not authorized to edit this document.", "error")
        return redirect(url_for('owner_dashboard', email=current_owner_email))

    if request.method == 'POST':
        original_filename = doc['filename']
        original_path = doc['path']
        original_version = doc['version']
        original_assigned_reviewer_email = doc['assigned_reviewer_email']

        doc['owner_name'] = request.form.get('owner_name', doc['owner_name']).strip()
        doc['owner_email'] = request.form.get('owner_email', doc['owner_email']).strip()
        new_assigned_reviewer_email = request.form.get('assigned_reviewer_email', doc['assigned_reviewer_email']).strip()


        # Handle file re-upload
        if 'file' in request.files and request.files['file'].filename != '':
            f = request.files['file']
            # Ensure 'versions' list exists
            if 'versions' not in doc:
                doc['versions'] = []
            
            # Add current live version to history if not already there (prevents duplicates if edited multiple times without re-upload)
            current_live_version_details = {
                'version_id': doc['version'],
                'filename': doc['filename'],
                'path': doc['path'],
                'timestamp': datetime.now().isoformat() # Use current time for consistency, or store when it became live
            }
            # Check if this exact version_id is already in versions list to prevent duplication on multiple edits without file upload
            if not any(v['version_id'] == current_live_version_details['version_id'] for v in doc['versions']):
                 doc['versions'].append(current_live_version_details)


            new_fname, new_path = save_file(f, app.config['UPLOAD_FOLDER'])
            new_ftype = detect_type(new_fname)

            # Increment version
            try:
                new_version = f"{float(original_version) + 0.1:.1f}"
            except ValueError:
                new_version = "1.0" # Reset if version was malformed

            doc['filename'] = new_fname
            doc['path'] = new_path
            doc['type'] = new_ftype
            doc['version'] = new_version # Update current live version
            doc['status'] = 'Pending Re-Review (New Version)' # Update status for re-review
            doc['needs_re_review'] = True # Flag for re-review - SET TO TRUE WHEN RE-UPLOADING

            # Add new version to history
            doc['versions'].append({
                'version_id': new_version,
                'filename': new_fname,
                'path': new_path,
                'timestamp': datetime.now().isoformat()
            })

            flash(f"Document '{new_fname}' updated to version {doc['version']}.", "success")
            log_action(audit_log, f"Document '{doc_id}' updated with new file '{new_fname}' by {doc['owner_name']}. New version: {doc['version']}.")

            # Send email to reviewer with link to the updated document on their dashboard
            reviewer_link = url_for('reviewer_dashboard', email=new_assigned_reviewer_email, _external=True)
            subject = f"[Document Re-uploaded] {doc['filename']} (Version {doc['version']})"
            body = f"""
Dear Reviewer,

A new version ({doc['version']}) of the document "{doc['filename']}" has been uploaded by {doc['owner_name']} for your review.
It is now available on your reviewer dashboard and is marked as 'Needs Re-Review'.

Please access your dashboard here: {reviewer_link}

Regards,
Document Owner
"""
            send_email(new_assigned_reviewer_email, subject, body, SMTP_SERVER, SMTP_PORT, EMAIL_SENDER, EMAIL_PASSWORD)


        # Check if assigned reviewer changed
        if new_assigned_reviewer_email != original_assigned_reviewer_email:
            doc['assigned_reviewer_email'] = new_assigned_reviewer_email
            flash(f"Assigned reviewer changed to {new_assigned_reviewer_email}.", "info")
            log_action(audit_log, f"Document '{doc_id}' assigned reviewer changed from {original_assigned_reviewer_email} to {new_assigned_reviewer_email}.")

            # Notify new reviewer
            reviewer_link = url_for('reviewer_dashboard', email=new_assigned_reviewer_email, _external=True) # Changed link
            subject = f"[Document Assigned/Reassigned] {doc['filename']}"
            body = f"""
Dear Reviewer,

The document "{doc['filename']}" has been assigned to you for review (or reassigned from another reviewer).
It is now available on your reviewer dashboard.

Please access your dashboard here: {reviewer_link}

Regards,
Document Owner
"""
            send_email(new_assigned_reviewer_email, subject, body, SMTP_SERVER, SMTP_PORT, EMAIL_SENDER, EMAIL_PASSWORD)

            # Optionally, notify old reviewer if they were removed
            if original_assigned_reviewer_email and original_assigned_reviewer_email != new_assigned_reviewer_email:
                subject_old = f"[Document Reassignment Notice] {doc['filename']}"
                body_old = f"""
Dear Reviewer,

Please note that the document "{doc['filename']}" has been reassigned to another reviewer. You are no longer responsible for its review.

Regards,
Document Owner
"""
                send_email(original_assigned_reviewer_email, subject_old, body_old, SMTP_SERVER, SMTP_PORT, EMAIL_SENDER, EMAIL_PASSWORD)

        update_reason = request.form.get('update_reason', '').strip()
        if update_reason:
            # Add a "system" comment about the update
            # Generate a new unique ID for the system comment within the document's comments list
            new_comment_id = max([c['comment_id'] for c in doc['comments']]) + 1 if doc['comments'] else 1
            doc['comments'].append({
                'comment_id': new_comment_id,
                'comment_author_name': 'System',
                'comment_author_email': 'system@example.com',
                'comment_owner_name': doc['owner_name'],
                'comment_owner_email': doc['owner_email'],
                'sheet': None, 'section_page_number': None,
                'issue': f"Document updated by owner. Reason: {update_reason}",
                'priority': 'Informational',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'Resolved', # System comments are 'resolved' by nature
                'start_date': None, 'actual_start_date': None,
                'actual_end_date': None, 'end_date': None,
            })
            log_action(audit_log, f"System comment added to {doc_id}: Document updated. Reason: {update_reason}.")
        else:
            flash("Please provide a reason for the update.", "warning")


        flash("Document details updated.", "success")
        return redirect(url_for('document_view', doc_id=doc_id, role='owner', email=current_owner_email))

    return render_template("edit_document.html", doc=doc, request=request, current_owner_email=current_owner_email)


@fsrm_bp.route('/document_view/<doc_id>')
def document_view(doc_id):
    """Displays a single document for review or owner view."""
    doc = reviews.get(doc_id)
    if not doc:
        flash("Document not found. It might have been cleared due to server restart.", "error")
        # If the document is not found (e.g., after server restart), redirect to appropriate dashboard.
        # This is a fallback due to in-memory data.
        role = request.args.get('role')
        email = request.args.get('email')
        if role == 'reviewer':
            return redirect(url_for('reviewer_dashboard', email=email))
        else: # Default to owner dashboard
            return redirect(url_for('owner_dashboard', email=email))

    role = request.args.get('role')
    current_user_email = request.args.get('email')

    # Basic authorization check
    if role == 'owner' and current_user_email != doc['owner_email']:
        flash("Access Denied: You are not the owner of this document.", "error")
        return redirect(url_for('owner_dashboard', email=current_user_email))
    elif role == 'reviewer' and current_user_email != doc['assigned_reviewer_email']:
        flash("Access Denied: This document is not assigned to you for review.", "error")
        return redirect(url_for('reviewer_dashboard', email=current_user_email))
    elif not role or not current_user_email:
        flash("Access Denied: Missing role or email in URL.", "error")
        return redirect(url_for('index')) # Or a login page

    # Get selected versions for comparison
    # Default to first available version for left panel, current live version for right panel
    version_a_id = request.args.get('version_a', doc['versions'][0]['version_id'] if doc['versions'] else None)
    version_b_id = request.args.get('version_b', doc['version']) 

    # Get selected sheets for comparison (relevant only for Excel)
    selected_sheet_a = request.args.get('sheet_a')
    selected_sheet_b = request.args.get('sheet_b')

    version_a_info = next((v for v in doc['versions'] if v['version_id'] == version_a_id), None)
    version_b_info = next((v for v in doc['versions'] if v['version_id'] == version_b_id), None)

    left_panel_html = ""
    right_panel_html = ""
    comparison_mode = False
    
    # Get sheet names for dropdowns if Excel
    sheet_names_a = []
    sheet_names_b = []
    if doc['type'] == 'excel' and version_a_info:
        _, sheet_names_a = read_excel_sheets_with_names(version_a_info['path'])
        # Set default selected sheet if not already in URL
        if not selected_sheet_a and sheet_names_a:
            selected_sheet_a = sheet_names_a[0]
    if doc['type'] == 'excel' and version_b_info:
        _, sheet_names_b = read_excel_sheets_with_names(version_b_info['path'])
        if not selected_sheet_b and sheet_names_b:
            selected_sheet_b = sheet_names_b[0]


    if version_a_info and version_b_info:
        comparison_mode = True
        left_panel_html, right_panel_html = compare_documents_side_by_side(
            doc['type'],
            version_a_info['path'],
            version_b_info['path'],
            selected_sheet_a=selected_sheet_a, # Pass selected sheets
            selected_sheet_b=selected_sheet_b  # Pass selected sheets
        )
    else:
        # Fallback if no specific versions are selected or available, just show current version as preview
        if doc['type'] == 'excel':
            excel_data, all_sheet_names = read_excel_sheets_with_names(doc['path'])
            # Default to first sheet for single preview
            sheet_to_preview = selected_sheet_a if selected_sheet_a else (all_sheet_names[0] if all_sheet_names else None)
            sheet_data = excel_data.get(sheet_to_preview, []) if sheet_to_preview else []

            left_panel_html = f"<h3>Current Document Preview (Sheet: {sheet_to_preview})</h3><div class='excel-sheet-wrapper'><table class='excel-table'>"
            if sheet_data:
                for row in sheet_data:
                    left_panel_html += "<tr>"
                    for cell in row:
                        left_panel_html += f"<td>{str(cell) if cell is not None else ''}</td>"
                    left_panel_html += "</tr>"
            else:
                left_panel_html += "<tr><td>No data in this sheet or sheet not found.</td></tr>"
            left_panel_html += "</table></div>"
            right_panel_html = "<p>Select another version to compare.</p>" # No right panel if no comparison
        elif doc['type'] == 'word':
            word_paras = read_docx(doc['path'])
            left_panel_html = "<h3>Current Document Preview</h3><div class='word-preview-content'>"
            for para in word_paras:
                left_panel_html += f"<p>{para}</p>"
            left_panel_html += "</div>"
            right_panel_html = "<p>Select another version to compare.</p>"
        elif doc['type'] == 'pdf':
            left_panel_html = f"<embed src='{url_for('uploaded_file', filename=doc['filename'])}' type='application/pdf' width='100%' height='600px' />"
            right_panel_html = "<p>Select another version to compare.</p>"
        elif doc['type'] == 'ppt':
            ppt_slides = read_ppt(doc['path'])
            left_html = "<h3>Current Document Preview</h3>"
            for slide in ppt_slides:
                left_html += f"<div class='ppt-slide'><h4>Slide {slide['slide_number']}:</h4>"
                for text_line in slide['text']: left_html += f"<p>{text_line}</p>"
                left_html += "</div>"
            right_panel_html = "<p>Select another version to compare.</p>"
        else:
            left_panel_html = f"<p>No preview available for this file type.</p><p><a href='{url_for('uploaded_file', filename=doc['filename'])}' download>Download Original File</a></p>"
            right_panel_html = "<p>No preview available or selection possible.</p>"


    return render_template("document_view.html", doc=doc, role=role, current_user_email=current_user_email, request=request,
                                  left_panel_html=left_panel_html,
                                  right_panel_html=right_panel_html,
                                  selected_version_a=version_a_id,
                                  selected_version_b=version_b_id,
                                  comparison_mode=comparison_mode,
                                  doc_type=doc['type'], # Pass doc_type for conditional rendering
                                  sheet_names_a=sheet_names_a,
                                  sheet_names_b=sheet_names_b,
                                  selected_sheet_a=selected_sheet_a,
                                  selected_sheet_b=selected_sheet_b)


@fsrm_bp.route('/add_comment/<doc_id>', methods=['POST'])
def add_comment(doc_id):
    """Adds one or more new comments to a document."""
    doc = reviews.get(doc_id)
    if not doc:
        flash("Document not found.", "error")
        return redirect(url_for('owner_dashboard')) # Fallback for missing doc

    current_user_email = request.args.get('email')
    comments_added_count = 0

    # Retrieve all submitted comments from the form (using name="comments[idx][field]")
    # Flask's request.form does not directly give nested lists, so we parse manually
    comment_data = {}
    for key, value in request.form.items():
        if key.startswith('comments['):
            parts = key.split('[')
            idx = int(parts[1][:-1]) # Get index (e.g., '0' from 'comments[0]')
            field = parts[2][:-1]    # Get field name (e.g., 'issue' from 'comments[0][issue]')

            if idx not in comment_data:
                comment_data[idx] = {}
            comment_data[idx][field] = value.strip()

    if not comment_data:
        flash("No comments submitted.", "warning")
        return redirect(url_for('document_view', doc_id=doc_id, role=request.args.get('role'), email=current_user_email))

    for idx in sorted(comment_data.keys()):
        comment_entry = comment_data[idx]

        comment_author_name = comment_entry.get('comment_author_name', '').strip()
        comment_author_email = comment_entry.get('comment_author_email', '').strip()
        sheet = comment_entry.get('sheet', None)
        section_page_number = comment_entry.get('section_page_number', None)
        issue = comment_entry.get('issue', '').strip()
        priority = comment_entry.get('priority', 'Medium').strip()
        start_date = comment_entry.get('start_date') if comment_entry.get('start_date') else None
        end_date = comment_entry.get('end_date') if comment_entry.get('end_date') else None

        if not all([comment_author_name, comment_author_email, issue]):
            flash(f"Comment {idx+1}: Author name, email, and issue are required.", "error")
            continue # Skip this comment and try the next

        new_comment_id = max([c['comment_id'] for c in doc['comments']]) + 1 if doc['comments'] else 1

        doc['comments'].append({
            'comment_id': new_comment_id,
            'comment_author_name': comment_author_name,
            'comment_author_email': comment_author_email,
            'comment_owner_name': doc['owner_name'], # Store owner name with comment for context
            'comment_owner_email': doc['owner_email'], # Store owner email with comment for context
            'sheet': sheet if sheet else None,
            'section_page_number': section_page_number if section_page_number else None,
            'issue': issue,
            'priority': priority,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'Open', # New comments are 'Open' by default
            'start_date': start_date,
            'actual_start_date': None, # Set when reviewer starts
            'actual_end_date': None, # Set when reviewer finishes
            'end_date': end_date,
        })
        comments_added_count += 1
        log_action(audit_log, f"Comment {new_comment_id} added to document '{doc_id}' by {comment_author_name}. Issue: {issue[:50]}...")

    if comments_added_count > 0:
        flash(f"{comments_added_count} new comment(s) added successfully.", "success")
        doc['status'] = 'Under Review' # Update document status
        # Notify owner about new comments
        owner_link = url_for('document_view', doc_id=doc_id, role='owner', email=doc['owner_email'], _external=True)
        subject = f"[New Comments] {doc['filename']} has new comments"
        body = f"""
Dear {doc['owner_name']},

The reviewer ({doc['assigned_reviewer_email']}) has added new comment(s) to your document "{doc['filename']}".
The document status is now '{doc['status']}'.

You can view the document and comments here: {owner_link}

Regards,
Review System
"""
        send_email(doc['owner_email'], subject, body, SMTP_SERVER, SMTP_PORT, EMAIL_SENDER, EMAIL_PASSWORD)
    else:
        flash("No valid comments were added.", "warning")

    return redirect(url_for('document_view', doc_id=doc_id, role=request.args.get('role'), email=current_user_email))


@fsrm_bp.route('/update_comment_status/<doc_id>/<int:comment_id>', methods=['POST'])
def update_comment_status(doc_id, comment_id):
    """Updates the status of a specific comment."""
    doc = reviews.get(doc_id)
    if not doc:
        flash("Document not found.", "error")
        return redirect(url_for('owner_dashboard'))

    current_user_email = request.args.get('email')
    comment = next((c for c in doc['comments'] if c['comment_id'] == comment_id), None)

    if not comment:
        flash("Comment not found.", "error")
        return redirect(url_for('document_view', doc_id=doc_id, role=request.args.get('role'), email=current_user_email))

    new_status = request.form.get('status')
    if not new_status or new_status not in ['Open', 'In Progress', 'Resolved', 'Closed']:
        flash("Invalid status provided.", "error")
        return redirect(url_for('document_view', doc_id=doc_id, role=request.args.get('role'), email=current_user_email))

    original_status = comment['status']
    comment['status'] = new_status
    comment['actual_start_date'] = request.form.get('actual_start_date', comment.get('actual_start_date'))
    comment['actual_end_date'] = request.form.get('actual_end_date', comment.get('actual_end_date'))

    if new_status == 'In Progress' and not comment['actual_start_date']:
        comment['actual_start_date'] = datetime.now().strftime('%Y-%m-%d')
    if new_status in ['Resolved', 'Closed'] and not comment['actual_end_date']:
        comment['actual_end_date'] = datetime.now().strftime('%Y-%m-%d')

    flash(f"Comment {comment_id} status updated to '{new_status}'.", "success")
    log_action(audit_log, f"Comment {comment_id} in '{doc_id}' status changed from '{original_status}' to '{new_status}' by {current_user_email}.")

    # Notify relevant parties
    subject = f"[Comment Status Update] Doc: {doc['filename']}, Comment ID: {comment_id} is now {new_status}"
    body = f"""
Dear {doc['owner_name']} and {doc['assigned_reviewer_email']},

The status of comment ID {comment_id} in document "{doc['filename']}" has been updated to '{new_status}' by {current_user_email}.
Issue: {comment['issue']}

You can view the document and comments here: {url_for('document_view', doc_id=doc_id, role='owner', email=doc['owner_email'], _external=True)}

Regards,
Review System
"""
    send_email(doc['owner_email'], subject, body, SMTP_SERVER, SMTP_PORT, EMAIL_SENDER, EMAIL_PASSWORD)
    if doc['owner_email'] != doc['assigned_reviewer_email']: # Avoid sending duplicate if owner is also reviewer
        send_email(doc['assigned_reviewer_email'], subject, body, SMTP_SERVER, SMTP_PORT, EMAIL_SENDER, EMAIL_PASSWORD)

    return redirect(url_for('document_view', doc_id=doc_id, role=request.args.get('role'), email=current_user_email))

@fsrm_bp.route('/delete_comment/<doc_id>/<int:comment_id>', methods=['POST'])
def delete_comment(doc_id, comment_id):
    doc = reviews.get(doc_id)
    if not doc:
        flash("Document not found.", "error")
        return redirect(url_for('owner_dashboard'))

    current_user_email = request.args.get('email')
    
    # Simple authorization: Only the comment author or the owner can delete
    comment_to_delete = next((c for c in doc['comments'] if c['comment_id'] == comment_id), None)
    
    if not comment_to_delete:
        flash("Comment not found.", "error")
        return redirect(url_for('document_view', doc_id=doc_id, role=request.args.get('role'), email=current_user_email))

    if not (current_user_email == comment_to_delete['comment_author_email'] or current_user_email == doc['owner_email'] or current_user_email == doc['assigned_reviewer_email']):
        flash("Access Denied: You are not authorized to delete this comment.", "error")
        return redirect(url_for('document_view', doc_id=doc_id, role=request.args.get('role'), email=current_user_email))

    doc['comments'] = [c for c in doc['comments'] if c['comment_id'] != comment_id]
    flash(f"Comment {comment_id} deleted.", "success")
    log_action(audit_log, f"Comment {comment_id} deleted from document '{doc_id}' by {current_user_email}.")

    # Notify relevant parties about deletion
    subject = f"[Comment Deleted] Doc: {doc['filename']}, Comment ID: {comment_id} Deleted"
    body = f"""
Dear {doc['owner_name']} and {doc['assigned_reviewer_email']},

Comment ID {comment_id} in document "{doc['filename']}" has been deleted by {current_user_email}.
The deleted issue was: {comment_to_delete['issue']}

You can view the document and remaining comments here: {url_for('document_view', doc_id=doc_id, role='owner', email=doc['owner_email'], _external=True)}

Regards,
Review System
"""
    send_email(doc['owner_email'], subject, body, SMTP_SERVER, SMTP_PORT, EMAIL_SENDER, EMAIL_PASSWORD)
    if doc['owner_email'] != doc['assigned_reviewer_email']:
        send_email(doc['assigned_reviewer_email'], subject, body, SMTP_SERVER, SMTP_PORT, EMAIL_SENDER, EMAIL_PASSWORD)

    return redirect(url_for('document_view', doc_id=doc_id, role=request.args.get('role'), email=current_user_email))


@fsrm_bp.route('/submit_review/<doc_id>', methods=['POST'])
def submit_review(doc_id):
    """Allows reviewer to submit their review."""
    doc = reviews.get(doc_id)
    if not doc:
        flash("Document not found.", "error")
        return redirect(url_for('reviewer_dashboard', email=request.args.get('email', '')))

    reviewer_email = request.args.get('email')
    if reviewer_email != doc['assigned_reviewer_email']:
        flash("Access Denied: This document is not assigned to you for review.", "error")
        return redirect(url_for('reviewer_dashboard', email=reviewer_email))

    new_status = request.form.get('new_status')
    feedback = request.form.get('feedback', '').strip()

    if not new_status:
        flash("Please select a new status for the document.", "error")
        return redirect(url_for('document_view', doc_id=doc_id, role='reviewer', email=reviewer_email))
    
    # Valid transitions
    valid_transitions = {
        'Pending Review': ['Under Review', 'Approved', 'Rejected'],
        'Under Review': ['Approved', 'Rejected', 'Needs Re-Review'],
        'Pending Re-Review (New Version)': ['Under Review', 'Approved', 'Rejected', 'Needs Re-Review'],
        'Approved': [],
        'Rejected': [],
        'Needs Re-Review': ['Under Review', 'Approved', 'Rejected'] # After owner makes changes
    }

    if new_status not in valid_transitions.get(doc['status'], []):
        flash(f"Invalid status transition from '{doc['status']}' to '{new_status}'.", "error")
        return redirect(url_for('document_view', doc_id=doc_id, role='reviewer', email=reviewer_email))

    original_status = doc['status']
    doc['status'] = new_status
    doc['needs_re_review'] = False # Reset this flag once review is submitted

    if feedback:
        # Add a "system" comment about the review submission
        new_comment_id = max([c['comment_id'] for c in doc['comments']]) + 1 if doc['comments'] else 1
        doc['comments'].append({
            'comment_id': new_comment_id,
            'comment_author_name': doc['assigned_reviewer_email'], # Reviewer is the author of this 'system' feedback
            'comment_author_email': doc['assigned_reviewer_email'],
            'comment_owner_name': doc['owner_name'],
            'comment_owner_email': doc['owner_email'],
            'sheet': None, 'section_page_number': None,
            'issue': f"Review submitted by {doc['assigned_reviewer_email']}. Document status changed to '{new_status}'. Reviewer feedback: {feedback}",
            'priority': 'Informational',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'Resolved', # System comments are 'resolved'
            'start_date': None, 'actual_start_date': None,
            'actual_end_date': None, 'end_date': None,
        })
        log_action(audit_log, f"Review submitted for '{doc_id}' by {reviewer_email}. Status: {new_status}. Feedback: {feedback[:50]}...")
        flash(f"Review submitted. Document status changed to '{new_status}'.", "success")
    else:
        flash(f"Document status changed to '{new_status}'. Please consider providing feedback.", "success")
        log_action(audit_log, f"Review submitted for '{doc_id}' by {reviewer_email}. Status: {new_status}.")

    # Notify owner
    owner_link = url_for('document_view', doc_id=doc_id, role='owner', email=doc['owner_email'], _external=True)
    subject = f"[Document Status Update] Your document '{doc['filename']}' is now '{doc['status']}'"
    body = f"""
Dear {doc['owner_name']},

The review for your document "{doc['filename']}" has been submitted by {doc['assigned_reviewer_email']}.
The document status is now: '{doc['status']}'.

Reviewer Feedback:
{feedback if feedback else 'No specific feedback provided.'}

You can view the document and all comments here: {owner_link}

Regards,
Review System
"""
    send_email(doc['owner_email'], subject, body, SMTP_SERVER, SMTP_PORT, EMAIL_SENDER, EMAIL_PASSWORD)

    return redirect(url_for('reviewer_dashboard', email=reviewer_email))


@fsrm_bp.route('/set_deadline/<doc_id>', methods=['POST'])
def set_deadline(doc_id):
    doc = reviews.get(doc_id)
    if not doc:
        return jsonify({'success': False, 'message': 'Document not found.'}), 404

    current_user_email = request.args.get('email')
    if current_user_email != doc['assigned_reviewer_email']:
        return jsonify({'success': False, 'message': 'Access Denied: Only the assigned reviewer can set the deadline.'}), 403

    deadline_str = request.form.get('deadline')
    try:
        # Validate and store deadline (ISO format for consistency)
        deadline_date = datetime.strptime(deadline_str, '%Y-%m-%d').date()
        doc['deadline'] = deadline_date.isoformat()
        log_action(audit_log, f"Deadline for '{doc_id}' set to {deadline_date} by {current_user_email}.")
        flash(f"Deadline for document '{doc['filename']}' set to {deadline_date.strftime('%Y-%m-%d')}.", "success")

        # Notify owner about the new deadline
        owner_link = url_for('document_view', doc_id=doc_id, role='owner', email=doc['owner_email'], _external=True)
        subject = f"[Deadline Set] Document: {doc['filename']}"
        body = f"""
Dear {doc['owner_name']},

A deadline for your document "{doc['filename']}" has been set by the reviewer ({doc['assigned_reviewer_email']}).
The new deadline is: {deadline_date.strftime('%Y-%m-%d')}.

You can view the document here: {owner_link}

Regards,
Review System
"""
        send_email(doc['owner_email'], subject, body, SMTP_SERVER, SMTP_PORT, EMAIL_SENDER, EMAIL_PASSWORD)

        return redirect(url_for('document_view', doc_id=doc_id, role='reviewer', email=current_user_email))
    except ValueError:
        flash("Invalid date format. Please use YYYY-MM-DD.", "error")
        return redirect(url_for('document_view', doc_id=doc_id, role='reviewer', email=current_user_email))

@fsrm_bp.route('/add_doc_chat/<doc_id>', methods=['POST'])
def add_doc_chat(doc_id):
    """Adds a chat message to the document's general chat."""
    doc = reviews.get(doc_id)
    if not doc:
        flash("Document not found.", "error")
        return redirect(url_for('owner_dashboard'))

    current_user_email = request.args.get('email')
    current_user_role = request.args.get('role')
    message = request.form.get('message', '').strip()
    sender_name = request.form.get('sender_name', 'Anonymous').strip()

    if not message:
        flash("Message cannot be empty.", "error")
        return redirect(url_for('document_view', doc_id=doc_id, role=current_user_role, email=current_user_email))
    
    # Basic authorization
    if not (current_user_email == doc['owner_email'] or current_user_email == doc['assigned_reviewer_email']):
        flash("Access Denied: You are not authorized to chat on this document.", "error")
        return redirect(url_for('index'))

    doc['doc_chats'].append({
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'sender_email': current_user_email,
        'sender_name': sender_name,
        'message': message
    })
    flash("Chat message added.", "success")
    log_action(audit_log, f"Chat message added to '{doc_id}' by {sender_name} ({current_user_email}).")

    # Notify the other party
    recipient_email = doc['owner_email'] if current_user_email == doc['assigned_reviewer_email'] else doc['assigned_reviewer_email']
    recipient_role = 'owner' if current_user_email == doc['assigned_reviewer_email'] else 'reviewer'

    doc_link = url_for('document_view', doc_id=doc_id, role=recipient_role, email=recipient_email, _external=True)
    subject = f"[Document Chat] New message in '{doc['filename']}'"
    body = f"""
Dear {'Owner' if recipient_role == 'owner' else 'Reviewer'},

You have a new message in the chat for document "{doc['filename']}" from {sender_name}:

"{message}"

You can view the document and chat here: {doc_link}

Regards,
Review System
"""
    send_email(recipient_email, subject, body, SMTP_SERVER, SMTP_PORT, EMAIL_SENDER, EMAIL_PASSWORD)

    return redirect(url_for('document_view', doc_id=doc_id, role=current_user_role, email=current_user_email))


@fsrm_bp.route('/audit_log')
def view_audit_log():
    """Displays the in-memory audit log."""
    return render_template("audit_log.html", audit_log=audit_log)

if __name__ == '__main__':
    app.run(debug=True)