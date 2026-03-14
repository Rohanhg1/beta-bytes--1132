"""
SmartClinic GeoVoice Receptionist - Email Confirmation Service
Sends appointment confirmation emails via Gmail SMTP.

SETUP:
  1. Enable 2-Step Verification on chethansunny17@gmail.com
  2. Go to: https://myaccount.google.com/apppasswords
  3. Create an App Password for "Mail"
  4. Set the GMAIL_APP_PASSWORD env variable OR paste it directly below.
"""

import smtplib
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Gmail Sender Configuration ────────────────────────────────────────────────
# SMTP login credentials (account that SENDS the email)
GMAIL_SENDER  = os.getenv("GMAIL_SENDER",   "hgrohan501@gmail.com")
GMAIL_APP_PWD = os.getenv("GMAIL_APP_PASSWORD", "")   # loaded from .env

# ALL booking confirmation emails will be sent TO this address
BOOKING_NOTIFY_EMAIL = os.getenv("BOOKING_NOTIFY_EMAIL", "chethansunny17@gmail.com")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def send_appointment_email(
    to_email: str,
    hospital_name: str,
    specialization: str,
    patient_name: str,
    date: str,
    time: str,
    district: str,
) -> bool:
    """
    Send a beautifully formatted appointment confirmation email.
    Always sends to BOOKING_NOTIFY_EMAIL (chethansunny17@gmail.com).
    """
    # Always override to the configured notification inbox
    recipient = BOOKING_NOTIFY_EMAIL

    # ── Sanity check: App Password configured? ────────────────────────────────
    if not GMAIL_APP_PWD or GMAIL_APP_PWD.strip() == "":
        logger.warning("[EMAIL] Gmail App Password not configured. Printing to console instead.")
        print(f"[EMAIL SIMULATION] Would send to: {recipient}")
        return True

    # ── Build rich HTML email ─────────────────────────────────────────────────
    subject = f"🏥 New Booking — {hospital_name} | SmartClinic GeoVoice"

    html_body = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:0 auto;
                background:linear-gradient(135deg,#4f46e5 0%,#ec4899 100%);
                padding:4px;border-radius:16px;">
      <div style="background:#ffffff;border-radius:14px;padding:40px;">

        <div style="text-align:center;margin-bottom:28px;">
          <h1 style="color:#4f46e5;margin:0;font-size:24px;">🏥 SmartClinic GeoVoice</h1>
          <p style="color:#64748b;font-size:13px;margin:4px 0 0;">Voice Booking Confirmation</p>
        </div>

        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;
                    padding:24px;margin-bottom:20px;">
          <h2 style="color:#1e293b;margin-top:0;font-size:16px;
                     border-bottom:2px solid #e2e8f0;padding-bottom:10px;">
            📋 Booking Details
          </h2>
          <table style="width:100%;border-collapse:collapse;">
            <tr>
              <td style="padding:10px 0;color:#64748b;font-weight:600;width:40%;">Hospital</td>
              <td style="padding:10px 0;color:#0f172a;font-weight:600;">{hospital_name}</td>
            </tr>
            <tr style="border-top:1px solid #f1f5f9;">
              <td style="padding:10px 0;color:#64748b;font-weight:600;">Specialization</td>
              <td style="padding:10px 0;color:#0f172a;">{specialization or 'General Physician'}</td>
            </tr>
            <tr style="border-top:1px solid #f1f5f9;">
              <td style="padding:10px 0;color:#64748b;font-weight:600;">Patient</td>
              <td style="padding:10px 0;color:#0f172a;">{patient_name}</td>
            </tr>
            <tr style="border-top:1px solid #f1f5f9;">
              <td style="padding:10px 0;color:#64748b;font-weight:600;">Date</td>
              <td style="padding:10px 0;color:#0f172a;">{date}</td>
            </tr>
            <tr style="border-top:1px solid #f1f5f9;">
              <td style="padding:10px 0;color:#64748b;font-weight:600;">Time</td>
              <td style="padding:10px 0;color:#4f46e5;font-weight:700;">{time}</td>
            </tr>
            <tr style="border-top:1px solid #f1f5f9;">
              <td style="padding:10px 0;color:#64748b;font-weight:600;">District</td>
              <td style="padding:10px 0;color:#0f172a;">{district}</td>
            </tr>
          </table>
        </div>

        <div style="background:linear-gradient(135deg,#4f46e5,#ec4899);
                    border-radius:10px;padding:16px;text-align:center;">
          <p style="color:#fff;margin:0;font-size:13px;">
            ✅ Appointment confirmed via <strong>SmartClinic GeoVoice AI</strong>
          </p>
        </div>

        <p style="color:#94a3b8;font-size:11px;text-align:center;margin-top:20px;">
          This is an automated notification from SmartClinic GeoVoice.
        </p>
      </div>
    </div>
    """

    # ── Send via Gmail SMTP ───────────────────────────────────────────────────
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"SmartClinic GeoVoice <{GMAIL_SENDER}>"
        msg["To"]      = recipient

        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(GMAIL_SENDER, GMAIL_APP_PWD)
            server.sendmail(GMAIL_SENDER, recipient, msg.as_string())

        logger.info(f"[EMAIL] OK: Booking email sent to {recipient}")
        print(f"[EMAIL] OK: Email sent to {recipient}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("[EMAIL] FAILED: Gmail authentication failed. Check your App Password.")
        print("[EMAIL] FAILED: Auth error -- make sure GMAIL_APP_PASSWORD is correct.")
        return False
    except Exception as e:
        logger.error(f"[EMAIL] FAILED: {e}")
        print(f"[EMAIL] FAILED: {e}")
        return False


def send_cancellation_email(
    to_email: str,
    hospital_name: str,
    date: str,
    time: str,
    district: str,
) -> bool:
    """Send an appointment cancellation email."""
    recipient = BOOKING_NOTIFY_EMAIL

    if not GMAIL_APP_PWD or GMAIL_APP_PWD.strip() == "":
        logger.warning("[EMAIL] App Password not configured.")
        return True

    subject = "Appointment Cancelled"

    text_body = f"""Your appointment has been cancelled by admin.

Hospital: {hospital_name}
Date: {date}
Time Slot: {time}
District: {district}
"""
    html_body = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:0 auto;
                background:linear-gradient(135deg,#ef4444 0%,#b91c1c 100%);
                padding:4px;border-radius:16px;">
      <div style="background:#ffffff;border-radius:14px;padding:40px;">
        <h1 style="color:#ef4444;margin:0;font-size:24px;text-align:center;">Appointment Cancelled</h1>
        <p style="color:#64748b;font-size:15px;margin-top:20px;">Your appointment has been cancelled by admin.</p>
        <ul style="list-style:none;padding:0;margin-top:20px;color:#0f172a;line-height:1.6;">
            <li><strong>Hospital:</strong> {hospital_name}</li>
            <li><strong>Date:</strong> {date}</li>
            <li><strong>Time Slot:</strong> {time}</li>
            <li><strong>District:</strong> {district}</li>
        </ul>
      </div>
    </div>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"SmartClinic GeoVoice <{GMAIL_SENDER}>"
        msg["To"]      = recipient
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(GMAIL_SENDER, GMAIL_APP_PWD)
            server.sendmail(GMAIL_SENDER, recipient, msg.as_string())

        logger.info(f"[EMAIL] OK: Cancellation email sent to {recipient}")
        print(f"[EMAIL] OK: Cancellation email sent to {recipient}")
        return True
    except Exception as e:
        logger.error(f"[EMAIL] FAILED: {e}")
        print(f"[EMAIL] FAILED: {e}")
        return False
