from flask import Flask, render_template, request, redirect
import mysql.connector
import random
import string
from datetime import datetime, timedelta, timezone
import qrcode
import os
from dotenv import load_dotenv
import os

# 🔐 Load env
load_dotenv()

app = Flask(__name__)

# 🔌 DB Connection
def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 3306)),  # ✅ fallback
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

# 🎯 Generate REG_ID
def generate_reg_id():
    year = str(datetime.now(timezone.utc).year)[-2:]
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"EV{year}{rand}"

# 🔳 Generate QR
def generate_qr(reg_id):
    upi_link = f"upi://pay?pa=amindayalamanoj@pingpay&pn=Manoj%20Kumar&am=1&cu=INR&tn={reg_id}"

    if not os.path.exists("static"):
        os.makedirs("static")

    path = f"static/qr_{reg_id}.png"
    qrcode.make(upi_link).save(path)
    return path

# 🏠 HOME
@app.route('/')
def home():
    conn = get_db()
    cursor = conn.cursor()

    # 🧹 delete expired
    cursor.execute("""
        DELETE FROM ST_TABLE
        WHERE STATUS='PENDING'
        AND CREATED_AT < NOW() - INTERVAL 5 MINUTE
    """)
    conn.commit()

    # 🎯 new REG_ID
    reg_id = generate_reg_id()

    cursor.execute("""
        INSERT INTO ST_TABLE (REG_ID, CREATED_AT, STATUS)
        VALUES (%s, %s, %s)
    """, (reg_id, datetime.utcnow(), "PENDING"))

    conn.commit()
    cursor.close()
    conn.close()

    generate_qr(reg_id)

    return redirect(f'/payment/{reg_id}')

# 💳 PAYMENT
@app.route('/payment/<reg_id>')
def payment(reg_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM ST_TABLE WHERE REG_ID=%s", (reg_id,))
    data = cursor.fetchone()

    cursor.close()
    conn.close()

    if not data:
        return "❌ Invalid Link"

    created_at = data['CREATED_AT']

    # 🔥 fix datetime
    if isinstance(created_at, str):
        created_at = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")

    created_at = created_at.replace(tzinfo=timezone.utc)

    expiry_time = created_at + timedelta(minutes=5)

    return render_template(
        "payment.html",
        reg_id=reg_id,
        qr_file=f"qr_{reg_id}.png",
        expiry_time=expiry_time.isoformat()
    )

# 🔐 VERIFY
@app.route('/verify', methods=['POST'])
def verify():
    user_reg = request.form['reg_id']

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM ST_TABLE WHERE REG_ID=%s", (user_reg,))
    data = cursor.fetchone()

    if not data:
        return "❌ Invalid REG_ID"

    if data['STATUS'] != 'PENDING':
        return "⚠️ Already used"

    created_at = data['CREATED_AT']
    if isinstance(created_at, str):
        created_at = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")

    if datetime.utcnow() - created_at > timedelta(minutes=5):
        cursor.execute("DELETE FROM ST_TABLE WHERE REG_ID=%s", (user_reg,))
        conn.commit()
        return "⏰ Expired"

    cursor.close()
    conn.close()

    return redirect(f'/register/{user_reg}')

# 📝 REGISTER
@app.route('/register/<reg_id>')
def register(reg_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM ST_TABLE WHERE REG_ID=%s", (reg_id,))
    data = cursor.fetchone()

    cursor.close()
    conn.close()

    if not data or data['STATUS'] != 'PENDING':
        return redirect('/')

    return render_template("register.html", reg_id=reg_id)

# 📥 SUBMIT
@app.route('/submit', methods=['POST'])
def submit():
    conn = get_db()
    cursor = conn.cursor()

    reg_id = request.form['reg_id']
    htno = request.form['htno']
    name = request.form['name']
    py = request.form.get('py')
    branch = request.form['branch']
    phone = request.form['phone']
    whatsapp = request.form['whatsapp']

    try:
        cursor.execute("""
            UPDATE ST_TABLE
            SET HTNO=%s, Na_ME=%s, PY=%s, BRANCH=%s, PMBNO=%s, WTNO=%s, STATUS='REGISTERED'
            WHERE REG_ID=%s
        """, (htno, name, py, branch, phone, whatsapp, reg_id))

        conn.commit()

    except Exception as e:
        return f"Error: {e}"

    finally:
        cursor.close()
        conn.close()

    return redirect('/success')

# 🎉 SUCCESS
@app.route('/success')
def success():
    return render_template("success.html")

if __name__ == '__main__':
    app.run()
