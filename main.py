import socket
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
import os

from database import get_db, init_db, seed_db, execute_query, execute_many, is_postgres

app = FastAPI(title="St. Kabir Public School - Internal Fee System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Self-healing static files generator to ensure Render never crashes if static/index.html is missing
def ensure_static_files():
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if not os.path.exists(static_dir):
        os.makedirs(static_dir, exist_ok=True)
    
    html_file = os.path.join(static_dir, "index.html")
    css_file = os.path.join(static_dir, "styles.css")

    if not os.path.exists(css_file):
        with open(css_file, "w", encoding="utf-8") as f:
            f.write("""@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
body { font-family: 'Inter', system-ui, -apple-system, sans-serif; background-color: #f8fafc; color: #0f172a; }
.mono { font-family: 'JetBrains Mono', monospace; }
@media print {
    body * { visibility: hidden; }
    #printable-receipt-area, #printable-receipt-area * { visibility: visible; }
    #printable-receipt-area { position: absolute; left: 0; top: 0; width: 100%; margin: 0; padding: 0; background: white; }
    @page { margin: 5mm; size: auto; }
}
.receipt-thermal { width: 80mm; max-width: 80mm; margin: 0 auto; padding: 10px; font-family: 'Courier New', Courier, monospace; font-size: 12px; line-height: 1.3; color: #000; }
.receipt-a4 { width: 100%; max-width: 800px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 8px; background: white; }
""")

    if not os.path.exists(html_file):
        # Read local index.html if exists elsewhere or write from local template
        source_html = os.path.join(os.path.dirname(__file__), "static", "index.html")
        if os.path.exists(source_html) and source_html != html_file:
            with open(source_html, "r", encoding="utf-8") as rf:
                content = rf.read()
            with open(html_file, "w", encoding="utf-8") as wf:
                wf.write(content)

@app.on_event("startup")
def startup_event():
    ensure_static_files()
    seed_db()

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

# Schemas
class LoginRequest(BaseModel):
    username: str
    password: str

class UserCreateRequest(BaseModel):
    username: str
    password: str
    full_name: str
    role: str

class ClassCreate(BaseModel):
    name: str
    category: str

class FeeHeadCreate(BaseModel):
    title: str
    type: str = "MONTHLY"

class ClassFeeStructureCreate(BaseModel):
    class_id: int
    fee_head_id: int
    amount: float
    academic_year: str

class StudentCreate(BaseModel):
    admission_no: str
    roll_no: Optional[str] = ""
    name: str
    father_name: Optional[str] = ""
    contact_no: Optional[str] = ""
    class_id: int
    discount_flat: float = 0.00
    current_balance: float = 0.00

class StudentUpdate(BaseModel):
    roll_no: Optional[str] = None
    name: Optional[str] = None
    father_name: Optional[str] = None
    contact_no: Optional[str] = None
    class_id: Optional[int] = None
    discount_flat: Optional[float] = None
    current_balance: Optional[float] = None

class GenerateBillsRequest(BaseModel):
    month_year: str
    academic_year: str

class CollectPaymentRequest(BaseModel):
    student_id: int
    amount_paid: float
    payment_mode: str
    reference_no: Optional[str] = ""
    collected_by: str

# ----------------- AUTH & USER MANAGEMENT API -----------------
@app.post("/api/login")
def login(payload: LoginRequest):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor, """
        SELECT id, username, password, full_name, role 
        FROM users 
        WHERE LOWER(username) = LOWER(?)
    """, (payload.username.strip(),))
    user = cursor.fetchone()
    conn.close()

    if not user or user["password"] != payload.password:
        raise HTTPException(status_code=401, detail="Invalid User ID or Password")

    return {
        "id": user["id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "role": user["role"].upper()
    }

@app.get("/api/users")
def list_users():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, full_name, role, created_at FROM users ORDER BY id ASC")
    users = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return users

@app.post("/api/users")
def create_user(payload: UserCreateRequest):
    conn = get_db()
    cursor = conn.cursor()
    try:
        execute_query(cursor, """
            INSERT INTO users (username, password, full_name, role)
            VALUES (?, ?, ?, ?)
        """, (payload.username.strip(), payload.password, payload.full_name, payload.role.upper()))
        conn.commit()
        new_id = getattr(cursor, "lastrowid", None)
        conn.close()
        return {"id": new_id, "username": payload.username, "full_name": payload.full_name, "role": payload.role.upper()}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail="Username / User ID already exists.")

@app.delete("/api/users/{user_id}")
def delete_user(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor, "DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"message": "User account deleted"}

# ----------------- SYSTEM / LAN API -----------------
@app.get("/api/lan-info")
def lan_info():
    return {
        "school_name": "ST. KABIR PUBLIC SCHOOL",
        "local_ip": get_local_ip(),
        "port": 8000,
        "access_url": f"http://{get_local_ip()}:8000"
    }

@app.post("/api/seed-db")
def trigger_seed():
    seed_db()
    return {"message": "Database seeded with sample classes, fee heads, and students."}

# ----------------- MASTER DATA API -----------------
@app.get("/api/classes")
def list_classes():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM classes ORDER BY id ASC")
    classes = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return classes

@app.post("/api/classes")
def create_class(payload: ClassCreate):
    conn = get_db()
    cursor = conn.cursor()
    try:
        execute_query(cursor, "INSERT INTO classes (name, category) VALUES (?, ?)", (payload.name, payload.category))
        conn.commit()
        class_id = getattr(cursor, "lastrowid", None)
        conn.close()
        return {"id": class_id, "name": payload.name, "category": payload.category}
    except Exception:
        conn.close()
        raise HTTPException(status_code=400, detail="Class name already exists.")

@app.delete("/api/classes/{class_id}")
def delete_class(class_id: int):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor, "DELETE FROM classes WHERE id = ?", (class_id,))
    conn.commit()
    conn.close()
    return {"message": "Class deleted"}

@app.get("/api/fee-heads")
def list_fee_heads():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM fee_heads ORDER BY id ASC")
    heads = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return heads

@app.post("/api/fee-heads")
def create_fee_head(payload: FeeHeadCreate):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor, "INSERT INTO fee_heads (title, type) VALUES (?, ?)", (payload.title, payload.type))
    conn.commit()
    head_id = getattr(cursor, "lastrowid", None)
    conn.close()
    return {"id": head_id, "title": payload.title, "type": payload.type}

@app.delete("/api/fee-heads/{head_id}")
def delete_fee_head(head_id: int):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor, "DELETE FROM fee_heads WHERE id = ?", (head_id,))
    conn.commit()
    conn.close()
    return {"message": "Fee head deleted"}

@app.get("/api/class-fee-structure")
def get_fee_structure(academic_year: Optional[str] = "2026-2027"):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor, """
        SELECT cfs.id, cfs.class_id, cfs.fee_head_id, cfs.amount, cfs.academic_year,
               c.name as class_name, fh.title as fee_head_title, fh.type as fee_head_type
        FROM class_fee_structure cfs
        JOIN classes c ON cfs.class_id = c.id
        JOIN fee_heads fh ON cfs.fee_head_id = fh.id
        WHERE cfs.academic_year = ?
        ORDER BY c.id ASC, fh.id ASC
    """, (academic_year,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

@app.post("/api/class-fee-structure")
def set_class_fee_structure(payload: ClassFeeStructureCreate):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor, """
        INSERT INTO class_fee_structure (class_id, fee_head_id, amount, academic_year)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(class_id, fee_head_id, academic_year) 
        DO UPDATE SET amount = excluded.amount
    """, (payload.class_id, payload.fee_head_id, payload.amount, payload.academic_year))
    conn.commit()
    conn.close()
    return {"message": "Class fee structure saved successfully"}

# ----------------- STUDENTS API -----------------
@app.get("/api/students")
def list_students(
    q: Optional[str] = None,
    class_id: Optional[int] = None,
    balance_status: Optional[str] = None
):
    conn = get_db()
    cursor = conn.cursor()
    
    query = """
        SELECT s.*, c.name as class_name, c.category as class_category
        FROM students s
        LEFT JOIN classes c ON s.class_id = c.id
        WHERE 1=1
    """
    params = []

    if q:
        search_pattern = f"%{q.strip()}%"
        query += " AND (s.admission_no LIKE ? OR s.name LIKE ? OR s.father_name LIKE ? OR s.roll_no LIKE ?)"
        params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
    
    if class_id:
        query += " AND s.class_id = ?"
        params.append(class_id)
        
    if balance_status == "DEFAULTER":
        query += " AND s.current_balance > 0"
    elif balance_status == "SETTLED":
        query += " AND s.current_balance <= 0"

    query += " ORDER BY s.id DESC"
    execute_query(cursor, query, params)
    students = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return students

@app.get("/api/students/{student_id}")
def get_student_details(student_id: int):
    conn = get_db()
    cursor = conn.cursor()
    
    execute_query(cursor, """
        SELECT s.*, c.name as class_name, c.category as class_category
        FROM students s
        LEFT JOIN classes c ON s.class_id = c.id
        WHERE s.id = ?
    """, (student_id,))
    student = cursor.fetchone()
    if not student:
        conn.close()
        raise HTTPException(status_code=404, detail="Student not found")
    
    student_dict = dict(student)

    execute_query(cursor, """
        SELECT cfs.amount, fh.title, fh.type
        FROM class_fee_structure cfs
        JOIN fee_heads fh ON cfs.fee_head_id = fh.id
        WHERE cfs.class_id = ?
    """, (student_dict["class_id"],))
    class_fees = [dict(row) for row in cursor.fetchall()]

    execute_query(cursor, """
        SELECT * FROM charge_sheets WHERE student_id = ? ORDER BY id DESC
    """, (student_id,))
    charge_sheets = [dict(row) for row in cursor.fetchall()]

    execute_query(cursor, """
        SELECT * FROM transactions WHERE student_id = ? ORDER BY id DESC
    """, (student_id,))
    transactions = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return {
        "student": student_dict,
        "class_fees": class_fees,
        "charge_sheets": charge_sheets,
        "transactions": transactions
    }

@app.post("/api/students")
def create_student(payload: StudentCreate):
    conn = get_db()
    cursor = conn.cursor()
    try:
        execute_query(cursor, """
            INSERT INTO students (admission_no, roll_no, name, father_name, contact_no, class_id, discount_flat, current_balance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payload.admission_no, payload.roll_no, payload.name,
            payload.father_name, payload.contact_no, payload.class_id,
            payload.discount_flat, payload.current_balance
        ))
        conn.commit()
        student_id = getattr(cursor, "lastrowid", None)
        conn.close()
        return {"id": student_id, **payload.dict()}
    except Exception:
        conn.close()
        raise HTTPException(status_code=400, detail="Admission number already exists.")

@app.put("/api/students/{student_id}")
def update_student(student_id: int, payload: StudentUpdate):
    conn = get_db()
    cursor = conn.cursor()
    
    fields = []
    values = []
    for k, v in payload.dict(exclude_none=True).items():
        fields.append(f"{k} = ?")
        values.append(v)
    
    if not fields:
        conn.close()
        return {"message": "No updates provided"}

    values.append(student_id)
    query = f"UPDATE students SET {', '.join(fields)} WHERE id = ?"
    execute_query(cursor, query, values)
    conn.commit()
    conn.close()
    return {"message": "Student updated successfully"}

@app.delete("/api/students/{student_id}")
def delete_student(student_id: int):
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor, "DELETE FROM students WHERE id = ?", (student_id,))
    conn.commit()
    conn.close()
    return {"message": "Student deleted"}

# ----------------- BILL GENERATION -----------------
@app.post("/api/generate-monthly-bills")
def generate_monthly_bills(payload: GenerateBillsRequest):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, class_id, discount_flat, current_balance FROM students")
    students = cursor.fetchall()

    if not students:
        conn.close()
        return {"message": "No students found to generate bills for.", "count": 0}

    generated_count = 0
    total_billed_sum = 0.0

    for st in students:
        student_id = st["id"]
        class_id = st["class_id"]
        discount_flat = float(st["discount_flat"] or 0.0)
        previous_due = float(st["current_balance"] or 0.0)

        execute_query(cursor, """
            SELECT SUM(amount) as total_gross 
            FROM class_fee_structure 
            WHERE class_id = ? AND academic_year = ?
        """, (class_id, payload.academic_year))
        res = cursor.fetchone()
        gross_billed = float(res["total_gross"]) if res and res["total_gross"] is not None else 0.0

        net_billed = max(0.0, gross_billed - discount_flat)
        total_payable = net_billed + previous_due

        execute_query(cursor, """
            INSERT INTO charge_sheets (student_id, month_year, gross_billed, discount_applied, previous_due, total_payable, amount_paid, status)
            VALUES (?, ?, ?, ?, ?, ?, 0.00, 'UNPAID')
        """, (student_id, payload.month_year, gross_billed, discount_flat, previous_due, total_payable))

        execute_query(cursor, """
            UPDATE students SET current_balance = ? WHERE id = ?
        """, (total_payable, student_id))

        generated_count += 1
        total_billed_sum += net_billed

    conn.commit()
    conn.close()

    return {
        "message": f"Successfully generated bills for {generated_count} students for {payload.month_year}.",
        "count": generated_count,
        "total_gross_billed": total_billed_sum
    }

# ----------------- PAYMENT COLLECTION -----------------
@app.post("/api/collect-payment")
def collect_payment(payload: CollectPaymentRequest):
    if payload.amount_paid <= 0:
        raise HTTPException(status_code=400, detail="Amount paid must be greater than zero.")

    conn = get_db()
    cursor = conn.cursor()

    execute_query(cursor, """
        SELECT s.*, c.name as class_name 
        FROM students s
        LEFT JOIN classes c ON s.class_id = c.id
        WHERE s.id = ?
    """, (payload.student_id,))
    student = cursor.fetchone()
    if not student:
        conn.close()
        raise HTTPException(status_code=404, detail="Student not found.")

    student_dict = dict(student)

    timestamp_str = datetime.now().strftime("%Y%m%d")
    cursor.execute("SELECT COUNT(*) FROM transactions")
    tx_count = cursor.fetchone()[0] + 1
    receipt_no = f"REC-{timestamp_str}-{tx_count:04d}"

    execute_query(cursor, """
        INSERT INTO transactions (receipt_no, student_id, amount_paid, payment_mode, reference_no, collected_by)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (receipt_no, payload.student_id, payload.amount_paid, payload.payment_mode, payload.reference_no, payload.collected_by))

    new_balance = float(student_dict["current_balance"]) - payload.amount_paid
    execute_query(cursor, "UPDATE students SET current_balance = ? WHERE id = ?", (new_balance, payload.student_id))

    remaining_payment = payload.amount_paid
    execute_query(cursor, """
        SELECT * FROM charge_sheets 
        WHERE student_id = ? AND status != 'PAID'
        ORDER BY id ASC
    """, (payload.student_id,))
    unpaid_sheets = cursor.fetchall()

    for sheet in unpaid_sheets:
        sheet_id = sheet["id"]
        total_payable = float(sheet["total_payable"])
        amount_paid_so_far = float(sheet["amount_paid"])
        due_on_sheet = total_payable - amount_paid_so_far

        if due_on_sheet <= 0:
            continue

        allocate = min(remaining_payment, due_on_sheet)
        new_sheet_paid = amount_paid_so_far + allocate
        new_status = "PAID" if new_sheet_paid >= total_payable else "PARTIALLY_PAID"

        execute_query(cursor, """
            UPDATE charge_sheets SET amount_paid = ?, status = ? WHERE id = ?
        """, (new_sheet_paid, new_status, sheet_id))

        remaining_payment -= allocate
        if remaining_payment <= 0:
            break

    conn.commit()

    execute_query(cursor, """
        SELECT fh.title, cfs.amount
        FROM class_fee_structure cfs
        JOIN fee_heads fh ON cfs.fee_head_id = fh.id
        WHERE cfs.class_id = ?
    """, (student_dict["class_id"],))
    fee_items = [{"title": r["title"], "amount": float(r["amount"])} for r in cursor.fetchall()]

    conn.close()

    receipt_payload = {
        "school_name": "ST. KABIR PUBLIC SCHOOL",
        "receipt_no": receipt_no,
        "date": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "student": {
            "id": student_dict["id"],
            "name": student_dict["name"],
            "admission_no": student_dict["admission_no"],
            "roll_no": student_dict["roll_no"],
            "class_name": student_dict["class_name"],
            "father_name": student_dict["father_name"],
            "contact_no": student_dict["contact_no"]
        },
        "fee_items": fee_items,
        "previous_balance": float(student_dict["current_balance"]),
        "amount_paid": payload.amount_paid,
        "remaining_balance": new_balance,
        "payment_mode": payload.payment_mode,
        "reference_no": payload.reference_no,
        "collected_by": payload.collected_by
    }

    return {
        "message": "Payment collected successfully.",
        "receipt": receipt_payload
    }

# ----------------- REPORTS & DASHBOARD -----------------
@app.get("/api/reports/summary")
def get_reports_summary(role: Optional[str] = Query("CASHIER")):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT SUM(current_balance) FROM students WHERE current_balance > 0")
    row = cursor.fetchone()
    total_dues_pending = float(row[0]) if row and row[0] is not None else 0.0

    cursor.execute("SELECT COUNT(*) FROM students WHERE current_balance > 0")
    defaulters_count = cursor.fetchone()[0]

    if is_postgres():
        cursor.execute("SELECT SUM(amount_paid) FROM transactions WHERE DATE(created_at) = CURRENT_DATE")
    else:
        cursor.execute("SELECT SUM(amount_paid) FROM transactions WHERE date(created_at) = date('now')")

    row_today = cursor.fetchone()
    total_cash_today = float(row_today[0]) if row_today and row_today[0] is not None else 0.0

    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM students WHERE current_balance <= 0")
    settled_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT t.*, s.name as student_name, s.admission_no, c.name as class_name
        FROM transactions t
        JOIN students s ON t.student_id = s.id
        LEFT JOIN classes c ON s.class_id = c.id
        ORDER BY t.id DESC LIMIT 10
    """)
    recent_transactions = [dict(r) for r in cursor.fetchall()]

    conn.close()

    is_admin = (role.upper() == "ADMIN")

    return {
        "role": role.upper(),
        "is_admin": is_admin,
        "total_dues_pending": total_dues_pending if is_admin else None,
        "defaulters_count": defaulters_count if is_admin else None,
        "total_cash_today": total_cash_today if is_admin else None,
        "total_students": total_students,
        "settled_count": settled_count,
        "recent_transactions": recent_transactions
    }

# Serve static frontend files
static_path = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_path):
    os.makedirs(static_path, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/")
def read_root():
    html_file = os.path.join(static_path, "index.html")
    if os.path.exists(html_file):
        return FileResponse(html_file)
    else:
        # Fallback inline response if static/index.html was omitted on GitHub upload
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head><title>St. Kabir Public School - Static Files Missing</title></head>
        <body style="font-family:sans-serif; text-align:center; padding:50px;">
            <h2>⚠️ St. Kabir Public School Fee System</h2>
            <p>The backend is running! However, <b>static/index.html</b> was not found in the GitHub upload.</p>
            <p>Please upload the <b>static</b> folder (containing index.html) to your GitHub repository.</p>
        </body>
        </html>
        """)
