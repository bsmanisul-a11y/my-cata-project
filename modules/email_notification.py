"""
Email Notification Service for Elderly Care & Medication Management Platform
Handles real SMTP dispatch (Gmail, Outlook, custom SMTP) and provides in-app
auditing with responsive HTML email templates for doses, missed meds, appointments, and SOS alerts.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from modules.models import db, NotificationLog, ElderlyProfile, CareCircleMember

# Configuration from environment variables
SMTP_SERVER = os.getenv('SMTP_SERVER', '')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
SMTP_FROM = os.getenv('SMTP_FROM', 'elderlycare.alert@gmail.com')
SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'True').lower() in ('true', '1', 't')

def is_smtp_configured():
    return bool(SMTP_SERVER and SMTP_USER and SMTP_PASSWORD)

def send_email(to_email, recipient_name, subject, html_body, text_body="", notification_type="general", profile_id=None):
    """
    Sends an email to the recipient.
    If SMTP credentials are configured, sends real email via smtplib.
    Always logs the email in the NotificationLog database table so the user & caregivers can view it in the app.
    """
    status = 'Simulated'
    error_msg = None

    if is_smtp_configured():
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"ElderCare Care-Circle <{SMTP_FROM}>"
            msg['To'] = to_email

            if text_body:
                msg.attach(MIMEText(text_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))

            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10)
            if SMTP_USE_TLS:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [to_email], msg.as_string())
            server.quit()
            status = 'Sent'
        except Exception as e:
            status = 'Failed'
            error_msg = str(e)
            print(f"[Email Notification Error] Failed to send email to {to_email}: {e}")
    else:
        # Development / Sandbox Mode - logged locally
        status = 'Simulated (In-App)'

    # Save to database log
    try:
        if profile_id:
            log_entry = NotificationLog(
                profile_id=profile_id,
                recipient_email=to_email,
                recipient_name=recipient_name or 'Caregiver/Senior',
                subject=subject,
                notification_type=notification_type,
                html_content=html_body,
                text_content=text_body or subject,
                status=status,
                sent_at=datetime.now(timezone.utc)
            )
            db.session.add(log_entry)
            db.session.commit()
    except Exception as db_err:
        db.session.rollback()
        print(f"[Email Log DB Error] {db_err}")

    return {
        "success": status in ('Sent', 'Simulated (In-App)'),
        "status": status,
        "error": error_msg
    }

# ----------------- BEAUTIFUL RESPONSIVE HTML EMAIL TEMPLATES -----------------

def get_base_email_template(header_title, header_badge, badge_color, content_html, footer_note=""):
    """Generates an accessible, clean HTML email wrapper."""
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{header_title}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      margin: 0; padding: 0; background-color: #f3f6f9; color: #2d3748;
    }}
    .email-container {{
      max-width: 600px; margin: 20px auto; background-color: #ffffff;
      border-radius: 14px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.06);
      border: 1px solid #e2e8f0;
    }}
    .email-header {{
      background: linear-gradient(135deg, #1e3a8a, #3b82f6);
      padding: 28px 24px; text-align: center; color: #ffffff;
    }}
    .badge {{
      display: inline-block; padding: 4px 14px; border-radius: 20px;
      font-size: 13px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.5px; margin-bottom: 12px;
      background-color: {badge_color}; color: #ffffff;
    }}
    .email-header h1 {{
      margin: 0; font-size: 24px; font-weight: 700;
    }}
    .email-body {{
      padding: 32px 28px; line-height: 1.6; font-size: 16px;
    }}
    .highlight-card {{
      background-color: #f8fafc; border-left: 4px solid #3b82f6;
      padding: 16px 20px; border-radius: 8px; margin: 20px 0;
    }}
    .alert-card {{
      background-color: #fef2f2; border-left: 4px solid #ef4444;
      padding: 16px 20px; border-radius: 8px; margin: 20px 0; color: #991b1b;
    }}
    .urgent-card {{
      background-color: #fff1f2; border: 2px dashed #e11d48;
      padding: 18px 20px; border-radius: 8px; margin: 20px 0;
    }}
    .info-row {{
      display: flex; justify-content: space-between; padding: 8px 0;
      border-bottom: 1px solid #edf2f7; font-size: 15px;
    }}
    .info-label {{
      font-weight: 600; color: #64748b;
    }}
    .info-val {{
      font-weight: 700; color: #1e293b;
    }}
    .email-footer {{
      background-color: #f8fafc; padding: 20px; text-align: center;
      font-size: 13px; color: #94a3b8; border-top: 1px solid #e2e8f0;
    }}
    .btn {{
      display: inline-block; background-color: #2563eb; color: #ffffff !important;
      text-decoration: none; padding: 12px 28px; border-radius: 8px;
      font-weight: 600; font-size: 15px; margin-top: 18px;
    }}
  </style>
</head>
<body>
  <div class="email-container">
    <div class="email-header">
      <div class="badge">{header_badge}</div>
      <h1>{header_title}</h1>
      <p style="margin: 6px 0 0 0; opacity: 0.9; font-size: 14px;">Elderly Care & Medication Management Platform</p>
    </div>
    <div class="email-body">
      {content_html}
    </div>
    <div class="email-footer">
      <p style="margin: 0 0 6px 0;">This is an automated safety alert from the Care Circle monitoring ecosystem.</p>
      <p style="margin: 0;">{footer_note}</p>
    </div>
  </div>
</body>
</html>"""

def notify_missed_dose(profile, med, schedule_time):
    """Sends immediate email reminder for missed dose to senior & care circle members."""
    subject = f"⚠️ Missed Medication Alert: {profile.full_name} has not confirmed {med.name}"
    
    content = f"""
      <div class="alert-card">
        <h3 style="margin-top:0; color:#b91c1c;">⚠️ Scheduled Dose Overdue</h3>
        <p>A scheduled dose for <strong>{profile.full_name}</strong> was due at <strong>{schedule_time}</strong> and has not yet been marked as taken.</p>
      </div>

      <div class="highlight-card">
        <table style="width: 100%; border-collapse: collapse;">
          <tr>
            <td style="padding: 6px 0; color: #64748b;"><strong>Medication:</strong></td>
            <td style="padding: 6px 0; text-align: right; color: #1e293b;"><strong>{med.name}</strong></td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;"><strong>Prescribed Dosage:</strong></td>
            <td style="padding: 6px 0; text-align: right; color: #1e293b;">{med.dosage} ({med.form})</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;"><strong>Appearance:</strong></td>
            <td style="padding: 6px 0; text-align: right; color: #1e293b;">{med.color_shape}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;"><strong>Instructions:</strong></td>
            <td style="padding: 6px 0; text-align: right; color: #1e293b;">{med.instructions or 'Take as prescribed'}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;"><strong>Purpose:</strong></td>
            <td style="padding: 6px 0; text-align: right; color: #1e293b;">{med.purpose or 'Health Maintenance'}</td>
          </tr>
        </table>
      </div>

      <p><strong>Recommended Action:</strong> Please contact <strong>{profile.full_name}</strong> or their on-duty caregiver to check in and verify if the medicine was taken or if assistance is needed.</p>
      
      <p style="text-align: center;">
        <a href="http://127.0.0.1:5000/dashboard" class="btn" style="background-color: #dc2626;">Open Care Circle Dashboard</a>
      </p>
    """
    html_body = get_base_email_template("Missed Medication Alert", "Overdue Dose Alert", "#ef4444", content, f"Patient: {profile.full_name}")

    # Dispatch to emergency contact and all care circle members
    recipients = get_care_circle_emails(profile)
    for rec in recipients:
        send_email(
            to_email=rec['email'],
            recipient_name=rec['name'],
            subject=subject,
            html_body=html_body,
            text_body=f"Missed dose alert for {profile.full_name}: {med.name} at {schedule_time}.",
            notification_type='missed_dose',
            profile_id=profile.id
        )

def notify_upcoming_dose(profile, med, schedule_time):
    """Sends proactive reminder 15-30 minutes before dose time."""
    subject = f"🔔 Medication Reminder: Upcoming dose of {med.name} at {schedule_time}"
    
    content = f"""
      <p>Hello! This is a proactive reminder that <strong>{profile.full_name}</strong> has a scheduled medication coming up shortly.</p>

      <div class="highlight-card">
        <h3 style="margin-top:0; color:#1d4ed8;">💊 {med.name} — {med.dosage}</h3>
        <p><strong>Scheduled Time:</strong> {schedule_time}</p>
        <p><strong>Pill Appearance:</strong> {med.color_shape}</p>
        <p><strong>Instructions:</strong> {med.instructions or 'Take with water'}</p>
      </div>

      <p>Taking medications consistently on schedule ensures optimal blood concentration and effective disease management.</p>
      <p style="text-align: center;">
        <a href="http://127.0.0.1:5000/dashboard" class="btn">Mark as Taken in App</a>
      </p>
    """
    html_body = get_base_email_template("Upcoming Medication Reminder", "Scheduled Dose", "#3b82f6", content, f"Patient: {profile.full_name}")

    recipients = get_care_circle_emails(profile)
    for rec in recipients:
        send_email(
            to_email=rec['email'],
            recipient_name=rec['name'],
            subject=subject,
            html_body=html_body,
            text_body=f"Upcoming medication for {profile.full_name}: {med.name} at {schedule_time}.",
            notification_type='upcoming_dose',
            profile_id=profile.id
        )

def notify_appointment(profile, appointment, time_window_label="Upcoming"):
    """Sends appointment alert (24 hours or 2 hours prior)."""
    subject = f"🗓️ Medical Appointment Reminder ({time_window_label}): Dr. {appointment.doctor_name} for {profile.full_name}"
    
    transport_note = f"🚗 <strong>Transportation:</strong> {appointment.transport_status}"
    if appointment.accompanying_person:
        transport_note += f"<br>👤 <strong>Accompanying Person:</strong> {appointment.accompanying_person}"
        
    prep_note = f"<p><strong>Preparation Instructions:</strong><br>{appointment.preparation_notes}</p>" if appointment.preparation_notes else ""

    content = f"""
      <div class="highlight-card" style="border-left-color: #8b5cf6;">
        <h3 style="margin-top:0; color:#6d28d9;">Doctor Appointment ({time_window_label})</h3>
        <table style="width: 100%; border-collapse: collapse;">
          <tr>
            <td style="padding: 6px 0; color: #64748b;"><strong>Doctor:</strong></td>
            <td style="padding: 6px 0; text-align: right; color: #1e293b;">Dr. {appointment.doctor_name} ({appointment.specialty})</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;"><strong>Clinic / Hospital:</strong></td>
            <td style="padding: 6px 0; text-align: right; color: #1e293b;">{appointment.clinic_name or 'Main Clinic'}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;"><strong>Address:</strong></td>
            <td style="padding: 6px 0; text-align: right; color: #1e293b;">{appointment.location_address or 'See clinic details'}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;"><strong>Date & Time:</strong></td>
            <td style="padding: 6px 0; text-align: right; color: #1e293b;"><strong>{appointment.appointment_date} at {appointment.appointment_time}</strong></td>
          </tr>
        </table>
      </div>

      <div style="background-color: #f1f5f9; padding: 14px 18px; border-radius: 8px; margin: 16px 0; font-size: 14px;">
        {transport_note}
      </div>

      {prep_note}

      <p style="text-align: center;">
        <a href="http://127.0.0.1:5000/appointments" class="btn" style="background-color: #7c3aed;">View Appointment Details</a>
      </p>
    """
    html_body = get_base_email_template("Medical Appointment Reminder", time_window_label, "#8b5cf6", content, f"Patient: {profile.full_name}")

    recipients = get_care_circle_emails(profile)
    for rec in recipients:
        send_email(
            to_email=rec['email'],
            recipient_name=rec['name'],
            subject=subject,
            html_body=html_body,
            text_body=f"Appointment reminder for {profile.full_name} with Dr. {appointment.doctor_name} on {appointment.appointment_date} at {appointment.appointment_time}.",
            notification_type='appointment',
            profile_id=profile.id
        )

def notify_low_refill(profile, med):
    """Sends pharmacy refill warning when stock <= refill threshold."""
    subject = f"📦 Prescription Refill Needed: {med.name} ({med.current_stock} doses remaining)"
    
    content = f"""
      <div class="alert-card" style="background-color: #fffbeb; border-left-color: #f59e0b; color: #92400e;">
        <h3 style="margin-top:0; color:#b45309;">⚠️ Prescription Low Stock Alert</h3>
        <p><strong>{profile.full_name}</strong> is running low on <strong>{med.name}</strong>.</p>
      </div>

      <div class="highlight-card">
        <p><strong>Medication:</strong> {med.name} ({med.dosage})</p>
        <p><strong>Remaining Pills:</strong> <span style="font-size: 18px; font-weight: bold; color: #dc2626;">{med.current_stock}</span></p>
        <p><strong>Refill Threshold:</strong> {med.refill_threshold} doses</p>
        <p><strong>Prescribing Doctor:</strong> {med.prescribing_doctor or 'Primary Physician'}</p>
      </div>

      <p>Please re-order this medication with the pharmacy to avoid gaps in therapy.</p>
    """
    html_body = get_base_email_template("Prescription Refill Warning", "Low Supply Alert", "#f59e0b", content, f"Patient: {profile.full_name}")

    recipients = get_care_circle_emails(profile)
    for rec in recipients:
        send_email(
            to_email=rec['email'],
            recipient_name=rec['name'],
            subject=subject,
            html_body=html_body,
            text_body=f"Refill needed for {profile.full_name}: {med.name} has only {med.current_stock} pills left.",
            notification_type='refill',
            profile_id=profile.id
        )

def notify_sos_alert(profile, emergency_note="Emergency Assistance Requested"):
    """Instant high-priority SOS emergency dispatch to all family and care circle members."""
    subject = f"🚨 URGENT SOS ALERT: {profile.full_name} Needs Immediate Assistance!"
    
    content = f"""
      <div class="urgent-card">
        <h2 style="margin-top:0; color: #e11d48; font-size: 24px;">🚨 EMERGENCY SOS TRIGGERED</h2>
        <p style="font-size: 18px; font-weight: bold; color: #9f1239;">
          {profile.full_name} has triggered an emergency help call from their device!
        </p>
        <p><strong>Timestamp:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        <p><strong>Note:</strong> {emergency_note}</p>
      </div>

      <div class="highlight-card" style="border-left-color: #e11d48;">
        <h3 style="margin-top:0; color: #be123c;">Critical Medical Profile</h3>
        <p><strong>Blood Group:</strong> {profile.blood_group or 'Unknown'}</p>
        <p><strong>Known Allergies:</strong> {profile.allergies or 'None reported'}</p>
        <p><strong>Chronic Conditions:</strong> {profile.chronic_conditions or 'None specified'}</p>
        <p><strong>Primary Emergency Contact:</strong> {profile.emergency_contact_name} ({profile.emergency_contact_phone})</p>
        <p><strong>Primary Physician:</strong> {profile.primary_physician or 'Not listed'}</p>
      </div>

      <p style="font-size: 16px; font-weight: bold; color: #b91c1c;">
        Action: Please call {profile.full_name} immediately at {profile.emergency_contact_phone or 'their phone number'}, or dispatch medical services if unreachable!
      </p>
    """
    html_body = get_base_email_template("EMERGENCY SOS ALERT", "CRITICAL ALERT", "#e11d48", content, f"Immediate Response Required")

    recipients = get_care_circle_emails(profile)
    for rec in recipients:
        send_email(
            to_email=rec['email'],
            recipient_name=rec['name'],
            subject=subject,
            html_body=html_body,
            text_body=f"URGENT SOS from {profile.full_name}! Please check on them immediately.",
            notification_type='sos',
            profile_id=profile.id
        )

def notify_ambulance_dispatch(profile, ambulance):
    """Urgent alert dispatched to all Care Circle members when an emergency ambulance is called."""
    subject = f"🚨 EMERGENCY AMBULANCE DISPATCHED: Help requested for {profile.full_name}"
    
    content = f"""
      <div class="urgent-card">
        <h2 style="margin-top:0; color: #dc2626; font-size: 24px;">🚨 AMBULANCE EN ROUTE</h2>
        <p style="font-size: 18px; font-weight: bold; color: #991b1b;">
          An emergency ambulance has been dispatched to {profile.full_name}'s residence!
        </p>
        <p><strong>Status:</strong> {ambulance.status.upper()}</p>
        <p><strong>Estimated Arrival Time:</strong> ~{ambulance.eta_minutes} minutes</p>
        <p><strong>Emergency Vehicle:</strong> {ambulance.vehicle_number}</p>
        <p><strong>Paramedic Contact:</strong> {ambulance.paramedic_name} ({ambulance.paramedic_phone})</p>
        <p><strong>Destination Hospital:</strong> {ambulance.hospital_destination}</p>
      </div>

      <div class="highlight-card" style="border-left-color: #dc2626;">
        <h3 style="margin-top:0; color: #991b1b;">Patient Critical Information</h3>
        <p><strong>Pickup Address:</strong> {ambulance.pickup_address}</p>
        <p><strong>Blood Group:</strong> {profile.blood_group}</p>
        <p><strong>Known Allergies:</strong> {profile.allergies}</p>
        <p><strong>Chronic Conditions:</strong> {profile.chronic_conditions}</p>
      </div>

      <p style="text-align: center;">
        <a href="http://127.0.0.1:5000/ambulance/{ambulance.id}" class="btn" style="background-color: #dc2626;">Open Live Ambulance Tracking</a>
      </p>
    """
    html_body = get_base_email_template("AMBULANCE EMERGENCY DISPATCH", "CRITICAL 911/108", "#dc2626", content, "Care Circle Urgent Action")

    recipients = get_care_circle_emails(profile)
    for rec in recipients:
        send_email(
            to_email=rec['email'],
            recipient_name=rec['name'],
            subject=subject,
            html_body=html_body,
            text_body=f"EMERGENCY: Ambulance dispatched for {profile.full_name} to {ambulance.pickup_address}.",
            notification_type='sos',
            profile_id=profile.id
        )

def notify_doctor_update(profile, update_type, details):
    """Notifies senior and family when their attending doctor updates prescriptions or next visit."""
    subject = f"🩺 Doctor Update for {profile.full_name}: {update_type}"
    
    content = f"""
      <div class="highlight-card" style="border-left-color: #2563eb;">
        <h3 style="margin-top:0; color: #1e40af;">🩺 Attending Physician Clinical Update</h3>
        <p>Your physician has updated your healthcare plan in the portal.</p>
        <p><strong>Update Category:</strong> {update_type}</p>
        <div style="background: #ffffff; padding: 14px; border-radius: 6px; border: 1px solid #e2e8f0; margin: 12px 0;">
          {details}
        </div>
      </div>

      <p style="text-align: center;">
        <a href="http://127.0.0.1:5000/dashboard" class="btn">View Updated Routine</a>
      </p>
    """
    html_body = get_base_email_template("Doctor Healthcare Update", "CLINICAL PLAN", "#2563eb", content, f"Patient: {profile.full_name}")

    recipients = get_care_circle_emails(profile)
    for rec in recipients:
        send_email(
            to_email=rec['email'],
            recipient_name=rec['name'],
            subject=subject,
            html_body=html_body,
            text_body=f"Doctor updated {update_type} for {profile.full_name}.",
            notification_type='general',
            profile_id=profile.id
        )

def get_care_circle_emails(profile):
    """Retrieves all active email recipients for a given elderly profile."""
    recipients = []
    
    # Emergency contact email if present
    if profile.emergency_contact_email:
        recipients.append({
            'name': profile.emergency_contact_name or 'Emergency Contact',
            'email': profile.emergency_contact_email
        })
        
    # Linked user account (if senior has their own email registered)
    if profile.creator and profile.creator.email:
        if not any(r['email'] == profile.creator.email for r in recipients):
            recipients.append({
                'name': profile.creator.name,
                'email': profile.creator.email
            })

    # Care circle members who have receive_email_alerts enabled
    for member in profile.care_circle:
        if member.receive_email_alerts and member.user and member.user.email:
            if not any(r['email'] == member.user.email for r in recipients):
                recipients.append({
                    'name': member.user.name,
                    'email': member.user.email
                })

    # Fallback default if no emails linked
    if not recipients:
        recipients.append({
            'name': 'Primary Caregiver',
            'email': 'caregiver.family@example.com'
        })

    return recipients
