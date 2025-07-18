from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import os
import sqlite3
import face_recognition
import numpy as np
import qrcode
import cv2
import base64
from datetime import datetime
from utils import send_email_alert
from PIL import Image
import io
from functools import wraps

def staff_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('staff_logged_in'):
            flash('Please login as staff to access this page.')
            return redirect(url_for('staff_login'))
        return f(*args, **kwargs)
    return decorated_function


app = Flask(__name__)
# app.permanent_session_lifetime = 0  # immediate expiration
app.secret_key = 'your-secret-key'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

os.makedirs("face_data", exist_ok=True)
os.makedirs("static/qr_codes", exist_ok=True)

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            phone TEXT,
            car_type TEXT,
            car_color TEXT,
            plate_number TEXT UNIQUE,
            qr_code TEXT,
            face_encoding BLOB
        )
    ''')
    conn.commit()
    conn.close()

def generate_qr_code(data, filename):
    qr = qrcode.QRCode(
        version=1, error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10, border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    qr_path = os.path.join('static', 'qr_codes', filename)
    img.save(qr_path)
    return qr_path

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        car_type = request.form['car_type']
        car_color = request.form['car_color']
        plate_number = request.form['plate_number']

        if not all([name, email, phone, car_type, car_color, plate_number]):
            flash("All fields are required.")
            return redirect(url_for('register'))

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE plate_number=?", (plate_number,))
        if cursor.fetchone():
            conn.close()
            flash("Plate number already registered.")
            return redirect(url_for('register'))

        cursor.execute("INSERT INTO users (name, email, phone, car_type, car_color, plate_number) VALUES (?, ?, ?, ?, ?, ?)",
               (name, email, phone, car_type, car_color, plate_number))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return redirect(url_for('register_face', user_id=user_id))
    return render_template('register.html')

@app.route('/register_face/<int:user_id>', methods=['GET', 'POST'])
def register_face(user_id):
    if request.method == 'POST':
        face_image_data = request.form['face_image']
        if not face_image_data:
            flash('No face image provided.')
            return redirect(url_for('register_face', user_id=user_id))

        header, encoded = face_image_data.split(',', 1)
        image_data = base64.b64decode(encoded)
        image = Image.open(io.BytesIO(image_data)).convert('RGB')
        image = image.resize((320, 240))  # Resize to 320x240
        image_np = np.array(image)

        face_encodings = face_recognition.face_encodings(image_np)
        if not face_encodings:
            flash('No face detected. Please try again.')
            return redirect(url_for('register_face', user_id=user_id))

        face_encoding = face_encodings[0]

        qr_code_value = f"user_{user_id}_{datetime.now().timestamp()}"
        qr_filename = f"{qr_code_value}.png"
        generate_qr_code(qr_code_value, qr_filename)

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET face_encoding=?, qr_code=? WHERE id=?",
                       (face_encoding.tobytes(), qr_code_value, user_id))
        conn.commit()
        conn.close()

        qr_image_url = f"qr_codes/{qr_filename}"
        return render_template("download_qrcode.html", qr_image=qr_image_url)

    return render_template('register_face.html', user_id=user_id)

@app.route('/staff_login', methods=['GET', 'POST'])
def staff_login():
    if request.method == 'POST':
        secret = request.form.get('secret_key')
        if secret == "CSC2024/2025":  # your secret key
            session.permanent = True  # session expires when browser/tab closes or reloads
            session['staff_logged_in'] = True
            return redirect(url_for('staff_access'))
        else:
            flash('Invalid secret key.')
    return render_template('staff_login.html')


@app.route('/access')
@staff_login_required
def access_page():
    if not session.get('staff_logged_in'):
        flash('Please login as staff to access this page.')
        return redirect(url_for('staff_login'))
    return render_template('access.html')

@app.route('/staff_access', methods=['GET', 'POST'])
@staff_login_required
def staff_access():
    if request.method == 'POST':
        plate_number = request.form['plate_number']
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE plate_number=?", (plate_number,))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            user_id = user[0]
            return redirect(url_for('verify_face', user_id=user_id))
        else:
            flash("Plate number is invalid.")
    
    return render_template("staff_plate.html")

@app.route('/verify_face/<int:user_id>', methods=['GET', 'POST'])
@staff_login_required
def verify_face(user_id):
    if request.method == 'POST':
        data = request.json
        image_data = data['face_image'].split(',')[1]
        img_array = np.frombuffer(base64.b64decode(image_data), np.uint8)
        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT face_encoding, email, name, plate_number, car_type, car_color FROM users WHERE id=?", (user_id,))
        user = cursor.fetchone()
        conn.close()

        if not user:
            return jsonify({"status": "fail", "message": "User not found."})

        face_encoding_blob, email, name, plate_number, car_type, car_color = user
        if not face_encoding_blob:
            return jsonify({"status": "fail", "message": "No face data registered."})

        known_encoding = np.frombuffer(face_encoding_blob, dtype=np.float64)

        face_locations = face_recognition.face_locations(frame)
        if not face_locations or len(face_locations) != 1:
            return jsonify({"status": "fail", "message": "Face Not Recognized"})

        encoding = face_recognition.face_encodings(frame, face_locations)[0]
        match = face_recognition.compare_faces([known_encoding], encoding)[0]


        if match:
            session['face_verified_user_id'] = user_id
            return jsonify({"status": "success", "redirect": url_for('scan_qr', user_id=user_id)})
        else:
            subject = "Access Alert: Face Mismatch"
            body = render_template('email_alert.html', name=name, alert_type="Face Mismatch", plate_number=plate_number, car_color=car_color, car_type=car_type, timestamp=datetime.now())
            send_email_alert(email, subject, body)
            return jsonify({"status": "fail", "message": "Face mismatch. Alert sent."})

    return render_template('staff_face.html', user_id=user_id)

@app.route('/scan_qr/<int:user_id>')
@staff_login_required
def scan_qr(user_id):
    if session.get('face_verified_user_id') != user_id:
        flash("Face not verified.")
        return redirect(url_for('staff_access'))
    return render_template("staff_qr.html", user_id=user_id)

@app.route('/verify_qr', methods=['POST'])
@staff_login_required
def verify_qr():
    data = request.get_json()
    user_id = data.get('user_id')
    scanned_code = data.get('qr_code')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT qr_code, name, email, plate_number, car_type, car_color FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return jsonify({"status": "fail", "message": "User not found."})

    stored_code, name, email, plate_number, car_type, car_color = user

    if scanned_code == stored_code:
        return jsonify({"status": "success", "message": f"Access granted to {name}."})
    else:
        subject = "Access Alert: QR Code Mismatch"
        body = render_template('email_alert.html', name=name, alert_type="QR Code Mismatch", plate_number=plate_number, car_color=car_color, car_type=car_type, timestamp=datetime.now())
        send_email_alert(email, subject, body)
        return jsonify({"status": "fail", "message": "QR Code mismatch. Alert sent."})
    
@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    return redirect(url_for('staff_login'))



from werkzeug.exceptions import RequestEntityTooLarge

@app.errorhandler(RequestEntityTooLarge)
def handle_large_request(e):
    return "File too large. Max size is 16MB.", 413

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
