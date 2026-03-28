from flask import Flask, render_template, request, redirect, session, send_file
import mysql.connector
import random
import string
from datetime import datetime, timedelta
import qrcode
import os
import secrets
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from io import BytesIO

app = Flask(__name__)
app.secret_key = "super_secret_key"

# 🔌 DB
def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        ssl_disabled=True
    )

# 🧹 Cleanup
def cleanup_expired():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM ST_TABLE
        WHERE STATUS='PENDING'
        AND CREATED_AT < NOW() - INTERVAL 5 MINUTE
    """)
    conn.commit()
    cursor.close()
    conn.close()

# 🎯 REG_ID
def generate_reg_id():
    year = str(datetime.utcnow().year)[-2:]
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"EV{year}{rand}"

# 🔐 TOKEN
def generate_token():
    return secrets.token_urlsafe(16)

# 🔳 QR
def generate_qr(reg_id):
    upi = f"upi://pay?pa=amindayalamanoj@pingpay&pn=Manoj%20Kumar&am=1&cu=INR&tn={reg_id}"
    if not os.path.exists("static"):
        os.makedirs("static")
    qrcode.make(upi).save(f"static/qr_{reg_id}.png")

# 📄 PDF
def generate_pdf(data):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()

    content = [
        Paragraph("Event Registration Receipt", styles['Title']),
        Spacer(1, 20),
        Paragraph(f"Name: {data['Na_ME']}", styles['Normal']),
        Paragraph(f"HTNO: {data['HTNO']}", styles['Normal']),
        Paragraph(f"Branch: {data['BRANCH']}", styles['Normal']),
        Paragraph(f"Year: {data['PY']}", styles['Normal']),
        Paragraph(f"Phone: {data['PMBNO']}", styles['Normal']),
        Paragraph(f"WhatsApp: {data['WTNO']}", styles['Normal']),
        Paragraph(f"Registration ID: {data['REG_ID']}", styles['Normal']),
        Spacer(1, 20),
        Paragraph("Payment Status: SUCCESS", styles['Normal']),
        Paragraph(f"Date: {datetime.utcnow()}", styles['Normal'])
    ]

    doc.build(content)
    buffer.seek(0)
    return buffer

# 🏠 HOME
@app.route('/')
def home():
    cleanup_expired()

    conn = get_db()
    cursor = conn.cursor()

    reg_id = generate_reg_id()
    token = generate_token()

    cursor.execute("""
        INSERT INTO ST_TABLE (REG_ID, TOKEN, CREATED_AT, STATUS)
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

    cursor.execute("SELECT * FROM ST_TABLE WHERE TOKEN=%s", (token,))
    data = cursor.fetchone()

    cursor.close()
    conn.close()

    if not data:
        return redirect('/')

    reg_id = data['REG_ID']
    created_at = data['CREATED_AT']

    elapsed = (datetime.utcnow() - created_at).total_seconds()
    remaining = int(300 - elapsed)

    if remaining <= 0:
        return redirect('/')

    return render_template(
        "payment.html",
        reg_id=reg_id,
        qr_file=f"qr_{reg_id}.png",
        remaining_seconds=remaining
    )

# 🔐 VERIFY
@app.route('/verify', methods=['POST'])
def verify():
    cleanup_expired()

    reg_id = request.form['reg_id']

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM ST_TABLE WHERE REG_ID=%s", (reg_id,))
    data = cursor.fetchone()

    if not data or data['STATUS'] != 'PENDING':
        return "Invalid or Used"

    created_at = data['CREATED_AT']

    if datetime.utcnow() - created_at > timedelta(minutes=5):
        return "Expired"

    cursor.close()
    conn.close()

    return redirect(f'/register/{reg_id}')

# 📝 REGISTER
@app.route('/register/<reg_id>')
def register(reg_id):
    return render_template("register.html", reg_id=reg_id)

# 📥 SUBMIT
@app.route('/submit', methods=['POST'])
def submit():
    conn = get_db()
    cursor = conn.cursor()

    reg_id = request.form['reg_id']

    cursor.execute("""
        UPDATE ST_TABLE SET
        HTNO=%s, Na_ME=%s, PY=%s, BRANCH=%s,
        PMBNO=%s, WTNO=%s, STATUS='REGISTERED'
        WHERE REG_ID=%s
    """, (
        request.form['htno'],
        request.form['name'],
        request.form['py'],
        request.form['branch'],
        request.form['phone'],
        request.form['whatsapp'],
        reg_id
    ))

    conn.commit()
    cursor.close()
    conn.close()

    session['reg_id'] = reg_id

    return redirect('/success')

# 🎉 SUCCESS
@app.route('/success')
def success():
    reg_id = session.get('reg_id')
    if not reg_id:
        return redirect('/')
    return render_template("success.html", reg_id=reg_id)

# 📄 DOWNLOAD PDF
@app.route('/download')
def download():
    reg_id = session.get('reg_id')

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM ST_TABLE WHERE REG_ID=%s", (reg_id,))
    data = cursor.fetchone()

    cursor.close()
    conn.close()

    pdf = generate_pdf(data)

    return send_file(pdf, as_attachment=True,
                     download_name=f"{reg_id}.pdf",
                     mimetype='application/pdf')

if __name__ == '__main__':
    app.run()
