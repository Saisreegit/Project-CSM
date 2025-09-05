from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask import request, jsonify
import pandas as pd

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Work Products
WORK_PRODUCTS = [{"id": "part 2","name": "Management of functional safety"}
,{
    "id":"WKPR_2_5.5.1",
 "name": "Organization-Specific Rules and Process for Functional Safety",
 "description": "The organization-specific rules and processes is structured guidelines and methodologies that ensure functional safety throughout the lifecycle of automotive systems. These processes are designed to meet the requirements of ISO 26262. The rules cover areas such as safety management, requirements definition, design, verification, validation, and documentation, ensuring that all safety aspects are addressed systematically.",
 "predecessors": "NA",
 "Successor":"All Work Products"
 },
 
{"id":"WKPR_2_5.5.2", 
 "name": "Evidence of competence Management" ,
 "description":"Team Competence shall document the required competencies for each role, ensuring that team members have expertise in safety engineering, software and hardware development, verification and validation, and risk assessment. Regular training programs, competency assessments, and knowledge-sharing initiatives should be implemented to maintain and enhance team skills.",
 "predecessors": "NA",
 "Successor":"Safety Plan"
 },
{"id":"WKPR_2_5.5.3", 
 "name": "Evidence of a quality management system",
 "description":" The QMS is a formalized system that documents processes, procedures, and responsibilities for achieving quality policies and objectives.",
 "predecessors": "NA",
 "Successor":"Organization Specific rules and processes"
 },
 {"id":"WKPR_2_5.5.4", 
 "name": "Identified Safety anomaly reports",
 "description":" The QMS is a formalized system that documents processes, procedures, and responsibilities for achieving quality policies and objectives.",
 "predecessors": "All Work Products",
 "Successor":"NA"
 },
 {"id":"WKPR_2_6.5.1", 
 "name": "Evidence of a quality management system",
 "description":" Impact analysis at the item Level",
 "predecessors": "Safety certified Spec, Spec(External)",
 "Successor":"FMEDA"
 },
 {"id":"WKPR_2_6.5.2", 
 "name": "Evidence of a quality management system",
 "description":" Impact analysis at the element Level",
 "predecessors": "Safety certified Spec, Spec(External)",
 "Successor":"FSR, TSR"
 },
 {"id":"WKPR_2_6.5.3", 
 "name": "Evidence of a quality management system",
 "description":" Safety Plan ",
 "predecessors": "NA",
 "Successor":"All Work Products"
 },
 {"id":"WKPR_2_6.5.4", 
 "name": "Evidence of a quality management system",
 "description":"A safety case shall be developed in accordance with the safety plan to provide a structured and well-documented argument demonstrating the achievement of functional safety. It shall include safety-related work products, supporting evidence, and traceability to applicable safety requirements..",
 "predecessors": "NA",
 "Successor":"All Work Products"
 },
 {"id":"WKPR_2_6.5.5", 
 "name": "Evidence of a quality management system",
 "description":" The confirmation review assesses whether key work products provide sufficient and convincing evidence of their contribution to achieving functional safety, in alignment with the objectives and requirements of the ISO 26262 series of standards. This review ensures that the work products meet the necessary safety goals by evaluating their completeness, correctness, and compliance with the defined safety requirements.",
 "predecessors": "All Work Products",
 "Successor":"NA"
 },
 {"id":"WKPR_2_6.5.6", 
 "name": "Evidence of a quality management system",
 "description":" The production report consists of all the documents related to the manufacturing process and confirms its alignment with ISO 26262 standards..",
 "predecessors": "Confirmation measure reports",
 "Successor":"NA"
 },
 {"id":"WKPR_2_7.5.1", 
 "name": "Evidence of a quality management system",
 "description":" It documents the appointment of responsible personnel who have the authority to oversee and enforce functional safety measures during these lifecycle stages. Planning for safety activities must begin early in system development, ensuring compliance with safety standards for production, operation, maintenance, and decommissioning while also integrating safety considerations from the system development phase.",
 "predecessors": "Confirmation measure reports",
 "Successor":"NA"
 },



{"id":"part 4", "name": "Product development at the system"},

{"id": "WKPR_4_6.5.1",
 "name": "Technical Safety Requirements specification",
 "description": "The Technical Safety Requirements (TSR) Specification defines the detailed safety requirements necessary to achieve functional safety at the technical level. The TSR is derived from the Functional Safety Concept (FSC) and ensures that safety goals from the Hazard Analysis and Risk Assessment (HARA) are systematically implemented in the system, hardware, and software architecture.",
 "predecessors": "Functional Safety Concept (FSC), Hazard Analysis and Risk Assessment (HARA)",
 "Successor": "System Arch design, SM implementation"
},

{"id": "WKPR_4_6.5.2",
 "name": "Technical Safety Concept",
 "description": "The Technical Safety Concept defines the high-level architectural structure, including the decomposition of safety requirements across system elements, to ensure traceability and fulfill safety goals.",
 "predecessors": "Functional Safety Concept (FSC)",
 "Successor": "Safety Analysis"
},

{"id": "WKPR_4_6.5.3",
 "name": "System Architectural Design",
 "description": "The System Architectural Design is the selected system-level solution that is implemented by a technical system. It aims to fulfill both the allocated technical safety requirements and the non-safety requirements. System development can be performed iteratively, ensuring adaptability to design constraints and safety considerations.",
 "predecessors": "Technical Safety Concept",
 "Successor": "Safety Analysis"
},

{"id": "WKPR_4_6.5.4",
 "name": "Hardware-Software Interface (HSI) Specification",
 "description": "The Hardware-Software Interface (HSI) specification defines the interaction between hardware and software components in a system. It ensures consistency with the Technical Safety Concept and outlines the hardware parts controlled by software and the hardware resources supporting software execution. This specification serves as a reference for both hardware and software teams to align their development activities.",
 "predecessors": "System Architectural Design, Technical Safety Concept",
 "Successor": "HDS, SW Architectural Spec"
}

]

for item in WORK_PRODUCTS:
    if 'id' in item:
        item['id'] = item['id'].strip()
SAVED_DATA = {}
NOT_TAILORED_DATA = {}
IMPORTED_PEOPLE = {}  # New global to store imported people
FINAL_VIEW_DATA = []  # Stores what to show on third page
FINAL_DATE_DATA = {}




@app.route('/')
def show_products():
    part = request.args.get('part', '')  # Get the selected part from URL (e.g., "part 2")
    parts = [item for item in WORK_PRODUCTS if item['id'].startswith('part')]  # Part headers

    # Filter work products to only show ones under selected part
    selected_products = []
    in_section = False
    for item in WORK_PRODUCTS:
        if item['id'].startswith('part'):
            in_section = (item['id'] == part or part == '')
            if in_section:
                selected_products.append(item)  
            continue
        if in_section:
            selected_products.append(item)

    return render_template(
        'final_page.html',
        work_products=selected_products,
        saved_data=SAVED_DATA,
        parts=parts,
        selected_part=part
    )


@app.route('/autosave', methods=['POST'])
def autosave():
    data = request.get_json()
    idx = data['idx'].strip()
    tailored = data['tailored']
    rationale = data['rationale'] if tailored == 'Yes' else ''
    other = data['other'] if rationale == 'Other' else ''
    SAVED_DATA[idx] = {"tailored": tailored, "rationale": rationale, "other": other}
    return jsonify(success=True)


@app.route('/autosave_not_tailored', methods=['POST'])
def autosave_not_tailored():
    data = request.get_json()
    idx = data['idx'].strip()
    if idx not in NOT_TAILORED_DATA:
        NOT_TAILORED_DATA[idx] = {}
    NOT_TAILORED_DATA[idx][data['field']] = data['value']
    return jsonify(success=True)


@app.route('/next', methods=['POST', 'GET'])
def next_page():
    part = request.args.get('part', '')
    filtered = []
    in_section = False
    current_part = None
    temp_group = []

    for item in WORK_PRODUCTS:
        if item['id'].startswith('part'):
            if temp_group:
                filtered.append(current_part)  # add last part header
                filtered.extend(temp_group)   # add its non-tailored work products
                temp_group = []               # reset for next part

            current_part = {
                "idx": item["id"],
                "name": item["name"],
                "is_part": True
            }
            in_section = (item['id'] == part or part == '')
            continue

        if in_section:
            idx = item["id"]
            sel = SAVED_DATA.get(idx, {}).get("tailored", "No")
            if sel == "No":
                temp_group.append({
                    "idx": idx,
                    "name": item["name"],
                    "data": NOT_TAILORED_DATA.get(idx, {}),
                    "is_part": False
                })

    # Append last group if any
    if temp_group:
        filtered.append(current_part)
        filtered.extend(temp_group)

    return render_template('second_page.html', filtered=filtered, imported_people=IMPORTED_PEOPLE)



@app.route('/save_not_tailored', methods=['POST'])
def save_not_tailored():
    global FINAL_VIEW_DATA
    part = request.args.get('part', '')
    
    for item in WORK_PRODUCTS:
        idx = item["id"].strip()
        if SAVED_DATA.get(idx, {}).get("tailored", "No") == "No":
            NOT_TAILORED_DATA[idx] = {
                "author": request.form.get(f"author_{idx}", ""),
                "author_other": request.form.get(f"author_other_{idx}", ""),
                "reviewer1": request.form.get(f"reviewer1_{idx}", ""),
                "reviewer1_other": request.form.get(f"reviewer1_other_{idx}", ""),
                "reviewer2": request.form.get(f"reviewer2_{idx}", ""),
                "reviewer2_other": request.form.get(f"reviewer2_other_{idx}", ""),
            }

    # ✅ Capture the same filtered structure used in /next
    filtered = []
    in_section = False
    current_part = None
    temp_group = []

    for item in WORK_PRODUCTS:
        if item['id'].startswith('part'):
            if temp_group:
                filtered.append(current_part)
                filtered.extend(temp_group)
                temp_group = []
            current_part = {
                "idx": item["id"],
                "name": item["name"],
                "is_part": True
            }
            in_section = (item['id'] == part or part == '')
            continue

        if in_section:
            idx = item["id"]
            sel = SAVED_DATA.get(idx, {}).get("tailored", "No")
            if sel == "No":
               temp_group.append({
    "idx": idx,
    "name": item["name"],
    "predecessors": item.get("predecessors", "N/A"),
    "successor": item.get("Successor", "N/A"),  # Note: capital 'S' in your source data
    "is_part": False
})


    if temp_group:
        filtered.append(current_part)
        filtered.extend(temp_group)

    FINAL_VIEW_DATA = filtered  # ✅ Save for use in final page

    flash("Products not tailored data saved.")
    return redirect(url_for('final_page'))

@app.route('/import_excel', methods=['POST'])
def import_excel():
    global IMPORTED_PEOPLE
    file = request.files.get('file')

    if not file:
        return jsonify({"success": False, "error": "No file uploaded."}), 400

    try:
        df = pd.read_excel(file)
        df.columns = [c.lower().strip() for c in df.columns]
        df['id'] = df['id'].astype(str).str.strip()

        required_columns = {'id', 'person_name'}
        if not required_columns.issubset(df.columns):
            return jsonify({"success": False, "error": "Missing required columns: 'id' and 'person_name'"}), 400

        if df.empty:
            return jsonify({"success": False, "error": "Excel file is empty."}), 400

        grouped = df.groupby('id')['person_name'].apply(lambda x: list(set(x.dropna()))).to_dict()
        IMPORTED_PEOPLE = grouped  # Save globally

        return jsonify({"success": True, "data": grouped})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
@app.route('/final')
def final_page():
    return render_template('final_page.html', final_data=FINAL_VIEW_DATA, FINAL_DATE_DATA=FINAL_DATE_DATA)


@app.route('/autosave_final', methods=['POST'])
def autosave_final():
    data = request.get_json()
    idx = data.get('idx')
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    if idx:
        FINAL_DATE_DATA[idx] = {"start_date": start_date, "end_date": end_date}
        return jsonify(success=True)
    return jsonify(success=False), 400
if __name__ == '__main__':
    app.run(debug=True)
