import sqlite3
from werkzeug.security import generate_password_hash


def init_db():
    conn = sqlite3.connect('training_management.db')
    cursor = conn.cursor()

    # Create tables
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS departments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        designation TEXT,
        department_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (department_id) REFERENCES departments(id)
    );

    CREATE TABLE IF NOT EXISTS training_formats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        department_id INTEGER NOT NULL,
        file_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_type TEXT NOT NULL,
        field_names TEXT NOT NULL,
        uploaded_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (department_id) REFERENCES departments(id)
    );

    CREATE TABLE IF NOT EXISTS training_programs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        department_id INTEGER NOT NULL,
        training_name TEXT NOT NULL,
        training_data TEXT NOT NULL,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (department_id) REFERENCES departments(id)
    );

    CREATE TABLE IF NOT EXISTS training_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        training_id INTEGER NOT NULL,
        employee_id INTEGER NOT NULL,
        assigned_by INTEGER,
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (training_id) REFERENCES training_programs(id),
        FOREIGN KEY (employee_id) REFERENCES employees(id),
        UNIQUE(training_id, employee_id)
    );

    CREATE TABLE IF NOT EXISTS attendance_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        training_id INTEGER NOT NULL,
        session_date TIMESTAMP NOT NULL,
        conducted_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (training_id) REFERENCES training_programs(id)
    );

    CREATE TABLE IF NOT EXISTS attendance_details (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        attendance_id INTEGER NOT NULL,
        employee_id INTEGER NOT NULL,
        attended BOOLEAN DEFAULT TRUE,
        FOREIGN KEY (attendance_id) REFERENCES attendance_records(id),
        FOREIGN KEY (employee_id) REFERENCES employees(id),
        UNIQUE(attendance_id, employee_id)
    );

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        department_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (department_id) REFERENCES departments(id)
    );
    """)

    # Insert initial departments
    departments = ['IS', 'CM', 'EL', 'HR', 'F&S', 'HSE', 'Finance']
    for dept in departments:
        try:
            cursor.execute("INSERT INTO departments (name) VALUES (?)", (dept,))
        except sqlite3.IntegrityError:
            pass  # Department already exists

    # Insert initial admin users (replace with your actual credentials)
    admin_users = [
        ('ldadmin', generate_password_hash('ld123'), 'ld_admin', None),
        ('isadmin', generate_password_hash('is123'), 'dept_admin', 1),
        ('cmadmin', generate_password_hash('cm123'), 'dept_admin', 2),
        ('eladmin', generate_password_hash('el123'), 'dept_admin', 3),
        ('hradmin', generate_password_hash('hr123'), 'dept_admin', 4),
        ('fsadmin', generate_password_hash('fs123'), 'dept_admin', 5),
        ('hseadmin', generate_password_hash('hse123'), 'dept_admin', 6),
        ('financeadmin', generate_password_hash('finance123'), 'dept_admin', 7)
    ]

    for username, pwd_hash, role, dept_id in admin_users:
        try:
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, department_id) VALUES (?, ?, ?, ?)",
                (username, pwd_hash, role, dept_id)
            )
        except sqlite3.IntegrityError:
            pass  # User already exists

    conn.commit()
    conn.close()


if __name__ == '__main__':
    init_db()