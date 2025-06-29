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

        record_id = str(len(training_records) + 1)
        training_records[record_id] = {
            'id': record_id,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'department': department,
            'training_name': training_data.get('training_name', 'Unnamed Training'),
            'assigned_employees': [e['name'] for e in departments_employees[department]
                                 if e['id'] in assigned_employees],
            'xml_content': ET.tostring(root, encoding='unicode')
        }

        flash('Training content saved successfully!', 'success')
        return redirect(url_for('dept_training_content'))

    field_names = session.get('training_fields', [])
    existing_values = {}
    employees = departments_employees.get(department, [])

    if os.path.exists(filepath):
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            if len(root) > 0:
                existing_values = {elem.tag: elem.text for elem in root[0]
                                 if elem.tag != 'AssignedEmployees'}
        except ET.ParseError:
            pass

    dept_records = [r for r in training_records.values()
                   if r['department'] == department]

    return render_template('Department/training_content.html',
                         department=department,
                         field_names=field_names,
                         existing_values=existing_values,
                         employees=employees,
                         training_records=dept_records,
                         datetime=datetime)


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
    return render_template('Department/attendance.html', employees=employees, department=department)


@app.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    department = session.get('department')
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        employee_id = request.form.get('employee_id')

        if department and name and email and employee_id:
            new_employee = {
                'id': employee_id,
                'name': name,
                'email': email,
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
    department = session.get('department')
    if request.method == 'POST':
        training_name = request.form.get('training_name')
        present_employee_ids = request.form.getlist('present')

        # In a real app, you would save this to a database
        print(f"Training: {training_name}")
        print(f"Present employees: {present_employee_ids}")

        return redirect(url_for('dashboard'))

    return redirect(url_for('dept_att'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('role_selection'))


if __name__ == '__main__':
    app.run(debug=True)