import qrcode
import os
import smtplib
from email.mime.text import MIMEText

sender = os.getenv('EMAIL_USER')
password = os.getenv('EMAIL_PASS')

def generate_qr(data):
    filename = f"static/qr_codes/{data}.png"
    img = qrcode.make(data)
    img.save(filename)
    return filename

def send_email_alert(email, subject, body):
    sender = "akinwumistudents05@gmail.com"
    password = "ygri muzv xpdw futc"

    msg = MIMEText(body, 'html')
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = email

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, email, msg.as_string())
