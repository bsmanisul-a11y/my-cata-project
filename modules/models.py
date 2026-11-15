from datetime import datetime, timezone, date
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import random

db = SQLAlchemy()

def utc_now():
    return datetime.now(timezone.utc)

def generate_family_passcode():
    """Generate a clean, memorable 6-digit uppercase alphanumeric access code."""
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choices(chars, k=6))

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='elderly') # 'elderly', 'caregiver', 'family', 'doctor', 'admin'
    phone = db.Column(db.String(30), nullable=True)
    specialty = db.Column(db.String(100), nullable=True) # For doctors
    hospital_affiliation = db.Column(db.String(150), nullable=True)
    license_no = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Relationships
    elderly_profiles_created = db.relationship('ElderlyProfile', backref='creator', lazy=True, foreign_keys='ElderlyProfile.user_id')
    circle_memberships = db.relationship('CareCircleMember', backref='user', lazy=True)
    caregiver_notes = db.relationship('CaregiverNote', backref='author', lazy=True)
    authored_reports = db.relationship('MedicalReport', backref='doctor', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ElderlyProfile(db.Model):
    __tablename__ = 'elderly_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    full_name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.String(20), nullable=True)
    age = db.Column(db.Integer, nullable=True)
    blood_group = db.Column(db.String(10), nullable=True, default='Unknown')
    allergies = db.Column(db.Text, nullable=True, default='None reported')
    chronic_conditions = db.Column(db.Text, nullable=True, default='Hypertension')
    address = db.Column(db.String(250), nullable=True, default='742 Evergreen Terrace, Chicago, IL')
    emergency_contact_name = db.Column(db.String(100), nullable=True)
    emergency_contact_phone = db.Column(db.String(30), nullable=True)
    emergency_contact_email = db.Column(db.String(120), nullable=True)
    primary_physician = db.Column(db.String(100), nullable=True, default='Dr. Robert Evans (Cardiology)')
    physician_phone = db.Column(db.String(30), nullable=True, default='+1 (555) 789-0123')
    family_passcode = db.Column(db.String(10), unique=True, default=generate_family_passcode)
    senior_pin = db.Column(db.String(6), default="1234") # Quick 4-digit PIN for elderly self-access
    notes = db.Column(db.Text, nullable=True)
    last_app_opened = db.Column(db.DateTime, default=utc_now)
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Relationships
    medications = db.relationship('Medication', backref='profile', cascade='all, delete-orphan', lazy=True)
    appointments = db.relationship('Appointment', backref='profile', cascade='all, delete-orphan', lazy=True)
    vitals = db.relationship('HealthVitalLog', backref='profile', cascade='all, delete-orphan', lazy=True)
    care_circle = db.relationship('CareCircleMember', backref='profile', cascade='all, delete-orphan', lazy=True)
    notes_list = db.relationship('CaregiverNote', backref='profile', cascade='all, delete-orphan', lazy=True)
    notifications = db.relationship('NotificationLog', backref='profile', cascade='all, delete-orphan', lazy=True)
    medical_reports = db.relationship('MedicalReport', backref='profile', cascade='all, delete-orphan', lazy=True)
    ambulance_requests = db.relationship('AmbulanceRequest', backref='profile', cascade='all, delete-orphan', lazy=True)
    delivery_orders = db.relationship('MedicineDeliveryOrder', backref='profile', cascade='all, delete-orphan', lazy=True)
    doctor_calls = db.relationship('DoctorCallRequest', backref='profile', cascade='all, delete-orphan', lazy=True)

class CareCircleMember(db.Model):
    __tablename__ = 'care_circle_members'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('elderly_profiles.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    relation = db.Column(db.String(50), default='Family Member')
    can_manage_meds = db.Column(db.Boolean, default=True)
    receive_email_alerts = db.Column(db.Boolean, default=True)
    is_primary = db.Column(db.Boolean, default=False)
    joined_at = db.Column(db.DateTime, default=utc_now)

class Medication(db.Model):
    __tablename__ = 'medications'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('elderly_profiles.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    dosage = db.Column(db.String(50), nullable=False)
    form = db.Column(db.String(30), default='Pill')
    color_shape = db.Column(db.String(50), default='White Round')
    instructions = db.Column(db.Text, nullable=True)
    purpose = db.Column(db.String(120), nullable=True)
    prescribing_doctor = db.Column(db.String(100), nullable=True)
    current_stock = db.Column(db.Integer, default=30)
    refill_threshold = db.Column(db.Integer, default=7)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    
    schedules = db.relationship('MedicationSchedule', backref='medication', cascade='all, delete-orphan', lazy=True)
    logs = db.relationship('MedicationLog', backref='medication', cascade='all, delete-orphan', lazy=True)

class MedicationSchedule(db.Model):
    __tablename__ = 'medication_schedules'
    
    id = db.Column(db.Integer, primary_key=True)
    medication_id = db.Column(db.Integer, db.ForeignKey('medications.id'), nullable=False)
    time_slot = db.Column(db.String(20), default='Morning')
    scheduled_time = db.Column(db.String(10), nullable=False)
    days_of_week = db.Column(db.String(50), default='Daily')

    logs = db.relationship('MedicationLog', backref='schedule', cascade='all, delete-orphan', lazy=True)

class MedicationLog(db.Model):
    __tablename__ = 'medication_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    medication_id = db.Column(db.Integer, db.ForeignKey('medications.id'), nullable=False)
    schedule_id = db.Column(db.Integer, db.ForeignKey('medication_schedules.id'), nullable=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('elderly_profiles.id'), nullable=False)
    scheduled_date = db.Column(db.String(10), nullable=False) # YYYY-MM-DD
    scheduled_time = db.Column(db.String(10), nullable=False) # HH:MM
    status = db.Column(db.String(20), default='pending')
    logged_at = db.Column(db.DateTime, nullable=True)
    logged_by_name = db.Column(db.String(100), default='Elderly')
    notes = db.Column(db.Text, nullable=True)
    missed_alert_sent = db.Column(db.Boolean, default=False)
    upcoming_alert_sent = db.Column(db.Boolean, default=False)

class Appointment(db.Model):
    __tablename__ = 'appointments'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('elderly_profiles.id'), nullable=False)
    doctor_name = db.Column(db.String(100), nullable=False)
    specialty = db.Column(db.String(100), default='General Physician')
    clinic_name = db.Column(db.String(120), nullable=True)
    location_address = db.Column(db.String(200), nullable=True)
    appointment_date = db.Column(db.String(10), nullable=False) # YYYY-MM-DD
    appointment_time = db.Column(db.String(10), nullable=False) # HH:MM
    transport_needed = db.Column(db.Boolean, default=False)
    transport_status = db.Column(db.String(50), default='Not Needed')
    accompanying_person = db.Column(db.String(100), nullable=True)
    preparation_notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='Scheduled')
    doctor_summary_notes = db.Column(db.Text, nullable=True)
    reminder_sent_24h = db.Column(db.Boolean, default=False)
    reminder_sent_2h = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utc_now)

class HealthVitalLog(db.Model):
    __tablename__ = 'health_vital_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('elderly_profiles.id'), nullable=False)
    log_date = db.Column(db.String(10), default=lambda: datetime.now().strftime('%Y-%m-%d'))
    log_time = db.Column(db.String(10), default=lambda: datetime.now().strftime('%H:%M'))
    systolic_bp = db.Column(db.Integer, nullable=True)
    diastolic_bp = db.Column(db.Integer, nullable=True)
    blood_glucose = db.Column(db.Float, nullable=True)
    heart_rate = db.Column(db.Integer, nullable=True)
    water_glasses = db.Column(db.Integer, default=0)
    mood = db.Column(db.String(20), default='good')
    notes = db.Column(db.Text, nullable=True)
    logged_by_doctor = db.Column(db.Boolean, default=False)
    doctor_name = db.Column(db.String(100), nullable=True)
    is_abnormal = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utc_now)

    def check_abnormality(self):
        abnormal = False
        if self.systolic_bp and (self.systolic_bp >= 140 or self.systolic_bp <= 90):
            abnormal = True
        if self.diastolic_bp and (self.diastolic_bp >= 90 or self.diastolic_bp <= 60):
            abnormal = True
        if self.blood_glucose and (self.blood_glucose >= 140 or self.blood_glucose <= 70):
            abnormal = True
        if self.heart_rate and (self.heart_rate >= 100 or self.heart_rate <= 55):
            abnormal = True
        self.is_abnormal = abnormal
        return abnormal

class CaregiverNote(db.Model):
    __tablename__ = 'caregiver_notes'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('elderly_profiles.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    author_name = db.Column(db.String(100), default='Caregiver')
    category = db.Column(db.String(30), default='General')
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)

class NotificationLog(db.Model):
    __tablename__ = 'notification_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('elderly_profiles.id'), nullable=False)
    recipient_email = db.Column(db.String(120), nullable=False)
    recipient_name = db.Column(db.String(100), default='Family Member')
    subject = db.Column(db.String(200), nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)
    html_content = db.Column(db.Text, nullable=False)
    text_content = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='Sent')
    sent_at = db.Column(db.DateTime, default=utc_now)

class MedicalReport(db.Model):
    __tablename__ = 'medical_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('elderly_profiles.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    doctor_name = db.Column(db.String(100), default='Attending Physician')
    title = db.Column(db.String(150), nullable=False)
    report_type = db.Column(db.String(50), default='Lab Test')
    file_name = db.Column(db.String(250), nullable=True)
    file_path = db.Column(db.String(300), nullable=True)
    summary_findings = db.Column(db.Text, nullable=True)
    doctor_recommendations = db.Column(db.Text, nullable=True)
    report_date = db.Column(db.String(10), default=lambda: datetime.now().strftime('%Y-%m-%d'))
    created_at = db.Column(db.DateTime, default=utc_now)

class AmbulanceRequest(db.Model):
    __tablename__ = 'ambulance_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('elderly_profiles.id'), nullable=False)
    status = db.Column(db.String(30), default='dispatched') # 'dispatched', 'nearby', 'arrived', 'completed', 'cancelled'
    pickup_address = db.Column(db.String(250), nullable=False)
    hospital_destination = db.Column(db.String(200), default='St. Jude Emergency Medical Center')
    paramedic_name = db.Column(db.String(100), default='Paramedic Alex Martinez')
    paramedic_phone = db.Column(db.String(30), default='+1 (555) 911-0422')
    vehicle_number = db.Column(db.String(30), default='AMB-UNIT-402')
    eta_minutes = db.Column(db.Integer, default=11)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now)

class MedicineDeliveryOrder(db.Model):
    __tablename__ = 'medicine_delivery_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('elderly_profiles.id'), nullable=False)
    hospital_name = db.Column(db.String(150), default='St. Jude Hospital Pharmacy')
    medication_id = db.Column(db.Integer, db.ForeignKey('medications.id'), nullable=True)
    medication_name = db.Column(db.String(100), nullable=False)
    dosage = db.Column(db.String(50), nullable=True)
    quantity = db.Column(db.Integer, default=30)
    delivery_address = db.Column(db.String(250), nullable=False)
    contact_phone = db.Column(db.String(30), nullable=True)
    status = db.Column(db.String(30), default='on_the_way') # 'on_the_way', 'arrived', 'checked', 'delivered'
    rider_name = db.Column(db.String(100), default='Express Rider Michael Chen')
    rider_phone = db.Column(db.String(30), default='+1 (555) 345-0199')
    vehicle_number = db.Column(db.String(30), default='PHARM-EXPRESS-18')
    eta_minutes = db.Column(db.Integer, default=14)
    is_checked = db.Column(db.Boolean, default=False)
    payment_method = db.Column(db.String(20), nullable=True) # 'Cash', 'UPI'
    upi_id = db.Column(db.String(100), nullable=True)
    total_amount = db.Column(db.Float, default=24.50)
    created_at = db.Column(db.DateTime, default=utc_now)
    delivered_at = db.Column(db.DateTime, nullable=True)

class DoctorCallRequest(db.Model):
    __tablename__ = 'doctor_call_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('elderly_profiles.id'), nullable=False)
    doctor_name = db.Column(db.String(100), default='Dr. Robert Evans, MD')
    urgency = db.Column(db.String(20), default='urgent') # 'emergency', 'urgent', 'routine'
    patient_query = db.Column(db.Text, nullable=False)
    callback_phone = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(20), default='pending') # 'pending', 'called_back', 'resolved'
    created_at = db.Column(db.DateTime, default=utc_now)
