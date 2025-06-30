from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
import xml.etree.ElementTree as ET
from flask import make_response
import os
import xml.etree.ElementTree as ET
from werkzeug.utils import secure_filename
from openpyxl import load_workbook
import pandas as pd

app = Flask(__name__)
app.secret_key = '3315'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'xml','xlsx'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def format_datetime(value, format='%Y-%m-%d %H:%M'):
    if value is None:
        return ''
    if isinstance(value, str):
        try:
            value = datetime.strptime(value, '%Y-%m-%d %H:%M')
        except ValueError:
            return value
    return value.strftime(format)

app.jinja_env.filters['datetimeformat'] = format_datetime

# Add datetime to all templates
@app.context_processor
def inject_datetime():
    return {'datetime': datetime}

credentials = {
    'ld_admin': {'username': 'ldadmin', 'password': 'ld123'},
    'is_admin': {'username': 'isadmin', 'password': 'is123', 'department': 'IS'},
    'cm_admin': {'username': 'cmadmin', 'password': 'cm123', 'department': 'CM'},
    'el_admin': {'username': 'eladmin', 'password': 'el123', 'department': 'EL'},
    'hr_admin': {'username': 'hradmin', 'password': 'hr123', 'department': 'HR'},
    'fs_admin': {'username': 'fsadmin', 'password': 'fs123', 'department': 'F&S'},
    'hse_admin': {'username': 'hseadmin', 'password': 'hse123', 'department': 'HSE'},
    'finance_admin': {'username': 'financeadmin', 'password': 'finance123', 'department': 'Finance'}
}

departments_employees = {
    'IS': [],
    'CM': [],
    'EL': [],
    'HR': [],
    'F&S': [],
    'HSE': [],
    'Finance': []
}
training_records = {}
attendance_records = {}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def role_selection():
    return render_template('auth/login.html')


@app.route('/login/<role>', methods=['GET', 'POST'])
def login(role):
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Handle L&D admin case
        if role == 'ld_admin':
            expected = credentials.get('ld_admin')
            if username == expected['username'] and password == expected['password']:
                session['role'] = 'ld_admin'
                return redirect(url_for('dashboard'))
            else:
                return render_template('auth/credentials.html', role=role, error="Invalid credentials")


        elif role == 'dept_admin':
            department = request.form.get('department')
            if not department:
                return render_template('auth/credentials.html', role=role, error="Please select a department")


            for cred_key, cred_value in credentials.items():
                if cred_key.endswith('_admin') and cred_key != 'ld_admin':
                    if username == cred_value['username'] and password == cred_value['password']:
                        # Verify the selected department matches the admin's department
                        if department == cred_value['department']:
                            session['role'] = cred_key
                            session['department'] = department
                            return redirect(url_for('dashboard'))
                        else:
                            return render_template('auth/credentials.html', role=role,
                                                   error="Invalid department for this admin")

            return render_template('auth/credentials.html', role=role, error="Invalid credentials")

        else:
            return render_template('auth/credentials.html', role=role, error="Invalid role")

    return render_template('auth/credentials.html', role=role)

@app.route('/dashboard')
def dashboard():
    role = session.get('role')
    if not role:
        return redirect(url_for('role_selection'))

    if role == 'ld_admin':
        return render_template('L&D/dashboard.html')
    elif role.endswith('_admin'):  # This will catch all department admins
        return render_template('Department/dashboard_dept.html', department=session.get('department'))
    else:
        return redirect(url_for('logout'))


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'GET':
        return redirect(url_for('dashboard'))

    print("Upload endpoint hit!")

    if 'training_file' not in request.files:
        flash('No file part')
        return redirect(request.url)

    file = request.files['training_file']
    department = request.form.get('department')

    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)

    if not department:
        flash('No department selected')
        return redirect(request.url)

    if file and allowed_file(file.filename):
        filename = secure_filename(f"{department}_training_format.{file.filename.rsplit('.', 1)[1].lower()}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        file_ext = filename.rsplit('.', 1)[1].lower()

        try:
            file.save(filepath)

            if file_ext == 'xml':
                import xml.etree.ElementTree as ET
                tree = ET.parse(filepath)
                root = tree.getroot()
                if len(root) > 0:
                    field_names = [elem.tag for elem in root[0]]
                    session['training_fields'] = field_names
                    flash('XML file successfully uploaded')
                else:
                    os.remove(filepath)
                    flash('XML file has no content')
                    return redirect(request.url)

            elif file_ext == 'xlsx':
                import openpyxl
                wb = openpyxl.load_workbook(filepath)
                sheet = wb.active
                headers = [cell.value for cell in next(sheet.iter_rows(min_row=1, max_row=1))]
                session['training_fields'] = headers
                flash('XLSX file successfully uploaded')

            return redirect(url_for('dashboard'))

        except Exception as e:
            if os.path.exists(filepath):
                os.remove(filepath)
            flash(f'Error processing file: {str(e)}')
            return redirect(request.url)

    flash('Invalid file type. Only XML or XLSX files are allowed')
    return redirect(request.url)

@app.route('/upload_page')
def upload_page():
    return render_template('upload.html')


@app.route('/dept_training_content', methods=['GET', 'POST'])
def dept_training_content():
    if 'department' not in session:
        return redirect(url_for('logout'))

    department = session['department']
    filename = f"{department}_training_format.xml"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if request.method == 'POST':
        training_data = request.form.to_dict()
        assigned_employees = request.form.getlist('assigned_employees')

        if not training_data.get('training_name'):
            flash('Training name is required', 'error')
            return redirect(url_for('dept_training_content'))

        # Save to XML
        root = ET.Element("TrainingContents")
        training_entry = ET.SubElement(root, "Training")

        for field, value in training_data.items():
            if field != 'assigned_employees':
                child = ET.SubElement(training_entry, field)
                child.text = value

        assigned = ET.SubElement(training_entry, "AssignedEmployees")
        for emp_id in assigned_employees:
            emp = next((e for e in departments_employees[department] if e['id'] == emp_id), None)
            if emp:
                emp_elem = ET.SubElement(assigned, "Employee")
                ET.SubElement(emp_elem, "ID").text = emp_id
                ET.SubElement(emp_elem, "Name").text = emp['name']
                ET.SubElement(emp_elem, "Email").text = emp['email']

        tree = ET.ElementTree(root)
        tree.write(filepath)

        # ✅ Save full training data to records
        record_id = str(len(training_records) + 1)
        record_data = training_data.copy()
        record_data['id'] = record_id
        record_data['date'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        record_data['department'] = department
        record_data['assigned_employees'] = [
            e['name'] for e in departments_employees[department] if e['id'] in assigned_employees
        ]
        record_data['xml_content'] = ET.tostring(root, encoding='unicode')
        training_records[record_id] = record_data

        flash('Training content saved successfully!', 'success')
        return redirect(url_for('dept_training_content'))

    # GET Request
    field_names = session.get('training_fields', [])
    existing_values = {}
    employees = departments_employees.get(department, [])

    if os.path.exists(filepath):
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            if len(root) > 0:
                existing_values = {elem.tag: elem.text for elem in root[0] if elem.tag != 'AssignedEmployees'}
        except ET.ParseError:
            pass

    dept_records = [r for r in training_records.values() if r['department'] == department]

    return render_template('Department/training_content.html',
                         department=department,
                         field_names=field_names,
                         existing_values=existing_values,
                         employees=employees,
                         training_records=dept_records,
                         datetime=datetime)


@app.route('/edit_training/<record_id>', methods=['GET', 'POST'])
def edit_training(record_id):
    if 'department' not in session:
        return redirect(url_for('logout'))

    department = session['department']
    field_names = session.get('training_fields', [])
    employees = departments_employees.get(department, [])

    if record_id not in training_records:
        flash('Training record not found', 'error')
        return redirect(url_for('dept_training_content'))

    record = training_records[record_id]

    if request.method == 'POST':
        updated_data = request.form.to_dict()
        assigned_employees = request.form.getlist('assigned_employees')

        # Update fields
        for field in field_names:
            record[field] = updated_data.get(field, '')

        # Also update training_name separately
        record['training_name'] = updated_data.get('training_name', 'Unnamed')

        # Update assigned_employees with IDs
        record['assigned_employees'] = assigned_employees

        flash('Training record updated successfully!', 'success')
        return redirect(url_for('dept_training_content'))

    return render_template('Department/edit_training.html',
                           department=department,
                           field_names=field_names,
                           record=record,
                           employees=employees)


@app.route('/delete_training/<record_id>')
def delete_training(record_id):
    if record_id in training_records:
        del training_records[record_id]
        flash('Training record deleted successfully', 'success')
    else:
        flash('Training record not found', 'error')
    return redirect(url_for('dept_training_content'))


@app.route('/export_training/<record_id>')
def export_training(record_id):
    if record_id not in training_records:
        flash('Record not found')
        return redirect(url_for('dashboard'))

    record = training_records[record_id]
    response = make_response(record['xml_content'])
    response.headers['Content-Type'] = 'application/xml'
    response.headers['Content-Disposition'] = \
        f'attachment; filename=training_record_{record_id}.xml'
    return response


@app.route('/export_period')
def export_by_period():
    department = request.args.get('department')
    month = request.args.get('month')
    year = request.args.get('year')


    filtered_records = []
    for record in training_records.values():
        if record['department'] == department:
            record_date = datetime.strptime(record['date'], '%Y-%m-%d %H:%M')
            if (not month or record_date.month == int(month)) and \
                    (not year or record_date.year == int(year)):
                filtered_records.append(record)


    root = ET.Element("TrainingRecords")
    for record in filtered_records:
        record_elem = ET.SubElement(root, "TrainingRecord")
        ET.SubElement(record_elem, "Date").text = record['date']
        ET.SubElement(record_elem, "Department").text = record['department']
        ET.SubElement(record_elem, "TrainingName").text = record['training_name']
        employees_elem = ET.SubElement(record_elem, "AssignedEmployees")
        for emp in record['assigned_employees']:
            ET.SubElement(employees_elem, "Employee").text = emp

    response = make_response(ET.tostring(root, encoding='unicode'))
    response.headers['Content-Type'] = 'application/xml'
    filename = f"training_records_{department}"
    if year:
        filename += f"_{year}"
    if month:
        filename += f"_{month}"
    response.headers['Content-Disposition'] = f'attachment; filename={filename}.xml'
    return response


@app.route('/export_all')
def export_all():
    department = request.args.get('department')


    filtered_records = [r for r in training_records.values() if r['department'] == department]


    root = ET.Element("TrainingRecords")
    for record in filtered_records:
        record_elem = ET.SubElement(root, "TrainingRecord")
        ET.SubElement(record_elem, "Date").text = record['date']
        ET.SubElement(record_elem, "Department").text = record['department']
        ET.SubElement(record_elem, "TrainingName").text = record['training_name']
        employees_elem = ET.SubElement(record_elem, "AssignedEmployees")
        for emp in record['assigned_employees']:
            ET.SubElement(employees_elem, "Employee").text = emp

    response = make_response(ET.tostring(root, encoding='unicode'))
    response.headers['Content-Type'] = 'application/xml'
    response.headers['Content-Disposition'] = f'attachment; filename=all_training_records_{department}.xml'
    return response


@app.route('/lnddepartments')
def lnddepartments():
    return render_template('L&D/departments.html')


@app.route('/dept_att')
def dept_att():
    department = session.get('department')
    employees = departments_employees.get(department, [])
    # Change this line to use the global training_records dictionary
    return render_template('Department/attendance.html',
                         department=department,
                         departments_employees=departments_employees,
                         employees=employees,
                         training_records=training_records,
                         attendance_records=attendance_records)


@app.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    department = session.get('department')
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        employee_id = request.form.get('employee_id')
        designation = request.form.get('designation')

        if department and name and email and employee_id:
            new_employee = {
                'id': employee_id,
                'name': name,
                'email': email,
                'designation': designation,
                'department': department
            }
            departments_employees[department].append(new_employee)
            return redirect(url_for('view_employees'))

    return render_template('Department/add_employee.html', department=department)


@app.route('/view_employees')
def view_employees():
    department = session.get('department')
    employees = departments_employees.get(department, [])
    return render_template('Department/view_employees.html', employees=employees, department=department)


@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    if 'department' not in session:
        return redirect(url_for('logout'))

    department = session['department']
    training_id = request.form.get('training_name')
    attendance_date = request.form.get('attendance_date')
    present_employee_ids = request.form.getlist('present')

    # Find the training record
    training_record = training_records.get(training_id)
    if not training_record:
        flash('Training record not found', 'error')
        return redirect(url_for('attendance'))

    # Get employee details
    participants = []
    for emp_id in present_employee_ids:
        employee = next((e for e in departments_employees[department] if e['id'] == emp_id), None)
        if employee:
            participants.append({
                'id': employee['id'],
                'name': employee['name'],
                'email': employee['email'],
                'designation': employee.get('designation', 'N/A')
            })

    # Save attendance record
    record_id = str(len(attendance_records) + 1)
    attendance_records[record_id] = {
        'id': record_id,
        'training_name': training_record['training_name'],
        'date': attendance_date,
        'department': department,
        'participants': participants
    }

    flash('Attendance saved successfully!', 'success')
    return redirect(url_for('attendance'))

@app.route('/attendance', methods=['GET'])
def attendance():
    if 'department' not in session:
        return redirect(url_for('logout'))

    department = session['department']
    employees = departments_employees.get(department, [])
    today = datetime.now().strftime('%Y-%m-%d')

    # Filter training records for the current department
    dept_training_records = {
        k: v for k, v in training_records.items()
        if v.get('department') == department
    }

    # Filter attendance records for the current department
    dept_attendance_records = {
        k: v for k, v in attendance_records.items()
        if v.get('department') == department
    }

    return render_template('Department/attendance.html',
                         department=department,
                         departments_employees=departments_employees,
                         employees=employees,
                         training_records=dept_training_records,
                         attendance_records=dept_attendance_records,
                         current_date=today)

@app.route('/export_attendance_period')
def export_attendance_period():
    department = request.args.get('department')
    month = request.args.get('month')
    year = request.args.get('year')

    filtered_records = []
    for record in attendance_records.values():
        if record['department'] == department:
            record_date = datetime.strptime(record['date'], '%Y-%m-%d %H:%M')
            if (not month or record_date.month == int(month)) and \
                    (not year or record_date.year == int(year)):
                filtered_records.append(record)

    # Create XML response
    root = ET.Element("AttendanceRecords")
    for record in filtered_records:
        record_elem = ET.SubElement(root, "AttendanceRecord")
        ET.SubElement(record_elem, "TrainingName").text = record['training_name']
        ET.SubElement(record_elem, "Date").text = record['date']
        employees_elem = ET.SubElement(record_elem, "Participants")
        for emp in record['participants']:
            emp_elem = ET.SubElement(employees_elem, "Employee")
            ET.SubElement(emp_elem, "Name").text = emp['name']
            ET.SubElement(emp_elem, "ID").text = emp['id']
            ET.SubElement(emp_elem, "Designation").text = emp.get('designation', 'N/A')

    response = make_response(ET.tostring(root, encoding='unicode'))
    response.headers['Content-Type'] = 'application/xml'
    filename = f"attendance_records_{department}"
    if year:
        filename += f"_{year}"
    if month:
        filename += f"_{month}"
    response.headers['Content-Disposition'] = f'attachment; filename={filename}.xml'
    return response

@app.route('/export_all_attendance')
def export_all_attendance():
    department = request.args.get('department')
    filtered_records = [r for r in attendance_records.values() if r['department'] == department]

    root = ET.Element("AttendanceRecords")
    for record in filtered_records:
        record_elem = ET.SubElement(root, "AttendanceRecord")
        ET.SubElement(record_elem, "TrainingName").text = record['training_name']
        ET.SubElement(record_elem, "Date").text = record['date']
        employees_elem = ET.SubElement(record_elem, "Participants")
        for emp in record['participants']:
            emp_elem = ET.SubElement(employees_elem, "Employee")
            ET.SubElement(emp_elem, "Name").text = emp['name']
            ET.SubElement(emp_elem, "ID").text = emp['id']
            ET.SubElement(emp_elem, "Designation").text = emp.get('designation', 'N/A')

    response = make_response(ET.tostring(root, encoding='unicode'))
    response.headers['Content-Type'] = 'application/xml'
    response.headers['Content-Disposition'] = f'attachment; filename=all_attendance_records_{department}.xml'
    return response


@app.route('/export_attendance_record/<record_id>')
def export_attendance_record(record_id):
    if record_id not in attendance_records:
        flash('Record not found')
        return redirect(url_for('attendance'))

    record = attendance_records[record_id]

    root = ET.Element("AttendanceRecord")
    ET.SubElement(root, "TrainingName").text = record['training_name']
    ET.SubElement(root, "Date").text = record['date']
    ET.SubElement(root, "Department").text = record['department']

    participants = ET.SubElement(root, "Participants")
    for emp in record['participants']:
        emp_elem = ET.SubElement(participants, "Employee")
        ET.SubElement(emp_elem, "Name").text = emp['name']
        ET.SubElement(emp_elem, "ID").text = emp['id']
        ET.SubElement(emp_elem, "Designation").text = emp['designation']

    response = make_response(ET.tostring(root, encoding='unicode'))
    response.headers['Content-Type'] = 'application/xml'
    response.headers['Content-Disposition'] = f'attachment; filename=attendance_record_{record_id}.xml'
    return response

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('role_selection'))


if __name__ == '__main__':
    app.run(debug=True)