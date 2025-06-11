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

app = Flask(__name__)
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
        car_color = request.form['car_color']
        plate_number = request.form['plate_number']

        if not all([name, email, phone, car_color, plate_number]):
            flash("All fields are required.")
            return redirect(url_for('register'))

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE plate_number=?", (plate_number,))
        if cursor.fetchone():
            conn.close()
            flash("Plate number already registered.")
            return redirect(url_for('register'))

        cursor.execute("INSERT INTO users (name, email, phone, car_color, plate_number) VALUES (?, ?, ?, ?, ?)",
                       (name, email, phone, car_color, plate_number))
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
        return render_template("register_face.html", qr_image=qr_image_url)

    return render_template('register_face.html', user_id=user_id)

@app.route('/staff_login', methods=['GET', 'POST'])
def staff_login():
    if request.method == 'POST':
        secret = request.form.get('secret_key')
        if secret == "CSC2024/2025":  # your secret key
            session['staff_logged_in'] = True
            return redirect(url_for('access_page'))
        else:
            flash('Invalid secret key.')
    return render_template('staff_login.html')


@app.route('/access')
def access_page():
    if not session.get('staff_logged_in'):
        flash('Please login as staff to access this page.')
        return redirect(url_for('staff_login'))
    return render_template('access.html')

@app.route('/verify_plate', methods=['POST'])
def verify_plate():
    data = request.json
    plate_number = data.get('plate_number')

    # Extract base64 face image, removing prefix if present
    image_data = data.get('face_image').split(',')[1]

    # Decode image data and convert to numpy array
    img_array = np.frombuffer(base64.b64decode(image_data), np.uint8)
    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    # Load user info and stored face encoding from DB
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, face_encoding, email, name FROM users WHERE plate_number=?", (plate_number,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return jsonify({"status": "fail", "message": "❌ Plate number not found."})

    user_id, face_encoding_blob, email, name = user
    known_encoding = np.frombuffer(face_encoding_blob, dtype=np.float64)

    # Detect faces in the uploaded image
    face_locations = face_recognition.face_locations(frame)
    if not face_locations:
        return jsonify({"status": "fail", "message": "❌ No face detected."})

    if len(face_locations) != 1:
        return jsonify({"status": "fail", "message": "❌ Please ensure only one face is visible."})

    # Get encoding for the detected face
    encoding = face_recognition.face_encodings(frame, face_locations)[0]

    # Compare face encoding with stored encoding
    match = face_recognition.compare_faces([known_encoding], encoding)[0]

    if match:
        # Store user ID in session to track successful face verification
        session['face_verified_user_id'] = user_id
        return jsonify({
            "status": "success",
            "user_id": user_id,
            "message": f"✅ Face matched for {name}. Proceed to scan QR."
        })
    else:
        subject = "Access Alert: Face Mismatch"
        body = f"Hi {name},\n\nAn unauthorized face scan was attempted at {datetime.now()}."
        send_email_alert(email, subject, body)
        return jsonify({"status": "fail", "message": "❌ Face mismatch. Alert email sent."})



@app.route('/verify_qr', methods=['POST'])
def verify_qr():
    data = request.json
    user_id = data.get('user_id')
    scanned_qr = data.get('qr_code')

    verified_user_id = session.get('face_verified_user_id')
    if int(verified_user_id) != int(user_id):
        return jsonify({"status": "fail", "message": "❌ Face not verified. Please verify face first."})

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT email, qr_code, name FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return jsonify({"status": "fail", "message": "User not found"})

    email, correct_qr, name = user
    if scanned_qr == correct_qr:
        # Clear session so it can't be reused
        session.pop('face_verified_user_id', None)
        return jsonify({
            "status": "success",
            "message": f"✅ Access Granted, {name}! Face and QR Code matched.",
            "name": name
        })
    else:
        subject = "Access Alert: QR Code Mismatch"
        body = f"Hi {name},\n\nAn unauthorized QR code scan was attempted at {datetime.now()}."
        send_email_alert(email, subject, body)
        return jsonify({"status": "fail", "message": "❌ QR code mismatch. Alert email sent."})

from werkzeug.exceptions import RequestEntityTooLarge

@app.errorhandler(RequestEntityTooLarge)
def handle_large_request(e):
    return "File too large. Max size is 16MB.", 413

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
