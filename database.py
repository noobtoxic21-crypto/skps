import sqlite3
import os
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")

def is_postgres():
    return bool(DATABASE_URL and (DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")))

def get_db():
    if is_postgres():
        import psycopg2
        import psycopg2.extras
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.DictCursor)
        return conn
    else:
        DB_PATH = os.path.join(os.path.dirname(__file__), "school_fees.db")
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def execute_query(cursor, query, params=None):
    if params is None:
        params = []
    if is_postgres():
        query = query.replace("?", "%s")
    return cursor.execute(query, params)

def execute_many(cursor, query, params_list):
    if is_postgres():
        query = query.replace("?", "%s")
    return cursor.executemany(query, params_list)

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    if is_postgres():
        tables = [
            """CREATE TABLE IF NOT EXISTS classes (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) NOT NULL UNIQUE,
                category VARCHAR(30) NOT NULL
            );""",
            """CREATE TABLE IF NOT EXISTS fee_heads (
                id SERIAL PRIMARY KEY,
                title VARCHAR(100) NOT NULL,
                type VARCHAR(20) DEFAULT 'MONTHLY'
            );""",
            """CREATE TABLE IF NOT EXISTS class_fee_structure (
                id SERIAL PRIMARY KEY,
                class_id INT REFERENCES classes(id) ON DELETE CASCADE,
                fee_head_id INT REFERENCES fee_heads(id) ON DELETE CASCADE,
                amount DECIMAL(10, 2) NOT NULL,
                academic_year VARCHAR(10) NOT NULL,
                UNIQUE(class_id, fee_head_id, academic_year)
            );""",
            """CREATE TABLE IF NOT EXISTS students (
                id SERIAL PRIMARY KEY,
                admission_no VARCHAR(50) UNIQUE NOT NULL,
                roll_no VARCHAR(20),
                name VARCHAR(100) NOT NULL,
                father_name VARCHAR(100),
                mother_name VARCHAR(100),
                aadhar_no VARCHAR(20),
                contact_no VARCHAR(15),
                address TEXT,
                dob VARCHAR(20),
                gender VARCHAR(10),
                class_id INT REFERENCES classes(id),
                discount_flat DECIMAL(10, 2) DEFAULT 0.00,
                current_balance DECIMAL(10, 2) DEFAULT 0.00
            );""",
            """CREATE TABLE IF NOT EXISTS charge_sheets (
                id SERIAL PRIMARY KEY,
                student_id INT REFERENCES students(id) ON DELETE CASCADE,
                month_year VARCHAR(20) NOT NULL,
                gross_billed DECIMAL(10, 2) NOT NULL,
                discount_applied DECIMAL(10, 2) DEFAULT 0.00,
                previous_due DECIMAL(10, 2) NOT NULL,
                total_payable DECIMAL(10, 2) NOT NULL,
                amount_paid DECIMAL(10, 2) DEFAULT 0.00,
                status VARCHAR(20) DEFAULT 'UNPAID',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );""",
            """CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                receipt_no VARCHAR(50) UNIQUE NOT NULL,
                student_id INT REFERENCES students(id),
                amount_paid DECIMAL(10, 2) NOT NULL,
                payment_mode VARCHAR(20) NOT NULL,
                reference_no VARCHAR(100),
                collected_by VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );""",
            """CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(100) NOT NULL,
                full_name VARCHAR(100) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'CASHIER',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );"""
        ]
        for tbl_sql in tables:
            cursor.execute(tbl_sql)
            
        # Migrate new columns for PostgreSQL if existing table lacks them
        for col, coltype in [('mother_name', 'VARCHAR(100)'), ('aadhar_no', 'VARCHAR(20)'), ('address', 'TEXT'), ('dob', 'VARCHAR(20)'), ('gender', 'VARCHAR(10)')]:
            try:
                cursor.execute(f"ALTER TABLE students ADD COLUMN {col} {coltype};")
            except Exception:
                conn.rollback()
    else:
        tables = [
            """CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL
            );""",
            """CREATE TABLE IF NOT EXISTS fee_heads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                type TEXT DEFAULT 'MONTHLY'
            );""",
            """CREATE TABLE IF NOT EXISTS class_fee_structure (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
                fee_head_id INTEGER NOT NULL REFERENCES fee_heads(id) ON DELETE CASCADE,
                amount REAL NOT NULL,
                academic_year TEXT NOT NULL,
                UNIQUE(class_id, fee_head_id, academic_year)
            );""",
            """CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admission_no TEXT UNIQUE NOT NULL,
                roll_no TEXT,
                name TEXT NOT NULL,
                father_name TEXT,
                mother_name TEXT,
                aadhar_no TEXT,
                contact_no TEXT,
                address TEXT,
                dob TEXT,
                gender TEXT,
                class_id INTEGER REFERENCES classes(id),
                discount_flat REAL DEFAULT 0.00,
                current_balance REAL DEFAULT 0.00
            );""",
            """CREATE TABLE IF NOT EXISTS charge_sheets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                month_year TEXT NOT NULL,
                gross_billed REAL NOT NULL,
                discount_applied REAL DEFAULT 0.00,
                previous_due REAL NOT NULL,
                total_payable REAL NOT NULL,
                amount_paid REAL DEFAULT 0.00,
                status TEXT DEFAULT 'UNPAID',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );""",
            """CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_no TEXT UNIQUE NOT NULL,
                student_id INTEGER NOT NULL REFERENCES students(id),
                amount_paid REAL NOT NULL,
                payment_mode TEXT NOT NULL,
                reference_no TEXT,
                collected_by TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );""",
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'CASHIER',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );"""
        ]
        for tbl_sql in tables:
            cursor.execute(tbl_sql)

        # Migrate new columns for SQLite if existing table lacks them
        cursor.execute("PRAGMA table_info(students)")
        existing_cols = [row['name'] for row in cursor.fetchall()]
        for col, coltype in [('mother_name', 'TEXT'), ('aadhar_no', 'TEXT'), ('address', 'TEXT'), ('dob', 'TEXT'), ('gender', 'TEXT')]:
            if col not in existing_cols:
                cursor.execute(f"ALTER TABLE students ADD COLUMN {col} {coltype}")

    conn.commit()

    # Seed Default Users if empty
    cursor.execute("SELECT COUNT(*) FROM users")
    res = cursor.fetchone()
    count = res[0] if res else 0
    if count == 0:
        default_users = [
            ('admin', 'skps2131', 'Principal / Admin', 'ADMIN'),
            ('cashier1', 'cashier123', 'Counter Cashier', 'CASHIER')
        ]
        execute_many(
            cursor,
            "INSERT INTO users (username, password, full_name, role) VALUES (?, ?, ?, ?)",
            default_users
        )
        conn.commit()
    else:
        execute_query(cursor, "UPDATE users SET password = ? WHERE username = ?", ['skps2131', 'admin'])
        conn.commit()

    conn.close()

def seed_db():
    init_db()
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM classes")
    res = cursor.fetchone()
    count = res[0] if res else 0
    if count > 0:
        conn.close()
        return

    classes_data = [
        ('Nursery', 'PRE_PRIMARY'),
        ('LKG', 'PRE_PRIMARY'),
        ('UKG', 'PRE_PRIMARY'),
        ('Class 1', 'PRIMARY'),
        ('Class 2', 'PRIMARY'),
        ('Class 3', 'PRIMARY'),
        ('Class 4', 'PRIMARY'),
        ('Class 5', 'PRIMARY'),
        ('Class 6', 'MIDDLE'),
        ('Class 7', 'MIDDLE'),
        ('Class 8', 'MIDDLE'),
        ('Class 9', 'SECONDARY'),
        ('Class 10', 'SECONDARY'),
        ('11th Medical', 'SENIOR_SECONDARY'),
        ('11th Non-Medical', 'SENIOR_SECONDARY'),
        ('11th Commerce', 'SENIOR_SECONDARY'),
        ('11th Arts', 'SENIOR_SECONDARY'),
        ('12th Medical', 'SENIOR_SECONDARY'),
        ('12th Non-Medical', 'SENIOR_SECONDARY'),
        ('12th Commerce', 'SENIOR_SECONDARY'),
        ('12th Arts', 'SENIOR_SECONDARY'),
    ]
    execute_many(cursor, "INSERT INTO classes (name, category) VALUES (?, ?)", classes_data)

    fee_heads_data = [
        ('Tuition Fee', 'MONTHLY'),
        ('Lab Fee', 'MONTHLY'),
        ('Annual Maintenance', 'ANNUAL'),
        ('Computer & Smart Class', 'MONTHLY'),
        ('Transport Fee', 'MONTHLY'),
    ]
    execute_many(cursor, "INSERT INTO fee_heads (title, type) VALUES (?, ?)", fee_heads_data)

    conn.commit()

    cursor.execute("SELECT id, name FROM classes")
    class_map = {row['name']: row['id'] for row in cursor.fetchall()}

    cursor.execute("SELECT id, title FROM fee_heads")
    head_map = {row['title']: row['id'] for row in cursor.fetchall()}

    acad_year = '2026-2027'
    structure_data = []

    for c_name, c_id in class_map.items():
        if 'PRE_PRIMARY' in [c[1] for c in classes_data if c[0] == c_name]:
            tuition = 1500.00
            comp = 200.00
        elif 'PRIMARY' in [c[1] for c in classes_data if c[0] == c_name]:
            tuition = 2200.00
            comp = 300.00
        elif 'MIDDLE' in [c[1] for c in classes_data if c[0] == c_name]:
            tuition = 2800.00
            comp = 400.00
        elif 'SECONDARY' in [c[1] for c in classes_data if c[0] == c_name]:
            tuition = 3500.00
            comp = 500.00
        else:
            tuition = 4500.00
            comp = 600.00

        structure_data.append((c_id, head_map['Tuition Fee'], tuition, acad_year))
        structure_data.append((c_id, head_map['Computer & Smart Class'], comp, acad_year))

        if 'Medical' in c_name or 'Non-Medical' in c_name:
            structure_data.append((c_id, head_map['Lab Fee'], 800.00, acad_year))

    execute_many(
        cursor,
        "INSERT INTO class_fee_structure (class_id, fee_head_id, amount, academic_year) VALUES (?, ?, ?, ?)",
        structure_data
    )

    sample_students = [
        ('ADM-2026-001', '101', 'Aarav Sharma', 'Rajesh Sharma', 'Sunita Sharma', '1234-5678-9012', '9876543210', 'Sector 15, Chandigarh', '2015-05-12', 'Male', class_map['Class 5'], 200.00, 2300.00),
        ('ADM-2026-002', '102', 'Ananya Verma', 'Suresh Verma', 'Anita Verma', '2345-6789-0123', '9876543211', 'Model Town, Ambala', '2015-08-20', 'Female', class_map['Class 5'], 0.00, 0.00),
        ('ADM-2026-003', '201', 'Rohan Gupta', 'Vikas Gupta', 'Meena Gupta', '3456-7890-1234', '9876543212', 'Urban Estate, Patiala', '2009-02-14', 'Male', class_map['11th Non-Medical'], 500.00, 5400.00),
        ('ADM-2026-004', '202', 'Priya Singh', 'Harpreet Singh', 'Gurpreet Kaur', '4567-8901-2345', '9876543213', 'Phase 7, Mohali', '2009-11-05', 'Female', class_map['11th Non-Medical'], 0.00, 0.00),
        ('ADM-2026-005', '301', 'Vivaan Patel', 'Amit Patel', 'Neha Patel', '5678-9012-3456', '9876543214', 'Zirakpur Campus', '2022-01-18', 'Male', class_map['Nursery'], 0.00, 1700.00),
        ('ADM-2026-006', '401', 'Ishita Mehra', 'Sanjeev Mehra', 'Pooja Mehra', '6789-0123-4567', '9876543215', 'Panchkula Sector 8', '2010-04-30', 'Female', class_map['Class 10'], 0.00, 4000.00),
        ('ADM-2026-007', '402', 'Kabir Malhotra', 'Raman Malhotra', 'Kavita Malhotra', '7890-1234-5678', '9876543216', 'Sector 22, Chandigarh', '2010-07-22', 'Male', class_map['Class 10'], 300.00, 0.00),
        ('ADM-2026-008', '501', 'Diya Joshi', 'Manoj Joshi', 'Rekha Joshi', '8901-2345-6789', '9876543217', 'Phase 3B2, Mohali', '2008-09-15', 'Female', class_map['12th Commerce'], 0.00, 5100.00),
    ]

    execute_many(
        cursor,
        """INSERT INTO students (admission_no, roll_no, name, father_name, mother_name, aadhar_no, contact_no, address, dob, gender, class_id, discount_flat, current_balance)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        sample_students
    )

    conn.commit()

    cursor.execute("SELECT id, current_balance, discount_flat FROM students")
    students = cursor.fetchall()
    
    for st in students:
        if st['current_balance'] > 0:
            execute_query(
                cursor,
                """INSERT INTO charge_sheets (student_id, month_year, gross_billed, discount_applied, previous_due, total_payable, amount_paid, status)
                   VALUES (?, ?, ?, ?, ?, ?, 0.00, 'UNPAID')""",
                (st['id'], 'September 2026', st['current_balance'] + st['discount_flat'], st['discount_flat'], 0.00, st['current_balance'])
            )

    conn.commit()
    conn.close()

if __name__ == "__main__":
    seed_db()
    print("Database initialized and migrated with rich student fields.")
