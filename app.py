from flask import Flask, render_template, request, redirect
import mysql.connector
import random
import string
from datetime import datetime, timedelta
import qrcode
import os
import secrets

app = Flask(__name__)

# 🔌 DB Connection (ENV VARIABLES)
def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        ssl_disabled=True
    )

# 🧹 Cleanup expired
def cleanup_expired():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM ST_TABLE2
        WHERE STATUS='PENDING'
        AND CREATED_AT < NOW() - INTERVAL 5 MINUTE
    """)

    conn.commit()
    cursor.close()
    conn.close()

# 🎯 Generate REG_ID
def generate_reg_id():
    year = str(datetime.utcnow().year)[-2:]
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"EV{year}{rand}"

# 🔐 Generate TOKEN (SECURE)
def generate_token():
    return secrets.token_urlsafe(16)

# 🔳 Generate QR
def generate_qr(reg_id):
    upi_link = f"upi://pay?pa=amindayalamanoj@pingpay&pn=Manoj%20Kumar&am=1&cu=INR&tn={reg_id}"

    if not os.path.exists("static"):
        os.makedirs("static")

    qrcode.make(upi_link).save(f"static/qr_{reg_id}.png")

# 🏠 HOME
@app.route('/')
def home():
    cleanup_expired()

    conn = get_db()
    cursor = conn.cursor()

    reg_id = generate_reg_id()
    token = generate_token()

    cursor.execute("""
        INSERT INTO ST_TABLE2 (REG_ID, TOKEN, CREATED_AT, STATUS)
        VALUES (%s, %s, %s, %s)
    """, (reg_id, token, datetime.utcnow(), "PENDING"))

    conn.commit()
    cursor.close()
    conn.close()

    generate_qr(reg_id)

    return redirect(f'/payment/{token}')

# 💳 PAYMENT
@app.route('/payment/<token>')
def payment(token):
    cleanup_expired()

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM ST_TABLE2 WHERE TOKEN=%s", (token,))
    data = cursor.fetchone()

    cursor.close()
    conn.close()

    if not data:
        return redirect('/')

    reg_id = data['REG_ID']
    created_at = data['CREATED_AT']

    if isinstance(created_at, str):
        created_at = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")

    elapsed = (datetime.utcnow() - created_at).total_seconds()
    remaining_seconds = int(300 - elapsed)

    if remaining_seconds <= 0:
        return redirect('/')

    return render_template(
        "payment.html",
        reg_id=reg_id,
        qr_file=f"qr_{reg_id}.png",
        remaining_seconds=remaining_seconds
    )

# 🔐 VERIFY
@app.route('/verify', methods=['POST'])
def verify():
    cleanup_expired()

    user_reg = request.form['reg_id']

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM ST_TABLE2 WHERE REG_ID=%s", (user_reg,))
    data = cursor.fetchone()

    if not data:
        return "❌ Invalid REG_ID"

    if data['STATUS'] != 'PENDING':
        return "⚠️ Already used"

    created_at = data['CREATED_AT']

    if isinstance(created_at, str):
        created_at = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")

    if datetime.utcnow() - created_at > timedelta(minutes=5):
        return "⏰ Expired"

    cursor.close()
    conn.close()

    return redirect(f'/register/{user_reg}')

# 📝 REGISTER
@app.route('/register/<reg_id>')
def register(reg_id):
    cleanup_expired()

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM ST_TABLE2 WHERE REG_ID=%s", (reg_id,))
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
    utr = request.form['utr'].strip()

    try:
        # 🔍 STEP 1: Check if UTR already exists (for other users)
        cursor.execute("""
            SELECT REG_ID FROM ST_TABLE2 WHERE utr = %s
        """, (utr,))
        existing = cursor.fetchone()

        if existing and str(existing[0]) != str(reg_id):
            return "❌ This UTR is already used by another user!"

        # ✅ STEP 2: Update safely
        cursor.execute("""
            UPDATE ST_TABLE2
            SET HTNO=%s, Na_ME=%s, PY=%s, BRANCH=%s,
                PMBNO=%s, WTNO=%s, utr=%s, STATUS='REGISTERED'
            WHERE REG_ID=%s
        """, (htno, name, py, branch, phone, whatsapp, utr, reg_id))

        conn.commit()

    # 🔥 STEP 3: Handle race condition (DB-level protection)
    except Exception as e:
        if "Duplicate" in str(e) or "UNIQUE" in str(e):
            return "❌ Duplicate UTR detected! Try another."
        return f"Error: {e}"

    finally:
        cursor.close()
        conn.close()

    return redirect('/success')
# 🎉 SUCCESS
@app.route('/success/<reg_id>')
def success(reg_id):
    return render_template("success.html", reg_id=reg_id)

# 🔥 RUN
if __name__ == '__main__':
    app.run()
