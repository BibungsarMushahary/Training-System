from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
import xml.etree.ElementTree as ET
from flask import make_response
import os
import io
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
training_records = {dept: {} for dept in departments_employees.keys()}
attendance_records = {dept: {} for dept in departments_employees.keys()}

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

        try:
            file.save(filepath)

            session[f'{department}_training_fields'] = []

            if filename.endswith('.xml'):
                tree = ET.parse(filepath)
                root = tree.getroot()
                if len(root) > 0:
                    field_names = [elem.tag for elem in root[0]]
                    session[f'{department}_training_fields'] = field_names
                    flash('XML file successfully uploaded')
                else:
                    os.remove(filepath)
                    flash('XML file has no content')
                    return redirect(request.url)

            elif filename.endswith('.xlsx'):
                wb = load_workbook(filepath)
                sheet = wb.active
                headers = [cell.value for cell in next(sheet.iter_rows(min_row=1, max_row=1))]
                session[f'{department}_training_fields'] = headers
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


        record_id = str(len(training_records[department]) + 1)
        record_data = training_data.copy()
        record_data['id'] = record_id
        record_data['date'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        record_data['department'] = department
        record_data['assigned_employees'] = [
            e['id'] for e in departments_employees[department] if e['id'] in assigned_employees
        ]
        training_records[department][record_id] = record_data

        flash('Training content saved successfully!', 'success')
        return redirect(url_for('dept_training_content'))


    field_names = session.get(f'{department}_training_fields', [])
    employees = departments_employees.get(department, [])


    dept_records = list(training_records.get(department, {}).values())

    return render_template('Department/training_content.html',
                           department=department,
                           field_names=field_names,
                           existing_values={},
                           employees=employees,
                           training_records=dept_records,
                           datetime=datetime)


@app.route('/edit_training/<record_id>', methods=['GET', 'POST'])
def edit_training(record_id):
    if 'department' not in session:
        return redirect(url_for('logout'))

    department = session['department']
    field_names = session.get(f'{department}_training_fields', [])
    employees = departments_employees.get(department, [])

    if record_id not in training_records[department]:
        flash('Training record not found', 'error')
        return redirect(url_for('dept_training_content'))

    record = training_records[department][record_id]

    if request.method == 'POST':
        updated_data = request.form.to_dict()
        assigned_employees = request.form.getlist('assigned_employees')

        # Update fields
        for field in field_names:
            if field in updated_data:
                record[field] = updated_data[field]

        record['training_name'] = updated_data.get('training_name', record.get('training_name', 'Unnamed'))
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
    for record in training_records.get(department, {}).values():
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
        for emp_id in record['assigned_employees']:
            emp = next((e for e in departments_employees[department] if e['id'] == emp_id), None)
            if emp:
                ET.SubElement(employees_elem, "Employee").text = emp['name']

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

    filtered_records = [r for r in training_records.get(department, {}).values()]


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
    if not department:
        return redirect(url_for('logout'))

    employees = departments_employees.get(department, [])
    dept_trainings = training_records.get(department, {})

    return render_template('Department/attendance.html',
                           department=department,
                           departments_employees=departments_employees,
                           employees=employees,
                           training_records=dept_trainings,  # Pass only department-specific records
                           attendance_records=attendance_records.get(department, {}))


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


    training_record = training_records[department].get(training_id)
    if not training_record:
        flash('Training record not found', 'error')
        return redirect(url_for('attendance'))


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


    record_id = str(len(attendance_records[department]) + 1)
    attendance_records[department][record_id] = {
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
    today = datetime.now().strftime('%Y-%m-%d')

    return render_template('Department/attendance.html',
                         department=department,
                         departments_employees=departments_employees,
                         employees=departments_employees.get(department, []),
                         training_records=training_records.get(department, {}),
                         attendance_records=attendance_records.get(department, {}),
                         current_date=today)

@app.route('/export_attendance_period')
def export_attendance_period():
    department = request.args.get('department')
    month = request.args.get('month')
    year = request.args.get('year')

    filtered_records = []
    for record in attendance_records.get(department, {}).values():
            record_date = datetime.strptime(record['date'], '%Y-%m-%d %H:%M')
            if (not month or record_date.month == int(month)) and \
                    (not year or record_date.year == int(year)):
                filtered_records.append(record)

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


@app.route('/department_report')
def department_report():
    if session.get('role') not in ['ld_admin'] + [f"{dept.lower()}_admin" for dept in departments_employees.keys()]:
        return redirect(url_for('logout'))

    department = request.args.get('department', session.get('department'))
    if not department:
        return redirect(url_for('logout'))

    stats = {
        'total_trainings': len(training_records.get(department, {})),
        'total_attendance_records': len(attendance_records.get(department, {})),
        'unique_employees_trained': len(set(
            emp['id']
            for record in attendance_records.get(department, {}).values()
            for emp in record['participants']
        )),
        'total_employees': len(departments_employees.get(department, []))
    }

    return render_template('Department/report.html',
                         department=department,
                         trainings=list(training_records.get(department, {}).values()),
                         attendance_records=attendance_records.get(department, {}),
                         training_records=training_records,
                         stats=stats,
                         departments_employees=departments_employees)


@app.route('/export_report')
def export_report():
    if 'department' not in session:
        return redirect(url_for('logout'))

    department = request.args.get('department', session.get('department'))
    month = request.args.get('month')
    year = request.args.get('year')


    filtered_trainings = []
    filtered_attendance = []

    for record in training_records.get(department, {}).values():
        record_date = datetime.strptime(record['date'], '%Y-%m-%d %H:%M')
        if (not month or record_date.month == int(month)) and \
                (not year or record_date.year == int(year)):
            filtered_trainings.append(record)

    for record in attendance_records.get(department, {}).values():
        record_date = datetime.strptime(record['date'], '%Y-%m-%d %H:%M')
        if (not month or record_date.month == int(month)) and \
                (not year or record_date.year == int(year)):
            filtered_attendance.append(record)


    data = []


    for training in filtered_trainings:
        training_date = datetime.strptime(training['date'], '%Y-%m-%d %H:%M')


        related_attendance = [a for a in filtered_attendance
                              if a['training_name'] == training['training_name']]

        attendance_count = len(related_attendance)
        participants_count = sum(len(a['participants']) for a in related_attendance)
        assigned_count = len(training['assigned_employees'])

        data.append({
            'Record Type': 'Training',
            'Training Name': training['training_name'],
            'Date': training_date.strftime('%Y-%m-%d'),
            'Assigned Employees': assigned_count,
            'Attendance Sessions': attendance_count,
            'Total Participants': participants_count,
            'Attendance Rate': f"{round((participants_count / (assigned_count * attendance_count if attendance_count > 0 else 1)) * 100)}%" if assigned_count > 0 else 'N/A',
            'Details': ', '.join(
                [f"{k}: {v}" for k, v in training.items() if k not in ['date', 'training_name', 'assigned_employees']])
        })


    for attendance in filtered_attendance:
        attendance_date = datetime.strptime(attendance['date'], '%Y-%m-%d %H:%M')
        participants = ', '.join([f"{p['name']} ({p['id']})" for p in attendance['participants']])

        data.append({
            'Record Type': 'Attendance',
            'Training Name': attendance['training_name'],
            'Date': attendance_date.strftime('%Y-%m-%d'),
            'Participants Count': len(attendance['participants']),
            'Participants': participants,
            'Details': ''
        })


    df = pd.DataFrame(data)


    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, sheet_name=f"{department} Report", index=False)


    for column in df:
        column_width = max(df[column].astype(str).map(len).max(), len(column))
        col_idx = df.columns.get_loc(column)
        writer.sheets[f"{department} Report"].set_column(col_idx, col_idx, column_width)

    writer.close()
    output.seek(0)


    filename = f"{department}_training_report"
    if year:
        filename += f"_{year}"
    if month:
        filename += f"_{month}"
    filename += ".xlsx"

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'

    return response


@app.route('/lnd_reports')
def lnd_reports():
    if session.get('role') != 'ld_admin':
        return redirect(url_for('logout'))

    return render_template('L&D/reports.html', departments=departments_employees.keys())

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('role_selection'))


if __name__ == '__main__':
    app.run(debug=True)