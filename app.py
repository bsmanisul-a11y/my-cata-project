"""
Elderly Care & Medication Management Platform
Main Application Entry Point, Routing, Doctor Admin Portal & Emergency Ambulance Services
"""

import os
import re
import secrets
import urllib.parse
from datetime import datetime, date, timedelta, timezone
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, abort, send_from_directory
)
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from modules.models import (
    db, User, ElderlyProfile, CareCircleMember,
    Medication, MedicationSchedule, MedicationLog,
    Appointment, HealthVitalLog, CaregiverNote, NotificationLog,
    MedicalReport, AmbulanceRequest, MedicineDeliveryOrder
)
from modules.medication import (
    get_profile_medications, add_medication, record_dose_action,
    get_today_pillbox, calculate_adherence_stats, analyze_profile_drug_safety,
    ensure_daily_logs_for_profile
)
from modules.appointment import (
    get_upcoming_appointments, get_past_appointments,
    add_appointment, update_appointment, format_relative_appointment_time
)
from modules.email_notification import (
    send_email, notify_sos_alert, notify_missed_dose,
    notify_upcoming_dose, notify_appointment, notify_low_refill,
    notify_ambulance_dispatch, notify_doctor_update,
    is_smtp_configured
)
from modules.reminder import start_reminder_scheduler, run_reminder_check
from modules.seed import seed_demo_data

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
if not app.secret_key:
    app.secret_key = secrets.token_hex(32)
    app.logger.warning("SECRET_KEY is not set; generated an ephemeral key. Sessions will expire when the app restarts.")

# Database & Uploads configuration
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(BASE_DIR, 'elderly_care.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'private_uploads', 'reports')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
DELIVERY_HOSPITAL_NAME = 'St. Jude Hospital Pharmacy'
SIMULATED_DELIVERY_TOTAL = 250.0

db.init_app(app)

PUBLIC_ENDPOINTS = {'index', 'about', 'login', 'passcode_access', 'register', 'static'}

def has_authenticated_session():
    user_id = session.get('user_id')
    if user_id is not None:
        return db.session.get(User, user_id) is not None

    profile_id = session.get('active_profile_id')
    if profile_id and (session.get('pin_authenticated') or session.get('passcode_authenticated')):
        return db.session.get(ElderlyProfile, profile_id) is not None

    return False

@app.before_request
def require_authentication():
    """Block every non-public endpoint unless the user has an authenticated session."""
    if request.endpoint is None or request.endpoint in PUBLIC_ENDPOINTS:
        return
    if has_authenticated_session():
        return
    # API / AJAX callers get a JSON 401 instead of an HTML redirect
    if request.path.startswith('/api/') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': 'Authentication required. Please log in first.'}), 401
    # All other unauthenticated requests → login page
    flash("Please log in to access that page.", "warning")
    return redirect(url_for('login', next=request.url))

# Helper context processor for global active state in templates
@app.context_processor
def inject_global_data():
    active_profile = None
    all_user_profiles = []

    authenticated = has_authenticated_session()
    profile_id = session.get('active_profile_id') if authenticated else None
    if profile_id:
        active_profile = db.session.get(ElderlyProfile, profile_id)
        
    user_id = session.get('user_id') if authenticated else None
    current_user = None
    is_doctor = False

    if user_id:
        current_user = db.session.get(User, user_id)
        if current_user:
            is_doctor = current_user.role in ('doctor', 'admin')
            if is_doctor:
                # Doctors can see all elderly patients
                all_user_profiles = ElderlyProfile.query.all()
            else:
                linked_p_ids = [m.profile_id for m in current_user.circle_memberships]
                created_p_ids = [p.id for p in current_user.elderly_profiles_created]
                combined_ids = list(set(linked_p_ids + created_p_ids))
                if combined_ids:
                    all_user_profiles = ElderlyProfile.query.filter(ElderlyProfile.id.in_(combined_ids)).all()

    # Active ambulance request (Only show when actively en route: 'dispatched' or 'nearby')
    active_ambulance = None
    if active_profile:
        active_ambulance = (
            AmbulanceRequest.query.filter_by(profile_id=active_profile.id)
            .filter(AmbulanceRequest.status.in_(['dispatched', 'nearby']))
            .order_by(AmbulanceRequest.id.desc())
            .first()
        )

    now = datetime.now()
    return {
        'current_user': current_user,
        'active_profile': active_profile,
        'all_user_profiles': all_user_profiles,
        'active_role': session.get('user_role', 'elderly'),
        'senior_mode': session.get('senior_mode', True),
        'is_doctor': is_doctor or session.get('user_role') in ('doctor', 'admin'),
        'active_ambulance': active_ambulance,
        'now': now,
        'today_str': now.strftime('%Y-%m-%d'),
        'smtp_configured': is_smtp_configured()
    }

def get_current_profile_or_redirect():
    """Gets the active profile or selects the default first profile."""
    if not has_authenticated_session():
        return None

    profile_id = session.get('active_profile_id')
    if not profile_id:
        first = ElderlyProfile.query.first()
        if first:
            session['active_profile_id'] = first.id
            return first
        return None
    return db.session.get(ElderlyProfile, profile_id)

# ----------------- AUTHENTICATION & ACCESS ROUTES -----------------

@app.route('/')
def index():
    """Show the public homepage; authenticated users go to their dashboard."""
    if has_authenticated_session():
        return redirect(url_for('dashboard'))
    return render_template('index.html', profiles_count=0, sample_profile=None)

@app.route('/about')
def about():
    """Public informational page with no patient-specific data."""
    if has_authenticated_session():
        return redirect(url_for('dashboard'))
    return render_template('index.html', profiles_count=0, sample_profile=None)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Sign-in via Senior 4-digit PIN, Caregiver Email, or Doctor/Admin portal."""
    # Already logged in → go to dashboard
    if has_authenticated_session():
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        auth_type = request.form.get('auth_type', 'password')

        if auth_type == 'pin':
            pin = request.form.get('senior_pin', '').strip()
            profile = ElderlyProfile.query.filter_by(senior_pin=pin).first()
            if profile:
                session.clear()
                session['active_profile_id'] = profile.id
                session['user_role'] = 'elderly'
                session['user_name'] = profile.full_name
                session['senior_mode'] = True
                session['pin_authenticated'] = True
                flash(f"Welcome back, {profile.full_name}! 👋", "success")
                next_url = request.args.get('next') or request.form.get('next')
                return redirect(next_url if next_url and next_url.startswith('/') else url_for('dashboard'))
            else:
                flash("Invalid Senior PIN. Please check and try again.", "danger")
        else:
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            user = User.query.filter_by(email=email).first()

            if user and user.check_password(password):
                session.clear()
                session['user_id'] = user.id
                session['user_role'] = user.role
                session['user_name'] = user.name

                if user.role in ('doctor', 'admin'):
                    session['senior_mode'] = False
                    flash(f"Welcome to Doctor Admin Portal, {user.name}!", "success")
                    first_p = ElderlyProfile.query.first()
                    if first_p:
                        session['active_profile_id'] = first_p.id
                    return redirect(url_for('doctor_portal'))

                session['senior_mode'] = (user.role == 'elderly')

                # Find associated profile
                if user.role == 'elderly':
                    p = ElderlyProfile.query.filter_by(user_id=user.id).first()
                    if p:
                        session['active_profile_id'] = p.id
                elif user.circle_memberships:
                    session['active_profile_id'] = user.circle_memberships[0].profile_id
                elif user.elderly_profiles_created:
                    session['active_profile_id'] = user.elderly_profiles_created[0].id

                if not session.get('active_profile_id'):
                    if user.role in ('caregiver', 'family'):
                        flash("Sign in succeeded. Enter a family passcode to connect to a patient profile.", "info")
                        return redirect(url_for('passcode_access'))
                    session.clear()
                    flash("No patient profile is linked to this account yet.", "warning")
                    return redirect(url_for('login'))

                flash(f"Signed in successfully as {user.name} ({user.role.title()}).", "success")
                next_url = request.args.get('next') or request.form.get('next')
                return redirect(next_url if next_url and next_url.startswith('/') else url_for('dashboard'))
            else:
                flash("Invalid email or password.", "danger")

    return render_template('login.html')

@app.route('/passcode-access', methods=['GET', 'POST'])
def passcode_access():
    """Instant 6-digit Care Circle Passcode access for family and caretakers."""
    pending_caregiver = (
        session.get('user_id') is not None
        and session.get('user_role') in ('caregiver', 'family')
        and not session.get('active_profile_id')
    )
    if has_authenticated_session() and not pending_caregiver:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        passcode = request.form.get('passcode', '').strip().upper()
        relation = request.form.get('relation', 'Family Member').strip()
        caretaker_name = request.form.get('caretaker_name', 'Caretaker').strip()

        profile = ElderlyProfile.query.filter_by(family_passcode=passcode).first()
        if profile:
            if pending_caregiver:
                member = CareCircleMember.query.filter_by(
                    profile_id=profile.id,
                    user_id=session['user_id']
                ).first()
                if not member:
                    db.session.add(CareCircleMember(
                        profile_id=profile.id,
                        user_id=session['user_id'],
                        relation=relation,
                        can_manage_meds=True,
                        receive_email_alerts=True
                    ))
                    db.session.commit()
                session['active_profile_id'] = profile.id
                flash(f"Passcode verified. Connected to {profile.full_name}'s care profile.", "success")
                return redirect(url_for('dashboard'))

            session.clear()
            session['active_profile_id'] = profile.id
            session['user_role'] = 'caregiver'
            session['user_name'] = caretaker_name
            session['senior_mode'] = False
            session['passcode_authenticated'] = True

            flash(f"Secure Passcode verified! Connected to {profile.full_name}'s Care Profile.", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid Passcode. Please verify the 6-character code with the family.", "danger")

    return render_template('passcode_access.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Register a new elderly profile or caregiver account."""
    if request.method == 'POST':
        reg_type = request.form.get('reg_type', 'elderly')
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        phone = request.form.get('phone', '').strip()

        if reg_type not in ('elderly', 'caregiver'):
            flash("Choose a valid account type. Doctor accounts must be provisioned by an administrator.", "danger")
            return redirect(url_for('register'))

        if not name or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email) or len(password) < 6:
            flash("Enter your name, a valid email address, and a password of at least 6 characters.", "danger")
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash("An account with this email already exists. Please sign in.", "warning")
            return redirect(url_for('login'))

        caregiver_profile = None
        if reg_type == 'caregiver':
            passcode = request.form.get('join_passcode', '').strip().upper()
            if passcode:
                caregiver_profile = ElderlyProfile.query.filter_by(family_passcode=passcode).first()
            if passcode and not caregiver_profile:
                flash("The family passcode was not recognized. Check it and try again, or leave it blank to connect later.", "danger")
                return redirect(url_for('register'))

        user = User(name=name, email=email, role=reg_type, phone=phone)
        user.set_password(password)

        db.session.add(user)
        db.session.flush()

        if reg_type == 'elderly':
            age = request.form.get('age')
            blood_group = request.form.get('blood_group', 'Unknown')
            allergies = request.form.get('allergies', '')
            emergency_name = request.form.get('emergency_name', '')
            emergency_phone = request.form.get('emergency_phone', '')
            emergency_email = request.form.get('emergency_email', '')
            physician = request.form.get('physician', '')
            address = request.form.get('address', '742 Evergreen Terrace, Chicago, IL')

            profile = ElderlyProfile(
                user_id=user.id,
                full_name=name,
                age=int(age) if age and age.isdigit() else 70,
                blood_group=blood_group,
                allergies=allergies or "None reported",
                address=address,
                emergency_contact_name=emergency_name,
                emergency_contact_phone=emergency_phone,
                emergency_contact_email=emergency_email,
                primary_physician=physician,
                senior_pin=request.form.get('senior_pin', '1234')
            )
            db.session.add(profile)
            db.session.commit()

            session['user_id'] = user.id
            session['active_profile_id'] = profile.id
            session['user_role'] = 'elderly'
            session['user_name'] = user.name
            session['senior_mode'] = True

            flash(f"Profile created! Your Family Passcode is {profile.family_passcode}. Share it with your family!", "success")
            return redirect(url_for('dashboard'))

        else: # Caregiver
            if caregiver_profile:
                db.session.add(CareCircleMember(
                    profile_id=caregiver_profile.id,
                    user_id=user.id,
                    relation=request.form.get('relation', 'Family Member'),
                    can_manage_meds=True,
                    receive_email_alerts=True
                ))
            db.session.commit()
            if caregiver_profile:
                session['active_profile_id'] = caregiver_profile.id

            session['user_id'] = user.id
            session['user_role'] = reg_type
            session['user_name'] = user.name
            session['senior_mode'] = False

            if caregiver_profile:
                flash("Caregiver account created and linked successfully!", "success")
                return redirect(url_for('dashboard'))
            flash("Caregiver account created. Enter your family passcode to connect to a patient profile.", "info")
            return redirect(url_for('passcode_access'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been signed out safely.", "info")
    return redirect(url_for('index'))

@app.route('/switch-profile/<int:profile_id>')
def switch_profile(profile_id):
    """Allows caregivers and doctors to switch between managed elderly individuals."""
    profile = db.session.get(ElderlyProfile, profile_id)
    if not profile:
        abort(404)
    session['active_profile_id'] = profile.id
    flash(f"Switched active view to {profile.full_name}'s profile.", "info")
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/toggle-senior-mode')
def toggle_senior_mode():
    """Toggles between Senior High-Contrast Large Touch View and Caregiver Hub View."""
    session['senior_mode'] = not session.get('senior_mode', True)
    mode_name = "Senior Friendly Mode (Large Text & Voice)" if session['senior_mode'] else "Caregiver Detailed View"
    flash(f"Switched to {mode_name}.", "info")
    return redirect(request.referrer or url_for('dashboard'))

# ----------------- MAIN DASHBOARD -----------------

@app.route('/dashboard')
def dashboard():
    profile = get_current_profile_or_redirect()
    if not profile:
        flash("Please create or link an elderly profile first.", "info")
        return redirect(url_for('register'))

    # Daily pillbox
    pillbox = get_today_pillbox(profile.id)
    # Adherence metrics
    stats = calculate_adherence_stats(profile.id)
    # Upcoming appointments (next 2)
    upcoming_appts = get_upcoming_appointments(profile.id)[:2]
    # Recent caregiver notes
    recent_notes = CaregiverNote.query.filter_by(profile_id=profile.id).order_by(CaregiverNote.created_at.desc()).limit(3).all()
    # Safety warnings
    safety_alerts = analyze_profile_drug_safety(profile.id)
    # Latest vitals
    latest_vital = HealthVitalLog.query.filter_by(profile_id=profile.id).order_by(HealthVitalLog.id.desc()).first()
    # Recent reports
    recent_reports = MedicalReport.query.filter_by(profile_id=profile.id).order_by(MedicalReport.created_at.desc()).limit(2).all()

    return render_template(
        'dashboard.html',
        profile=profile,
        pillbox=pillbox,
        stats=stats,
        upcoming_appts=upcoming_appts,
        recent_notes=recent_notes,
        safety_alerts=safety_alerts,
        latest_vital=latest_vital,
        recent_reports=recent_reports
    )

# ----------------- DOCTOR & ADMIN PORTAL -----------------

@app.route('/admin')
@app.route('/doctor/portal', methods=['GET', 'POST'])
def doctor_portal():
    """
    Dedicated Doctor & Clinical Admin Portal:
    - View and select any patient under care.
    - Update/change medications (dosages, timing, additions, discontinuations).
    - Schedule and update the next doctor visit (so patient is immediately informed).
    - Upload diagnostic reports (with PDF/image upload or clinical findings).
    - Record in-clinic vitals that sync into patient's graphs.
    """
    # ── Role Guard: only doctors and admins may enter this portal ──────────────
    user_role = session.get('user_role', '')
    if user_role not in ('doctor', 'admin'):
        flash("Access denied. The Doctor & Admin Portal is only accessible to registered physicians.", "danger")
        return redirect(url_for('dashboard'))

    profile = get_current_profile_or_redirect()
    if not profile:
        flash("No patient profile found. Please log in first.", "warning")
        return redirect(url_for('login'))

    doctor_name = session.get('user_name', 'Attending Physician')

    if request.method == 'POST':
        action = request.form.get('action')

        # 1. DOCTOR UPDATES / ADDS MEDICATION
        if action == 'doctor_update_med':
            med_id = request.form.get('med_id')
            name = request.form.get('name')
            dosage = request.form.get('dosage')
            form = request.form.get('form', 'Pill')
            color_shape = request.form.get('color_shape', 'White Round')
            instructions = request.form.get('instructions', '')
            purpose = request.form.get('purpose', '')

            if med_id:
                # Update existing medication
                med = db.session.get(Medication, med_id)
                if med and med.profile_id == profile.id:
                    name = (name or med.name).strip()
                    dosage = (dosage or '').strip()
                    form = (request.form.get('form') or med.form).strip()
                    instructions = (instructions or '').strip()
                    if not name or not dosage or not form or not instructions:
                        flash("Medication name, form, dosage, and instructions are required.", "warning")
                        return redirect(url_for('doctor_portal'))

                    old_name = med.name
                    old_dosage = med.dosage
                    old_form = med.form
                    med.name = name
                    med.dosage = dosage
                    med.form = form
                    med.instructions = instructions
                    med.purpose = purpose
                    med.prescribing_doctor = doctor_name
                    db.session.commit()

                    detail_msg = (
                        f"Medication changed from <strong>{old_name} ({old_form})</strong> "
                        f"to <strong>{med.name} ({form}), {dosage}</strong>. "
                        f"Previous dosage: {old_dosage}. Instructions: {instructions}"
                    )
                    notify_doctor_update(profile, "Medication Prescription Updated", detail_msg)

                    note = CaregiverNote(
                        profile_id=profile.id,
                        author_name=doctor_name,
                        category="Doctor Update",
                        content=(
                            f"Prescription changed from {old_name} ({old_form}, {old_dosage}) "
                            f"to {med.name} ({form}, {dosage}). Instructions: {instructions}"
                        )
                    )
                    db.session.add(note)
                    db.session.commit()
                    flash(f"Updated prescription for {med.name} successfully! Patient and family notified.", "success")
            else:
                # Add new medicine
                slots = request.form.getlist('time_slots') or ['Morning']
                schedule_times = []
                for s in slots:
                    time_val = request.form.get(f'time_{s.lower()}', '08:00')
                    schedule_times.append({'time_slot': s, 'time': time_val, 'days': 'Daily'})

                add_medication(
                    profile_id=profile.id,
                    name=name,
                    dosage=dosage,
                    form=form,
                    color_shape=color_shape,
                    instructions=instructions,
                    purpose=purpose,
                    prescribing_doctor=doctor_name,
                    stock=30,
                    refill_threshold=7,
                    schedule_times=schedule_times
                )
                detail_msg = f"New medication prescribed: <strong>{name} {dosage}</strong> ({form}). Instructions: {instructions}"
                notify_doctor_update(profile, "New Prescription Prescribed", detail_msg)
                flash(f"Prescribed new medication '{name}' for {profile.full_name}!", "success")

            return redirect(url_for('doctor_portal'))

        # 2. DOCTOR SCHEDULES NEXT CLINIC VISIT
        elif action == 'doctor_schedule_visit':
            appt_date = request.form.get('appointment_date')
            appt_time = request.form.get('appointment_time')
            specialty = request.form.get('specialty', 'Cardiology & Internal Medicine')
            clinic = request.form.get('clinic_name', 'St. Jude Heart & Vascular Pavilion')
            address = request.form.get('location_address', '450 Medical Center Blvd, Chicago, IL')
            prep_notes = request.form.get('preparation_notes', '')

            appt = add_appointment(
                profile_id=profile.id,
                doctor_name=doctor_name.replace('Dr. ', '').strip(),
                specialty=specialty,
                clinic_name=clinic,
                location_address=address,
                appointment_date=appt_date,
                appointment_time=appt_time,
                transport_needed=True,
                transport_status='Arranged by Family',
                accompanying_person='Family Member',
                preparation_notes=prep_notes
            )

            detail_msg = f"Next appointment scheduled for <strong>{appt_date} at {appt_time}</strong> at {clinic}.<br><strong>Preparation:</strong> {prep_notes}"
            notify_doctor_update(profile, "Next Doctor Visit Scheduled", detail_msg)

            note = CaregiverNote(
                profile_id=profile.id,
                author_name=doctor_name,
                category="Doctor Update",
                content=f"Next clinical consultation scheduled for {appt_date} at {appt_time}. Preparation: {prep_notes}"
            )
            db.session.add(note)
            db.session.commit()
            flash(f"Next doctor visit scheduled for {appt_date}! Patient & family notified automatically.", "success")
            return redirect(url_for('doctor_portal'))

        # 3. DOCTOR UPLOADS MEDICAL REPORT
        elif action == 'upload_report':
            title = request.form.get('title')
            report_type = request.form.get('report_type', 'Lab Test')
            summary = request.form.get('summary_findings', '')
            recommendations = request.form.get('doctor_recommendations', '')

            file = request.files.get('report_file')
            saved_filename = None
            if file and file.filename:
                clean_name = secure_filename(f"{profile.id}_{int(datetime.now().timestamp())}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], clean_name))
                saved_filename = clean_name

            rep = MedicalReport(
                profile_id=profile.id,
                doctor_name=doctor_name,
                title=title,
                report_type=report_type,
                file_name=saved_filename,
                file_path=os.path.join('uploads', 'reports', saved_filename) if saved_filename else None,
                summary_findings=summary,
                doctor_recommendations=recommendations,
                report_date=datetime.now().strftime('%Y-%m-%d')
            )
            db.session.add(rep)
            db.session.commit()

            detail_msg = f"New report uploaded: <strong>{title}</strong> ({report_type}).<br>Summary: {summary}<br>Recommendations: {recommendations}"
            notify_doctor_update(profile, f"New Medical Report Available ({title})", detail_msg)
            flash(f"Medical report '{title}' uploaded successfully! Available in patient's profile.", "success")
            return redirect(url_for('doctor_portal'))

        # 4. DOCTOR LOGS CLINICAL VITALS
        elif action == 'doctor_log_vitals':
            sbp = request.form.get('systolic_bp')
            dbp = request.form.get('diastolic_bp')
            glu = request.form.get('blood_glucose')
            hr = request.form.get('heart_rate')
            notes = request.form.get('notes', '')

            v = HealthVitalLog(
                profile_id=profile.id,
                systolic_bp=int(sbp) if sbp and sbp.isdigit() else None,
                diastolic_bp=int(dbp) if dbp and dbp.isdigit() else None,
                blood_glucose=float(glu) if glu else None,
                heart_rate=int(hr) if hr and hr.isdigit() else None,
                mood='good',
                notes=f"[Doctor Examined] {notes}",
                logged_by_doctor=True,
                doctor_name=doctor_name
            )
            v.check_abnormality()
            db.session.add(v)
            db.session.commit()
            flash("Clinical examination vitals recorded successfully into patient graph!", "success")
            return redirect(url_for('doctor_portal'))

    # Load data for doctor portal
    meds = get_profile_medications(profile.id)
    upcoming_appts = get_upcoming_appointments(profile.id)
    reports = MedicalReport.query.filter_by(profile_id=profile.id).order_by(MedicalReport.created_at.desc()).all()
    recent_vitals = HealthVitalLog.query.filter_by(profile_id=profile.id).order_by(HealthVitalLog.id.desc()).limit(10).all()
    all_patients = ElderlyProfile.query.all()
    ambulance_calls = AmbulanceRequest.query.filter_by(profile_id=profile.id).order_by(AmbulanceRequest.created_at.desc()).all()

    return render_template(
        'doctor_portal.html',
        profile=profile,
        meds=meds,
        upcoming_appts=upcoming_appts,
        reports=reports,
        recent_vitals=recent_vitals,
        all_patients=all_patients,
        ambulance_calls=ambulance_calls
    )

# ----------------- EMERGENCY AMBULANCE TRACKING SERVICE -----------------

@app.route('/ambulance')
def ambulance_service():
    """Ambulance booking overview & live tracking hub."""
    profile = get_current_profile_or_redirect()
    if not profile:
        flash("Please log in to access the ambulance service.", "warning")
        return redirect(url_for('login'))

    latest_req = AmbulanceRequest.query.filter_by(profile_id=profile.id).order_by(AmbulanceRequest.id.desc()).first()
    return render_template('ambulance.html', profile=profile, ambulance=latest_req)

@app.route('/ambulance/request', methods=['POST'])
def request_ambulance():
    """Dispatches emergency ambulance with real-time tracking."""
    profile = get_current_profile_or_redirect()
    if not profile:
        return jsonify({'error': 'No profile'}), 400

    pickup = request.form.get('pickup_address', profile.address or '742 Evergreen Terrace, Chicago, IL')
    hospital = request.form.get('hospital_destination', 'St. Jude Emergency Medical Center')
    notes = request.form.get('notes', 'Emergency medical assistance requested.')

    ambulance = AmbulanceRequest(
        profile_id=profile.id,
        status='dispatched',
        pickup_address=pickup,
        hospital_destination=hospital,
        paramedic_name='Paramedic Alex Martinez (Unit 402)',
        paramedic_phone='+1 (555) 911-0422',
        vehicle_number='AMB-UNIT-402',
        eta_minutes=11,
        notes=notes
    )
    db.session.add(ambulance)
    db.session.commit()

    # Dispatch urgent email & SMS simulation to all Care Circle members
    notify_ambulance_dispatch(profile, ambulance)

    flash("🚨 EMERGENCY AMBULANCE DISPATCHED! Paramedics are en route. Live tracking started below.", "danger")
    return redirect(url_for('ambulance_track', req_id=ambulance.id))

@app.route('/ambulance/<int:req_id>')
def ambulance_track(req_id):
    """Live interactive tracking screen for an ambulance request."""
    if not has_authenticated_session():
        flash("Please log in to view ambulance tracking.", "warning")
        return redirect(url_for('login'))
    ambulance = db.session.get(AmbulanceRequest, req_id)
    if not ambulance:
        abort(404)
    profile = ambulance.profile
    return render_template('ambulance.html', profile=profile, ambulance=ambulance)

@app.route('/ambulance/<int:req_id>/advance', methods=['POST'])
def advance_ambulance_status(req_id):
    """
    Simulates progression of the ambulance through the 3 required states:
    1. 'dispatched' -> 2. 'nearby' (ETA 2 mins) -> 3. 'arrived' (at doorstep)
    """
    ambulance = db.session.get(AmbulanceRequest, req_id)
    if not ambulance:
        return jsonify({'error': 'Not found'}), 404

    target_status = request.form.get('status')
    if target_status:
        ambulance.status = target_status
    else:
        if ambulance.status == 'dispatched':
            ambulance.status = 'nearby'
            ambulance.eta_minutes = 2
        elif ambulance.status == 'nearby':
            ambulance.status = 'arrived'
            ambulance.eta_minutes = 0
        elif ambulance.status == 'arrived':
            ambulance.status = 'completed'

    ambulance.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'status': ambulance.status, 'eta': ambulance.eta_minutes})

    flash(f"Ambulance status advanced to: {ambulance.status.upper()}!", "info")
    return redirect(url_for('ambulance_track', req_id=ambulance.id))

@app.route('/ambulance/<int:req_id>/dismiss', methods=['POST'])
def dismiss_ambulance(req_id):
    """Allows user to close / complete an ambulance call so the banner disappears."""
    ambulance = db.session.get(AmbulanceRequest, req_id)
    if ambulance:
        ambulance.status = 'completed'
        ambulance.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        flash("Ambulance request completed and dismissed.", "info")
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/api/ambulance/<int:req_id>/status')
def api_ambulance_status(req_id):
    """JSON status polling for the interactive map and ETA timer."""
    ambulance = db.session.get(AmbulanceRequest, req_id)
    if not ambulance:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({
        'id': ambulance.id,
        'status': ambulance.status,
        'eta_minutes': ambulance.eta_minutes,
        'paramedic_name': ambulance.paramedic_name,
        'paramedic_phone': ambulance.paramedic_phone,
        'vehicle_number': ambulance.vehicle_number,
        'pickup_address': ambulance.pickup_address,
        'hospital_destination': ambulance.hospital_destination
    })

# ----------------- MEDICAL REPORTS ACCESS FOR PATIENTS -----------------

@app.route('/reports')
def patient_reports():
    """Allows patient and family to view and download all doctor-uploaded reports."""
    profile = get_current_profile_or_redirect()
    if not profile:
        flash("Please log in to view medical reports.", "warning")
        return redirect(url_for('login'))

    reports = MedicalReport.query.filter_by(profile_id=profile.id).order_by(MedicalReport.created_at.desc()).all()
    return render_template('reports.html', profile=profile, reports=reports)

@app.route('/reports/download/<filename>')
def download_report(filename):
    """Securely downloads uploaded medical report files (login required)."""
    if not has_authenticated_session():
        flash("Please log in to download medical reports.", "warning")
        return redirect(url_for('login'))
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

# ----------------- MEDICATION ROUTES -----------------

@app.route('/medications', methods=['GET', 'POST'])
def medications():
    profile = get_current_profile_or_redirect()
    if not profile:
        flash("Please log in to manage medications.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add_medication':
            name = request.form.get('name')
            dosage = request.form.get('dosage')
            form = request.form.get('form', 'Pill')
            color_shape = request.form.get('color_shape', 'White Round')
            instructions = request.form.get('instructions', '')
            purpose = request.form.get('purpose', '')
            doctor = request.form.get('prescribing_doctor', '')
            stock = request.form.get('stock', 30)
            threshold = request.form.get('refill_threshold', 7)

            slots = request.form.getlist('time_slots')
            schedule_times = []
            slot_defaults = {'Morning': '08:00', 'Afternoon': '13:00', 'Evening': '19:00', 'Bedtime': '21:30'}
            for slot in slots:
                time_val = request.form.get(f'time_{slot.lower()}', slot_defaults.get(slot, '08:00'))
                schedule_times.append({'time_slot': slot, 'time': time_val, 'days': 'Daily'})

            if not schedule_times:
                schedule_times = [{'time_slot': 'Morning', 'time': '08:00', 'days': 'Daily'}]

            add_medication(
                profile_id=profile.id,
                name=name,
                dosage=dosage,
                form=form,
                color_shape=color_shape,
                instructions=instructions,
                purpose=purpose,
                prescribing_doctor=doctor,
                stock=stock,
                refill_threshold=threshold,
                schedule_times=schedule_times
            )
            flash(f"Medication '{name}' added successfully to the schedule!", "success")
            return redirect(url_for('medications'))

        # REFILL STOCK: SUPPORTS TYPING NUMBER OR PRESET BUTTONS
        elif action == 'refill_stock':
            med_id = request.form.get('med_id')
            refill_amount = request.form.get('refill_amount', '30')
            try:
                refill_val = int(refill_amount)
            except ValueError:
                refill_val = 30

            med = db.session.get(Medication, med_id)
            if med and med.profile_id == profile.id:
                med.current_stock += refill_val
                db.session.commit()
                flash(f"Added {refill_val} pills to {med.name} supply! (Total in stock: {med.current_stock})", "success")
            return redirect(url_for('medications'))

    meds = get_profile_medications(profile.id)
    pillbox = get_today_pillbox(profile.id)
    stats = calculate_adherence_stats(profile.id)
    safety_alerts = analyze_profile_drug_safety(profile.id)
    delivery_orders = (
        MedicineDeliveryOrder.query.filter_by(profile_id=profile.id)
        .order_by(MedicineDeliveryOrder.created_at.desc())
        .limit(5)
        .all()
    )

    recent_logs = (
        MedicationLog.query.filter_by(profile_id=profile.id)
        .order_by(MedicationLog.scheduled_date.desc(), MedicationLog.scheduled_time.desc())
        .limit(20)
        .all()
    )

    return render_template(
        'medications.html',
        profile=profile,
        meds=meds,
        pillbox=pillbox,
        stats=stats,
        safety_alerts=safety_alerts,
        delivery_orders=delivery_orders,
        recent_logs=recent_logs
    )

def get_profile_delivery_order(order_id, profile_id):
    order = MedicineDeliveryOrder.query.filter_by(
        id=order_id,
        profile_id=profile_id
    ).first()
    if not order:
        abort(404)
    return order

@app.route('/medicine-delivery/request/<int:med_id>', methods=['POST'])
def request_medicine_delivery(med_id):
    profile = get_current_profile_or_redirect()
    if not profile:
        flash("Please log in to request a medicine delivery.", "warning")
        return redirect(url_for('login'))

    med = Medication.query.filter_by(
        id=med_id,
        profile_id=profile.id,
        is_active=True
    ).first_or_404()
    if med.current_stock > med.refill_threshold:
        flash(f"{med.name} supply is not low enough to request delivery yet.", "info")
        return redirect(url_for('medications'))

    try:
        quantity = int(request.form.get('quantity', '30'))
    except ValueError:
        quantity = 0
    if not 1 <= quantity <= 500:
        flash("Choose a delivery quantity between 1 and 500.", "danger")
        return redirect(url_for('medications'))

    order = MedicineDeliveryOrder(
        profile_id=profile.id,
        medication_id=med.id,
        medication_name=med.name,
        dosage=med.dosage,
        quantity=quantity,
        delivery_address=profile.address or '',
        contact_phone=profile.emergency_contact_phone,
        hospital_name=DELIVERY_HOSPITAL_NAME,
        status='on_the_way',
        eta_minutes=18,
        total_amount=SIMULATED_DELIVERY_TOTAL
    )
    db.session.add(order)
    db.session.commit()
    flash(f"Delivery request for {med.name} created. Please check the medicine before payment.", "success")
    return redirect(url_for('medicine_delivery', order_id=order.id))

@app.route('/medicine-delivery/<int:order_id>')
def medicine_delivery(order_id):
    profile = get_current_profile_or_redirect()
    if not profile:
        flash("Please log in to view medicine delivery.", "warning")
        return redirect(url_for('login'))

    order = get_profile_delivery_order(order_id, profile.id)
    upi_processing = (
        session.pop('upi_processing_order_id', None) == order.id
        and order.payment_method == 'UPI'
    )
    return render_template(
        'medicine_delivery.html',
        profile=profile,
        order=order,
        upi_processing=upi_processing
    )

@app.route('/medicine-delivery/<int:order_id>/check', methods=['POST'])
def check_medicine_delivery(order_id):
    profile = get_current_profile_or_redirect()
    if not profile:
        flash("Please log in to continue.", "warning")
        return redirect(url_for('login'))

    order = get_profile_delivery_order(order_id, profile.id)
    if order.status != 'arrived':
        flash("This order is no longer waiting for a medicine check.", "info")
    elif request.form.get('medicine_checked') != 'yes':
        flash("Please confirm that you checked the medicine before continuing to payment.", "warning")
    else:
        order.is_checked = True
        order.status = 'checked'
        db.session.commit()
        flash("Medicine checked. Choose a payment method to continue.", "success")
    return redirect(url_for('medicine_delivery', order_id=order.id))

@app.route('/medicine-delivery/<int:order_id>/pay', methods=['POST'])
def pay_medicine_delivery(order_id):
    profile = get_current_profile_or_redirect()
    if not profile:
        flash("Please log in to continue.", "warning")
        return redirect(url_for('login'))

    order = get_profile_delivery_order(order_id, profile.id)
    if not order.is_checked or order.status != 'checked':
        flash("Receive and check the medicine before choosing a payment method.", "warning")
        return redirect(url_for('medicine_delivery', order_id=order.id))

    payment_method = request.form.get('payment_method')
    if payment_method == 'cod':
        order.payment_method = 'COD'
        order.status = 'delivered'
        order.delivered_at = datetime.now(timezone.utc)
        med = db.session.get(Medication, order.medication_id) if order.medication_id else None
        if med and med.profile_id == profile.id:
            med.current_stock += order.quantity
        db.session.commit()
        flash("Thank you, your health is our wealth.", "success")
        return redirect(url_for('medicine_delivery', order_id=order.id))

    if payment_method == 'upi':
        upi_id = request.form.get('upi_id', '').strip()
        if not re.fullmatch(r'[A-Za-z0-9._-]{2,256}@[A-Za-z][A-Za-z0-9]{1,63}', upi_id):
            flash("Enter a valid UPI ID, such as name@bank.", "danger")
            return redirect(url_for('medicine_delivery', order_id=order.id))

        order.payment_method = 'UPI'
        order.upi_id = None
        order.status = 'delivered'
        order.delivered_at = datetime.now(timezone.utc)
        med = db.session.get(Medication, order.medication_id) if order.medication_id else None
        if med and med.profile_id == profile.id:
            med.current_stock += order.quantity
        db.session.commit()
        session['upi_processing_order_id'] = order.id
        return redirect(url_for('medicine_delivery', order_id=order.id))

    flash("Choose Cash on Delivery or UPI.", "warning")
    return redirect(url_for('medicine_delivery', order_id=order.id))

@app.route('/medicine-delivery/<int:order_id>/arrived', methods=['POST'])
def mark_medicine_delivery_arrived(order_id):
    profile = get_current_profile_or_redirect()
    if not profile:
        return jsonify({'error': 'Authentication required.'}), 401

    order = get_profile_delivery_order(order_id, profile.id)
    if order.status == 'arrived':
        return jsonify({'success': True, 'status': order.status, 'already_arrived': True})
    if order.status != 'on_the_way':
        return jsonify({'error': 'This delivery is not out for delivery.'}), 409

    order.status = 'arrived'
    order.eta_minutes = 0
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'status': order.status
        })

    flash("Your medicine has arrived. Check the medicine before payment.", "success")
    return redirect(url_for('medicine_delivery', order_id=order.id))

@app.route('/api/medicine-delivery/<int:order_id>/status')
def medicine_delivery_status(order_id):
    profile = get_current_profile_or_redirect()
    if not profile:
        return jsonify({'error': 'Authentication required.'}), 401

    order = get_profile_delivery_order(order_id, profile.id)
    return jsonify({
        'id': order.id,
        'status': order.status,
        'eta_minutes': order.eta_minutes,
        'hospital_name': order.hospital_name,
        'vehicle_number': order.vehicle_number,
        'rider_name': order.rider_name
    })

@app.route('/medications/delete/<int:med_id>', methods=['POST'])
def delete_medication(med_id):
    profile = get_current_profile_or_redirect()
    med = db.session.get(Medication, med_id)
    if med and med.profile_id == profile.id:
        med_name = med.name
        db.session.delete(med)
        db.session.commit()
        flash(f"Medication '{med_name}' has been discontinued/removed.", "info")
    return redirect(url_for('medications'))

@app.route('/dose-action/<int:log_id>/<action>', methods=['POST'])
def log_dose(log_id, action):
    """Records dose status: 'taken', 'skipped', 'snoozed', 'pending'."""
    actor = session.get('user_name', 'Elderly User')
    notes = request.form.get('notes', '')
    log, msg = record_dose_action(log_id, action, actor_name=actor, notes=notes)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'action': action, 'status': log.status if log else action})

    if action == 'taken':
        flash(f"Dose marked as TAKEN! Great job! 🎉", "success")
    elif action == 'skipped':
        flash("Dose logged as skipped.", "warning")
    elif action == 'snoozed':
        flash("Dose snoozed for 30 minutes. We'll remind you again soon! ⏰", "info")
    else:
        flash(f"Dose updated to {action}.", "info")

    return redirect(request.referrer or url_for('dashboard'))

# ----------------- APPOINTMENTS & UBER RIDE INTEGRATION -----------------

@app.route('/appointments', methods=['GET', 'POST'])
def appointments():
    profile = get_current_profile_or_redirect()
    if not profile:
        flash("Please log in to view appointments.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add_appointment':
            doctor = request.form.get('doctor_name')
            specialty = request.form.get('specialty', 'General Physician')
            clinic = request.form.get('clinic_name', '')
            address = request.form.get('location_address', '')
            appt_date = request.form.get('appointment_date')
            appt_time = request.form.get('appointment_time')
            transport_needed = bool(request.form.get('transport_needed'))
            transport_status = request.form.get('transport_status', 'Not Needed')
            accompanying = request.form.get('accompanying_person', '')
            prep = request.form.get('preparation_notes', '')

            add_appointment(
                profile_id=profile.id,
                doctor_name=doctor,
                specialty=specialty,
                clinic_name=clinic,
                location_address=address,
                appointment_date=appt_date,
                appointment_time=appt_time,
                transport_needed=transport_needed,
                transport_status=transport_status,
                accompanying_person=accompanying,
                preparation_notes=prep
            )
            flash(f"Appointment with Dr. {doctor} scheduled successfully!", "success")
            return redirect(url_for('appointments'))

        elif action == 'update_status':
            appt_id = request.form.get('appt_id')
            new_status = request.form.get('status')
            summary = request.form.get('doctor_summary_notes', '')
            update_appointment(appt_id, status=new_status, doctor_summary_notes=summary)
            flash(f"Appointment updated to '{new_status}'.", "info")
            return redirect(url_for('appointments'))

    upcoming = get_upcoming_appointments(profile.id)
    past = get_past_appointments(profile.id)

    # Attach relative friendly countdowns and pre-computed Uber hospital ride links
    for a in upcoming:
        a.relative_time = format_relative_appointment_time(a.appointment_date, a.appointment_time)
        destination_query = a.location_address or a.clinic_name or "Hospital"
        # Deep link / redirect to Uber website with formatted dropoff
        a.uber_ride_url = f"https://www.uber.com/in/en/"

    return render_template(
        'appointments.html',
        profile=profile,
        upcoming=upcoming,
        past=past
    )

@app.route('/appointments/delete/<int:appt_id>', methods=['POST'])
def delete_appointment(appt_id):
    profile = get_current_profile_or_redirect()
    appt = db.session.get(Appointment, appt_id)
    if appt and appt.profile_id == profile.id:
        db.session.delete(appt)
        db.session.commit()
        flash("Appointment removed.", "info")
    return redirect(url_for('appointments'))

# ----------------- CAREGIVER HUB & COLLABORATION -----------------

@app.route('/caregiver', methods=['GET', 'POST'])
def caregiver():
    profile = get_current_profile_or_redirect()
    if not profile:
        flash("Please log in to access the Care Circle.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add_note':
            category = request.form.get('category', 'General')
            content = request.form.get('content', '').strip()
            author = session.get('user_name', 'Caregiver')

            if content:
                note = CaregiverNote(
                    profile_id=profile.id,
                    author_name=author,
                    category=category,
                    content=content
                )
                db.session.add(note)
                db.session.commit()
                flash("Caregiver note posted to the Care Circle board!", "success")
            return redirect(url_for('caregiver'))

        elif action == 'add_member':
            member_email = request.form.get('email', '').strip().lower()
            member_name = request.form.get('name', 'Family Member').strip()
            relation = request.form.get('relation', 'Relative')

            user = User.query.filter_by(email=member_email).first()
            if not user:
                user = User(
                    name=member_name,
                    email=member_email,
                    role='family',
                    password_hash=generate_password_hash('care123')
                )
                db.session.add(user)
                db.session.flush()

            existing = CareCircleMember.query.filter_by(profile_id=profile.id, user_id=user.id).first()
            if not existing:
                cm = CareCircleMember(
                    profile_id=profile.id,
                    user_id=user.id,
                    relation=relation,
                    can_manage_meds=True,
                    receive_email_alerts=True
                )
                db.session.add(cm)
                db.session.commit()
                flash(f"{member_name} ({relation}) added to {profile.full_name}'s Care Circle!", "success")
            else:
                flash(f"{member_name} is already a member of this Care Circle.", "info")
            return redirect(url_for('caregiver'))

        elif action == 'send_test_email':
            test_email = request.form.get('test_email', '').strip()
            test_type = request.form.get('test_type', 'missed_dose')
            if test_email:
                med = Medication.query.filter_by(profile_id=profile.id).first()
                if test_type == 'missed_dose' and med:
                    notify_missed_dose(profile, med, "08:00 AM")
                elif test_type == 'upcoming_dose' and med:
                    notify_upcoming_dose(profile, med, "12:00 PM")
                elif test_type == 'appointment':
                    appt = Appointment.query.filter_by(profile_id=profile.id).first()
                    if appt:
                        notify_appointment(profile, appt, "Tomorrow at 10:30 AM")
                elif test_type == 'sos':
                    notify_sos_alert(profile, "Care Circle manual test alert")
                else:
                    if med:
                        notify_low_refill(profile, med)
                flash(f"Test proactive email ({test_type}) triggered! Check your inbox or the live notification log below.", "success")
            return redirect(url_for('caregiver'))

    members = CareCircleMember.query.filter_by(profile_id=profile.id).all()
    notes = CaregiverNote.query.filter_by(profile_id=profile.id).order_by(CaregiverNote.created_at.desc()).all()
    notifications = NotificationLog.query.filter_by(profile_id=profile.id).order_by(NotificationLog.sent_at.desc()).limit(25).all()
    stats = calculate_adherence_stats(profile.id)

    return render_template(
        'caregiver.html',
        profile=profile,
        members=members,
        notes=notes,
        notifications=notifications,
        stats=stats
    )

# ----------------- VITALS & HEALTH ROUTINES (WITH ABNORMAL ALERTS & GRAPHS) -----------------

@app.route('/vitals', methods=['GET', 'POST'])
def vitals():
    profile = get_current_profile_or_redirect()
    if not profile:
        flash("Please log in to view health vitals.", "warning")
        return redirect(url_for('login'))

    abnormal_logged = False

    if request.method == 'POST':
        sbp = request.form.get('systolic_bp')
        dbp = request.form.get('diastolic_bp')
        glucose = request.form.get('blood_glucose')
        hr = request.form.get('heart_rate')
        water = request.form.get('water_glasses', 0)
        mood = request.form.get('mood', 'good')
        notes = request.form.get('notes', '')

        v = HealthVitalLog(
            profile_id=profile.id,
            systolic_bp=int(sbp) if sbp and sbp.isdigit() else None,
            diastolic_bp=int(dbp) if dbp and dbp.isdigit() else None,
            blood_glucose=float(glucose) if glucose else None,
            heart_rate=int(hr) if hr and hr.isdigit() else None,
            water_glasses=int(water) if water else 0,
            mood=mood,
            notes=notes.strip()
        )
        abnormal_logged = v.check_abnormality()
        db.session.add(v)
        db.session.commit()

        if abnormal_logged:
            flash("⚠️ Notice: One or more recorded vitals are above clinical thresholds. Please rest and consult your physician if symptoms persist.", "danger")
        else:
            flash("Daily health check-in recorded! Vitals are within normal ranges.", "success")
        return redirect(url_for('vitals'))

    # Load history (chronological for graphs)
    vitals_history = (
        HealthVitalLog.query.filter_by(profile_id=profile.id)
        .order_by(HealthVitalLog.log_date.asc(), HealthVitalLog.id.asc())
        .limit(20)
        .all()
    )

    # Format chart data for Blood Pressure, Blood Glucose, and Heart Rate
    chart_dates = [f"{v.log_date[-5:]} {v.log_time}" for v in vitals_history]
    chart_sbp = [v.systolic_bp or 0 for v in vitals_history]
    chart_dbp = [v.diastolic_bp or 0 for v in vitals_history]
    chart_glucose = [v.blood_glucose or 0 for v in vitals_history]
    chart_hr = [v.heart_rate or 0 for v in vitals_history]

    # Check latest vital for abnormal status
    latest_vital = vitals_history[-1] if vitals_history else None
    has_abnormal = latest_vital.is_abnormal if latest_vital else False

    return render_template(
        'vitals.html',
        profile=profile,
        vitals_history=list(reversed(vitals_history)),
        chart_dates=chart_dates,
        chart_sbp=chart_sbp,
        chart_dbp=chart_dbp,
        chart_glucose=chart_glucose,
        chart_hr=chart_hr,
        has_abnormal=has_abnormal,
        latest_vital=latest_vital
    )

# ----------------- DOCTOR'S PRINTABLE REPORT -----------------

@app.route('/doctor-report')
def doctor_report():
    profile = get_current_profile_or_redirect()
    if not profile:
        flash("Please log in to view the doctor report.", "warning")
        return redirect(url_for('login'))

    meds = get_profile_medications(profile.id)
    stats = calculate_adherence_stats(profile.id)
    safety_alerts = analyze_profile_drug_safety(profile.id)
    recent_vitals = (
        HealthVitalLog.query.filter_by(profile_id=profile.id)
        .order_by(HealthVitalLog.log_date.desc())
        .limit(7)
        .all()
    )
    upcoming_appts = get_upcoming_appointments(profile.id)

    return render_template(
        'report.html',
        profile=profile,
        meds=meds,
        stats=stats,
        safety_alerts=safety_alerts,
        recent_vitals=recent_vitals,
        upcoming_appts=upcoming_appts
    )

# ----------------- EMERGENCY SOS -----------------

@app.route('/sos', methods=['POST'])
def trigger_sos():
    """Instant Emergency SOS trigger: alerts all family and caregiver members via email & SMS simulation."""
    profile = get_current_profile_or_redirect()
    if not profile:
        return jsonify({'error': 'No active profile'}), 400

    note = request.form.get('emergency_note', 'Assistance button pressed by patient on platform.')
    notify_sos_alert(profile, emergency_note=note)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'message': f'Emergency SOS dispatched to all Care Circle members and {profile.emergency_contact_name}!'
        })

    flash(f"🚨 EMERGENCY ALERT DISPATCHED! All family members and emergency contacts ({profile.emergency_contact_name}) have been notified immediately.", "danger")
    return redirect(url_for('dashboard'))

# ----------------- API ENDPOINTS -----------------

@app.route('/api/reminders/run-now', methods=['POST'])
def trigger_manual_reminders():
    try:
        run_reminder_check(app)
        return jsonify({
            'success': True,
            'message': 'Proactive reminder check executed successfully across all schedules.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/notification-preview/<int:notif_id>')
def notification_preview(notif_id):
    notif = db.session.get(NotificationLog, notif_id)
    if not notif:
        abort(404)
    return jsonify({
        'id': notif.id,
        'subject': notif.subject,
        'recipient': notif.recipient_email,
        'status': notif.status,
        'sent_at': notif.sent_at.strftime('%Y-%m-%d %H:%M:%S UTC'),
        'html': notif.html_content
    })

# ----------------- INITIALIZATION & STARTUP -----------------

def create_app():
    with app.app_context():
        db.create_all()
        migrate_legacy_profile_schema(db.engine)
        seed_demo_data()
    start_reminder_scheduler(app, interval_seconds=60)
    return app

def migrate_legacy_profile_schema(engine):
    """Add profile columns introduced after an existing SQLite database was created."""
    inspector = inspect(engine)
    if 'elderly_profiles' not in inspector.get_table_names():
        return

    profile_columns = {column['name'] for column in inspector.get_columns('elderly_profiles')}
    missing_columns = {
        'physician_phone': 'VARCHAR(30)',
        'last_app_opened': 'DATETIME'
    }
    missing_columns = {
        name: sql_type for name, sql_type in missing_columns.items()
        if name not in profile_columns
    }
    if missing_columns:
        with engine.begin() as connection:
            for name, sql_type in missing_columns.items():
                connection.execute(
                    text(f'ALTER TABLE elderly_profiles ADD COLUMN {name} {sql_type}')
                )

if __name__ == '__main__':
    create_app()
    print("================================================================")
    print("Elderly Care & Medication Management Platform Running!")
    print("Serving on http://127.0.0.1:5000")
    print("Doctor Admin Account: dr.evans@example.com / doc123")
    print("Senior Login: PIN 1234 (Eleanor Vance) | Passcode: CARE74")
    print("================================================================")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
