from flask import Flask, render_template_string, request, redirect, url_for, session, send_from_directory, send_file, render_template, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
import os
from sqlalchemy.orm import validates
import io
from sqlalchemy.dialects.mysql import MEDIUMBLOB
import re
from dotenv import load_dotenv



load_dotenv()
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# MySQL Configuration
app.config['SQLALCHEMY_DATABASE_URI'] ='mysql+pymysql://root:root123@localhost:3307/crms_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Work product configuration for first page
work_products = [
    {"name": "Change Request ID", "input_type": "text"},
    {"name": "Start Date", "input_type": "date"},
    {"name": "Phase", "input_type": "select", "options": [
        "Change Request Description Phase",
        "Impact Analysis Phase",
        "Dependent Work Product Analysis Phase",
        "Verification Phase",
        "Closure"
    ]},
    {"name": "End Date", "input_type": "date"},
    {"name": "Summary of Change", "input_type": "textarea"},
]


# Fields for second page
additional_fields = [
    {"name": "Responsible Person", "input_type": "text"},
    {"name": "Document subject to change", "input_type": "text"},
    {"name": "Current Version", "input_type": "text"},
    {"name": "Configuration of the document", "input_type": "text"},
    {
        "name": "Type of Change Request",
        "input_type": "checkbox",
        "options": ["Error Resolution", "Adaption", "Elimination", "Enhancement", "Prevention"]
        
    },
    {"name": "Change Type", "input_type": "select", "options": ["Temporary", "Permanent"]},
    {"name": "Change Period (if Temporary)", "input_type": "daterange"},
    {"name": "Change Description", "input_type": "textarea"},
    {"name": "Reason for Change", "input_type": "textarea"},
    {"name": "Phase Status", "input_type": "select", "options": ["Open", "Closed"]},
]

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

mail = Mail(app)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = None  # Allow all types

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return True  # Accept all file types

# SQLAlchemy model
class ChangeRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    change_request_id = db.Column(db.String(100), unique=True, nullable=False)
    start_date = db.Column(db.String(50))
    phase = db.Column(db.String(50))
    end_date = db.Column(db.String(50))
    summary_of_change = db.Column(db.Text)

    responsible_person = db.Column(db.String(255))
    document_subject_to_change = db.Column(db.String(255))
    current_version = db.Column(db.String(255))
    configuration_of_the_document = db.Column(db.String(255))
    type_of_change_request = db.Column(db.String(255))
    change_type = db.Column(db.String(50))
    change_period_from = db.Column(db.String(50))
    change_period_to = db.Column(db.String(50))
    change_description = db.Column(db.Text)
    reason_for_change = db.Column(db.Text)
    phase_status = db.Column(db.String(50))
    email_ids = db.Column(db.String(500))

    # New columns for uploaded file stored in DB
    uploaded_file_name = db.Column(db.String(255))
    uploaded_file_data = db.Column(MEDIUMBLOB)
    uploaded_file_type = db.Column(db.String(255))

    @validates('change_period_from', 'change_period_to')
    def validate_date(self, key, value):
        if value in ('', 'N/A'):
            return None
        return value
# select template (Change Request Details)
    
# Embedded HTML template for the select page

@app.route('/', methods=['GET'])
def index():
    return render_template("select_template.html")


@app.route('/new-request', methods=['GET', 'POST'])
def new_request():
    change_request_id = request.args.get('change_request_id')
    saved_data = {}

    if request.method == 'POST':
        form_action = request.form.get('action')

        values = {}
        for i, wp in enumerate(work_products, start=1):
            key = f'value{i}'
            values[wp['name']] = request.form.get(key, '').strip()

        # Get ID from form
        cr_id = request.form.get('change_request_id', '').strip()

        # Generate new ID only if empty (first submit of new form)
        if not cr_id:
            cr_id = f"CR{datetime.now().strftime('%Y%m%d%H%M%S')}"

        cr = ChangeRequest.query.filter_by(change_request_id=cr_id).first()

        if not cr:
            cr = ChangeRequest(change_request_id=cr_id)
            db.session.add(cr)

        cr.start_date = values.get("Start Date")
        cr.end_date = values.get("End Date")
        cr.phase = values.get("Phase")
        cr.summary_of_change = values.get("Summary of Change")

        db.session.commit()

        saved_data = {
            "Change Request ID": cr.change_request_id,
            "Start Date": cr.start_date or '',
            "End Date": cr.end_date or '',
            "Phase": cr.phase or '',
            "Summary of Change": cr.summary_of_change or ''
        }

        if form_action == 'Next':
            # Pass the CR ID to the second step so it uses the same one
            return redirect(url_for('new_request_step2', change_request_id=cr.change_request_id))
        elif form_action == 'Save':
            return render_template("first_template.html", saved_data=saved_data, work_products=work_products, message="Saved successfully.")

    elif change_request_id:
        cr = ChangeRequest.query.filter_by(change_request_id=change_request_id).first()
        if cr:
            saved_data = {
                "Change Request ID": cr.change_request_id,
                "Start Date": cr.start_date or '',
                "End Date": cr.end_date or '',
                "Phase": cr.phase or '',
                "Summary of Change": cr.summary_of_change or ''
            }

    return render_template("first_template.html", saved_data=saved_data, work_products=work_products)


# New route: second page for new request filling more details
@app.route('/new-request-step2', methods=['GET', 'POST'])
def new_request_step2():
    cr_id = request.values.get('change_request_id')
    if not cr_id:
        return "Change Request ID is required", 400

    cr = ChangeRequest.query.filter_by(change_request_id=cr_id).first()
    if not cr:
        return f"Change Request '{cr_id}' not found", 404

    message = None

    if request.method == 'POST':
        # Process additional fields dynamically:
        for field in additional_fields:
            key = field['name'].replace(' ', '_').lower()
            if field['input_type'] == 'checkbox':
                # Multiple checkbox values come as list, join to string or store as list
                values = request.form.getlist(field['name'])
                setattr(cr, key, ','.join(values))
            else:
                setattr(cr, key, request.form.get(field['name'], '').strip())

        # Process date range fields explicitly (if needed)
        cr.change_period_from = request.form.get('change_period_from')
        cr.change_period_to = request.form.get('change_period_to')

        # Save email IDs if submitted
        cr.email_ids = request.form.get('email', '').strip()

        # Handle file upload if any
        file = request.files.get('file')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file_data = file.read()
            cr.uploaded_file_name = filename
            cr.uploaded_file_data = file_data  # assuming you have this column in your model

        db.session.commit()
        message = "Saved successfully."

        # If the 'send_email' button was clicked, you can implement sending logic here.

    return render_template("second_template.html",
                                  change_request=cr,
                                  additional_fields=additional_fields,
                                  message=message)


@app.route('/existing-change-request-step2', methods=['GET', 'POST'])
def existing_change_request_step2():
    cr_id = request.args.get('change_request_id')
    if not cr_id:
        return "Change Request ID is required", 400

    cr = ChangeRequest.query.filter_by(change_request_id=cr_id).first()
    if not cr:
        return f"Change Request '{cr_id}' not found", 404

    message = None

    if request.method == 'POST':
        for field in additional_fields:
            key = field['name'].replace(' ', '_').lower()
            if field['input_type'] == 'checkbox':
                values = request.form.getlist(field['name'])
                setattr(cr, key, ','.join(values))
            else:
                setattr(cr, key, request.form.get(field['name'], '').strip())

        cr.change_period_from = request.form.get('change_period_from')
        cr.change_period_to = request.form.get('change_period_to')
        cr.email_ids = request.form.get('email', '').strip()

        file = request.files.get('file')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            cr.uploaded_file_name = filename
            cr.uploaded_file_data = file.read()

        db.session.commit()
        message = "Second page saved successfully."

    return render_template(
        "second_template.html",
        change_request=cr,
        additional_fields=additional_fields,
        message=message
    )
# Your existing lookup and view routes below...
@app.route('/existing-change-request', methods=['GET', 'POST'])
def existing_change_request():
    error = None
    if request.method == 'POST':
        cr_id = request.form.get('change_request_id')
        if not cr_id:
            error = "Please enter a Change Request ID."
        else:
            cr = ChangeRequest.query.filter_by(change_request_id=cr_id).first()
            if cr:
                return redirect(url_for('existing_change_request_step1', change_request_id=cr_id))
            else:
                error = "Change Request ID not found."
    return render_template("existing_lookup.html", error=error)

@app.route('/existing-change-request/<change_request_id>', methods=['GET', 'POST'])
def existing_change_request_step1(change_request_id):
    cr = ChangeRequest.query.filter_by(change_request_id=change_request_id).first()
    if not cr:
        return f"Change Request '{change_request_id}' not found", 404

    saved_data = {
        "Change Request ID": cr.change_request_id,
        "Start Date": cr.start_date or '',
        "End Date": cr.end_date or '',
        "Phase": cr.phase or '',
        "Summary of Change": cr.summary_of_change or ''
    }

    if request.method == 'POST':
        action = request.form.get('action')
        cr.start_date = request.form.get('value1') or None
        cr.end_date = request.form.get('value2') or None
        cr.phase = request.form.get('value3') or ''
        cr.summary_of_change = request.form.get('value4') or ''
        db.session.commit()

        if action == 'Next':
            return redirect(url_for('existing_change_request_step2', change_request_id=cr.change_request_id))

        return render_template("first_template.html", saved_data=saved_data, work_products=work_products, message="Saved successfully.")

    return render_template("first_template.html", saved_data=saved_data, work_products=work_products)

@app.route('/', methods=['GET', 'POST'])
def show_work_products():
    message = ""
    saved_data = {}

    cr_id = request.args.get('change_request_id') or (session.get('saved_data') or {}).get('Change Request ID')
    change_request = None
    if cr_id:
        change_request = ChangeRequest.query.filter_by(change_request_id=cr_id).first()

    if request.method == 'POST':
        action = request.form.get('action')
        form_data = {}

        # Collect data from the form
        for i, wp in enumerate(work_products, start=1):
            form_data[wp['name']] = request.form.get(f'value{i}')

        # Save/update DB record here (not just session)
        existing = ChangeRequest.query.filter_by(change_request_id=form_data["Change Request ID"]).first()
        if existing:
            existing.start_date = form_data["Start Date"]
            existing.phase = form_data["Phase"]
            existing.end_date = form_data["End Date"]
            existing.summary_of_change = form_data.get("Summary of Change", "")
        else:
            entry = ChangeRequest(
                change_request_id=form_data["Change Request ID"],
                start_date=form_data["Start Date"],
                phase=form_data["Phase"],
                end_date=form_data["End Date"],
                summary_of_change=form_data.get("Summary of Change", "")
            )
            db.session.add(entry)

        db.session.commit()

        message = "Page saved successfully!"
        session['saved_data'] = form_data
        session['message'] = message

        if action == "Save":
            # After save, stay on first page with updated data
            return redirect(url_for('show_work_products', change_request_id=form_data["Change Request ID"]))

        elif action == "Next":
            return redirect(url_for('next_step', cr_id=form_data["Change Request ID"]))

    else:
        # GET method, load data either from DB or session
        if change_request:
            saved_data = {
                "Change Request ID": change_request.change_request_id,
                "Start Date": change_request.start_date,
                "Phase": change_request.phase,
                "End Date": change_request.end_date,
                "Summary of Change": change_request.summary_of_change
            }
        else:
            saved_data = session.pop('saved_data', {})

        message = session.pop('message', '')

    return render_template("first_template.html", work_products=work_products, saved_data=saved_data, message=message)

@app.route('/next', methods=['GET'])
def next_step():
    cr_id = request.args.get('cr_id')
    if not cr_id:
        return redirect(url_for('home'))

    change_request = ChangeRequest.query.filter_by(change_request_id=cr_id).first()
    if not change_request:
        return "Change Request not found!", 404

    return render_template("second_template.html", additional_fields=additional_fields, message="", change_request=change_request)

#second (Change Request Description Phase) page
# Second page template (Change Request Description Phase)

# === HELPER ===
def parse_date(value):
    if value in ('', 'N/A', None):
        return None
    return value  # You can parse date string here if needed


@app.route('/save-next', methods=['GET', 'POST'])
def save_next():
    # Get change_request_id from GET query or POST form
    cr_id = request.args.get('change_request_id') or request.form.get('change_request_id')
    if not cr_id:
        return "Change Request ID is required", 400

    # Query ChangeRequest from DB
    cr = ChangeRequest.query.filter_by(change_request_id=cr_id).first()
    if not cr:
        return "Change Request not found", 404

    message = None

    if request.method == 'POST':
        # Update fields from form POST
        cr.responsible_person = request.form.get('responsible_person')
        cr.document_subject_to_change = request.form.get('document_subject_to_change')
        cr.current_version = request.form.get('current_version')
        cr.document_configuration = request.form.get('document_configuration')
        cr.type_of_change_request = request.form.get('type_of_change_request')
        cr.change_type = request.form.get('change_type')
        cr.change_period_from = parse_date(request.form.get('change_period_from'))
        cr.change_period_to = parse_date(request.form.get('change_period_to'))
        cr.change_description = request.form.get('change_description')
        cr.reason_for_change = request.form.get('reason_for_change')
        cr.phase_status = request.form.get('phase_status')
        cr.email_ids = request.form.get('email')

        # Parse emails list from textarea input or input field
        email_input = request.form.get('email', '')
        email_list = [e.strip() for e in email_input.replace('\n', ',').split(',') if e.strip()]

        # If 'Send Email' button clicked but no emails, show error without saving
        if 'send_email' in request.form and not email_list:
            return render_template(
                "second_template.html",
                additional_fields=additional_fields,
                message="⚠️ Cannot send email: No recipient email address provided.",
                change_request=cr
            )

        # Update additional dynamic fields (assuming additional_fields is defined globally or imported)
        for field in additional_fields:
            field_name = field["name"]
            column_attr = field_name.replace(' ', '_').lower()

            if field_name == 'Type of Change Request':
                # Get multiple selections as comma separated string
                setattr(cr, column_attr, ', '.join(request.form.getlist(field_name)))
            elif field_name == 'Change Type':
                change_type = request.form.get(field_name)
                cr.change_type = change_type
                if change_type == 'Temporary':
                    cr.change_period_from = parse_date(request.form.get('change_period_from'))
                    cr.change_period_to = parse_date(request.form.get('change_period_to'))
                else:
                    cr.change_period_from = None
                    cr.change_period_to = None
            elif field_name != 'Change Period (if Temporary)':
                setattr(cr, column_attr, request.form.get(field_name, ''))

        # Save cleaned email list back to model as comma separated string
        cr.email_ids = ', '.join(email_list)

        # Handle file upload if new file is provided
        uploaded_file = request.files.get('file')
        if uploaded_file and uploaded_file.filename:
            data = uploaded_file.read()
            cr.uploaded_file_name = uploaded_file.filename
            cr.uploaded_file_data = data
            cr.uploaded_file_type = uploaded_file.content_type
        # else do nothing (keep old file)

        message = "Saved successfully."

        # If user clicked send_email button and there are emails, send email notification
        if 'send_email' in request.form and cr.email_ids:
            recipients = [e.strip() for e in cr.email_ids.split(',')]
            try:
                msg = Message("Change Request Notification", recipients=recipients)
                msg.body = f"Change Request ID: {cr.change_request_id}\n\nDetails:\n"

                # Include all ChangeRequest columns except file data
                for column in cr.__table__.columns:
                    if column.name != 'uploaded_file_data':
                        value = getattr(cr, column.name)
                        formatted_name = column.name.replace('_', ' ').title()
                        msg.body += f"{formatted_name}: {value}\n"

                # Attach file if exists
                if cr.uploaded_file_data and cr.uploaded_file_name:
                    msg.attach(
                        filename=cr.uploaded_file_name,
                        content_type=cr.uploaded_file_type or 'application/octet-stream',
                        data=cr.uploaded_file_data
                    )

                mail.send(msg)
                message = "Saved and email sent."
            except Exception as e:
                message = f"Saved but failed to send email: {str(e)}"

        # Commit all DB changes after save (and maybe email)
        db.session.commit()

        # Redirect to impact analysis page if 'Next' button clicked
        if 'next_form' in request.form:
            return redirect(url_for('impact_analysis', change_request_id=cr_id))

        # If 'Save' button clicked, just render the second page again with message
        elif 'save_form' in request.form:
            return render_template(
                "second_template.html",
                additional_fields=additional_fields,
                message=message,
                change_request=cr
            )

    # If GET request: render the second page with existing data
    # Provide a message only if you want, otherwise pass None
    return render_template(
        "second_template.html",
        additional_fields=additional_fields,
        message=None,
        change_request=cr
    )

@app.route('/download-db-file/<cr_id>')
def download_db_file(cr_id):
    cr = ChangeRequest.query.filter_by(change_request_id=cr_id).first_or_404()
    if cr.uploaded_file_data:
        return send_file(
            io.BytesIO(cr.uploaded_file_data),
            mimetype=cr.uploaded_file_type,
            as_attachment=True,
            download_name=cr.uploaded_file_name
        )
    return "No file found in database for this record.", 404


@app.route('/')
def home():
    return "Welcome to the Change Request App. Go to /next?cr_id=your_id to continue."

# third impact analysis phase page

class ImpactAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    change_request_id = db.Column(db.String(100), db.ForeignKey('change_request.change_request_id'), nullable=False)

    start_date = db.Column(db.String(50))
    due_date = db.Column(db.String(50))
    responsible_person = db.Column(db.String(100))
    change_severity = db.Column(db.String(50))
    impact_on_functional_safety = db.Column(db.Text)
    justification = db.Column(db.Text)
    change_request_status = db.Column(db.String(100))
    rationale_if_rejected_delay = db.Column(db.Text)
    phase_status = db.Column(db.String(100))

    email_ids = db.Column(db.Text)

    change_request = db.relationship('ChangeRequest', backref=db.backref('impact_analysis', uselist=False))

impact_analysis_fields = [

    {"name": "Change Request ID", "input_type": "text", "readonly": True},

    {"name": "Start Date", "input_type": "date"},
    {"name": "Due Date", "input_type": "date"},
    {"name": "Responsible Person", "input_type": "text"},

    {"name": "Change Severity", "input_type": "select", "options": ["Major",  "Minor"]},

    {"name": "Impact on Functional Safety", "input_type": "select", "options": ["Yes",  "No"]},

    {"name": "Justification", "input_type": "textarea"},

    {"name": "Change Request Status", "input_type": "select", "options": ["Approved", "Rejected", "Delayed"]},
    
    {"name": "Rationale (if Rejected/Delayed)", "input_type": "textarea"},
    
    {"name": "Phase Status", "input_type": "select", "options": ["Open", "Closed"]}
]

def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

@app.route('/impact-analysis', methods=['GET', 'POST'])
def impact_analysis():
    cr_id = request.form.get('change_request_id') or request.args.get('change_request_id')
    if not cr_id:
        return "Change Request ID is required", 400

    cr = ChangeRequest.query.filter_by(change_request_id=cr_id).first()
    if not cr:
        return f"Change Request '{cr_id}' not found", 404

    impact = ImpactAnalysis.query.filter_by(change_request_id=cr_id).first()
    if not impact:
        impact = ImpactAnalysis(change_request_id=cr_id)

    message = None

    if request.method == 'POST':
        impact.start_date = request.form.get('start_date') or None
        impact.due_date = request.form.get('due_date') or None
        impact.responsible_person = request.form.get('responsible_person', '').strip()
        impact.change_severity = request.form.get('change_severity', '').strip()
        impact.impact_on_functional_safety = request.form.get('impact_on_functional_safety', '').strip()
        impact.justification = request.form.get('justification', '').strip()
        impact.change_request_status = request.form.get('change_request_status', '').strip()
        impact.rationale_if_rejected_delay = request.form.get('rationale_if_rejected_delay', '').strip()
        impact.phase_status = request.form.get('phase_status', '').strip()

        
        from datetime import datetime
        def parse_date(d):
            try:
                return datetime.strptime(d, '%Y-%m-%d').date()
            except Exception:
                return None

        impact.start_date = parse_date(impact.start_date) if impact.start_date else None
        impact.due_date = parse_date(impact.due_date) if impact.due_date else None

        db.session.add(impact)
        db.session.commit()

        message = "Impact analysis saved successfully."

        if 'next_form' in request.form:
            return redirect(url_for('work_product_analysis', change_request_id=cr_id))

        # NEW: email_id field
        impact.email_id = request.form.get('email_id', '').strip()


        # Load current data
    impact_data = ImpactAnalysis.query.filter_by(change_request_id=cr_id).first()

    if 'send_email' in request.form:
        if impact.email_id:
            email_list = [email.strip() for email in impact.email_id.split(',') if email.strip()]
            invalid_emails = [email for email in email_list if not is_valid_email(email)]

            if invalid_emails:
                flash(f"Invalid email(s): {', '.join(invalid_emails)}")
                return redirect(url_for('impact_analysis', change_request_id=cr_id))

            send_email_to_multiple_users(email_list, cr_id)
            return render_template_string('impact_analysis',
                                   impact=impact_data,
                                   email_sent=True,
                                   sent_to=', '.join(email_list))
        else:
            flash("Email address field is empty.")
            return redirect(url_for('impact_analysis', change_request_id=cr_id))




    # Format dates for display
    def format_date(d):
        return d.strftime('%Y-%m-%d') if d else ''

    impact.start_date = format_date(impact.start_date)
    impact.due_date = format_date(impact.due_date)

    return render_template(
        "impact_analysis.html",
        message=message,
        impact=impact
    )


def send_email_to_multiple_users(email_list, change_request_id):
    msg = Message('Impact Analysis Notification',
                  sender='your_email@example.com',
                  recipients=email_list)
    msg.body = f'Impact Analysis has been updated for Change Request ID: {change_request_id}.'
    mail.send(msg)


def send_email_to_multiple_users(email_list, change_request_id):
    msg = Message(
        subject='Impact Analysis Notification',
        sender='your_email@example.com',
        recipients=email_list
    )

    msg.body = f"""
Dear Recipient,

The Impact Analysis Phase has been updated for the following Change Request:

Change Request ID: {change_request_id}

Please log in to the system to review the details.

Regards,  
Change Management Team
"""

    mail.send(msg)
@app.route('/checklist')
def auto_checklist():
    cr_id = request.args.get('change_request_id')
    if not cr_id:
        return "Change Request ID is required to run checklist", 400

    cr = ChangeRequest.query.filter_by(change_request_id=cr_id).first()
    if not cr:
        return f"Change Request ID '{cr_id}' not found", 404

    # Checklist logic
    checks = []

    # 1. Is the Change Request ID properly formatted? (e.g., starts with CR + digits)
    formatted = cr.change_request_id.startswith("CR") and cr.change_request_id[2:].isdigit()
    checks.append(("Is the Change Request ID properly formatted?", "Pass" if formatted else "Fail"))

    # 2. Is End Date after Start Date?
    try:
        from datetime import datetime
        start = datetime.strptime(cr.start_date, "%Y-%m-%d") if cr.start_date else None
        end = datetime.strptime(cr.end_date, "%Y-%m-%d") if cr.end_date else None
        date_check = start and end and end >= start
        checks.append(("Is the End Date after the Start Date?", "Pass" if date_check else "Fail"))
    except Exception:
        checks.append(("Is the End Date after the Start Date?", "Fail"))

    # 3. Is a document uploaded?
    doc_uploaded = cr.uploaded_file_name is not None
    checks.append(("Is the document uploaded (hyperlinked)?", "Pass" if doc_uploaded else "Fail"))

    # 4. Is version in correct decimal format? (e.g., 1.0, 2.3)
    import re
    decimal_pattern = re.compile(r'^\d+(\.\d+)?$')
    is_decimal = bool(decimal_pattern.match(cr.current_version or ""))
    checks.append(("Is the Version in correct decimal format?", "Pass" if is_decimal else "Fail"))

    # 5. Are all mandatory fields filled? (start, end, phase, etc.)
    required_fields = [cr.start_date, cr.end_date, cr.phase, cr.summary_of_change, cr.current_version]
    all_filled = all(str(f).strip() for f in required_fields if f is not None)
    checks.append(("Are all mandatory fields in Change Request filled?", "Pass" if all_filled else "Fail"))

    return render_template("checklist.html", cr_id=cr_id, checks=checks)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)












    
