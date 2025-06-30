# Smart Vehicle Access Control System



## 1. Overview of Project Architecture

SecureGate operates on a three-phase authentication model:

* **Phase 1**: Registration — Users register their information and facial identity.
* **Phase 2**: Verification — Staff authenticates entries by verifying faces and scanning QR codes.
* **Phase 3**: Monitoring — Alerts are triggered for any mismatch or unauthorized access attempts.

---

## 2. Technology Stack and Detailed Components

### Backend: **Python + Flask**

* **Flask** is used to serve web pages and handle form submissions, database queries, and route protection.
* Routes are defined for:

  * Homepage and registration
  * Staff login and access
  * Face verification and QR verification endpoints (AJAX-based)

### Face Recognition: **face\_recognition + OpenCV + Pillow**

* **face\_recognition** handles detection and encoding of facial features.
* **OpenCV** is used to process webcam-captured images submitted from the frontend.
* **Pillow (PIL)** helps in image resizing and format conversion.
* Images are captured in the frontend using HTML5 webcam access (JavaScript), converted to base64, and decoded on the server for processing.

### QR Code Generation: **qrcode**

* QR codes uniquely represent users during registration.
* Stored locally in the `static/qr_codes/` directory.
* Encodes values like `user_<id>_<timestamp>` for uniqueness.

### Database: **SQLite**

* Lightweight database to store:

  * User information (name, email, phone, plate number, car color)
  * Face encodings (as binary blobs)
  * QR code identifiers
* Queries ensure unique plate numbers and enable retrieval based on plate entries.
* Database file: `database.db`

### Frontend: **HTML, CSS, JavaScript**

* Jinja templates (`register.html`, `register_face.html`, `access.html`, `email_alert.html`) render dynamic content.
* JavaScript is used for:

  * Webcam access and image capture
  * AJAX calls for verification endpoints
  * QR code scanning via webcam (using client-side libraries or hardware scanners)

### Email Notifications: **smtplib + Gmail SMTP**

* Sends alerts when:

  * Face does not match registered encoding
  * QR code does not match user’s assigned code
* Emails include:

  * Type of alert (face mismatch or QR mismatch)
  * Time of attempt
  * Plate number
  * (Optionally) IP address or location details
* Uses Gmail SMTP on port 587; App Passwords are recommended for secure access.
* Email body is rendered from an HTML template (`email_alert.html`) for a styled appearance.

### Session and Security: **Flask Sessions**

* Session variables track login state of staff and successful face verifications.
* Routes like `/verify_plate, /verify_qr_code and /verify_face` are protected from unauthorized users by checking session flags.
* Face verification must be completed before QR code is checked.

---

## 3. Project Structure

```bash
PythonProject/
├── app.py                  # Main Flask application
├── utils.py                # Helper functions: email and QR code
├── database.db             # SQLite database
├── templates/
│   ├── home.html
│   ├── register.html
│   ├── register_face.html
│   ├── staff_login.html
│   ├── access.html
│   └── email_alert.html
├── static/
│   └── qr_codes/           # Stores generated QR codes
├── face_data/              # Directory to store or cache facial data (if needed)
└── requirements.txt        # List of required Python packages
```

---

## 4. How to Set Up and Run

### Prerequisites

* Python 3.9.5
* Pip

### Installation

```bash
git clone https://github.com/TripleHay321/CSC_FINAL_2024-2025
cd CSC_FINAL_2024-2025
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```


### Run the App

```bash
python app.py
```

Then open your browser at: `http://127.0.0.1:5000/`

---

## 5. Functional Flow

1. **User Registration**

   * Fills form (name, email, car info, etc.)
   * Face is captured and encoded
   * QR code is generated and displayed for download

2. **Staff Login and Verification**

   * Enters a secret passcode to access restricted portal
   * Inputs plate number to retrieve user
   * Captures and verifies face
   * Upon face match, proceeds to QR scanning
   * Successful dual match = access granted
   * Mismatch = email alert

3. **Email Alert Format**

   * Subject: "Access Alert: \[Type]"
   * Includes: name, plate number, timestamp, alert reason
   * Styled HTML using inline CSS

---

