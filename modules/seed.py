"""
Database Seed & Demo Generator for Elderly Care Platform
Pre-populates the database with realistic healthcare profiles, medication schedules,
adherence history, upcoming doctor appointments, care circle notes, doctor accounts, and reports.
"""

from datetime import datetime, date, timedelta, timezone
from werkzeug.security import generate_password_hash
from modules.models import (
    db, User, ElderlyProfile, CareCircleMember,
    Medication, MedicationSchedule, MedicationLog,
    Appointment, HealthVitalLog, CaregiverNote, NotificationLog,
    MedicalReport, AmbulanceRequest
)

def seed_demo_data():
    """Generates complete realistic demo data if database is empty."""
    # Check if doctor already exists
    if User.query.filter_by(email="dr.evans@example.com").first():
        return

    print("[Seed] Populating realistic demonstration data...")

    # 1. USERS (Senior, Family, Nurse, Doctor)
    user_eleanor = User.query.filter_by(email="eleanor@example.com").first()
    if not user_eleanor:
        user_eleanor = User(
            name="Eleanor Vance",
            email="eleanor@example.com",
            password_hash=generate_password_hash("senior123"),
            role="elderly",
            phone="+1 (555) 234-5678"
        )
        db.session.add(user_eleanor)

    user_david = User.query.filter_by(email="david.vance@example.com").first()
    if not user_david:
        user_david = User(
            name="David Vance",
            email="david.vance@example.com",
            password_hash=generate_password_hash("care123"),
            role="family",
            phone="+1 (555) 345-6789"
        )
        db.session.add(user_david)

    user_maria = User.query.filter_by(email="nurse.maria@example.com").first()
    if not user_maria:
        user_maria = User(
            name="Nurse Maria Santos",
            email="nurse.maria@example.com",
            password_hash=generate_password_hash("nurse123"),
            role="caregiver",
            phone="+1 (555) 456-7890"
        )
        db.session.add(user_maria)

    # DOCTOR / ADMIN ACCOUNT
    user_doctor = User.query.filter_by(email="dr.evans@example.com").first()
    if not user_doctor:
        user_doctor = User(
            name="Dr. Robert Evans, MD",
            email="dr.evans@example.com",
            password_hash=generate_password_hash("doc123"),
            role="doctor",
            phone="+1 (555) 789-0123",
            specialty="Cardiology & Internal Medicine",
            hospital_affiliation="St. Jude Heart & Vascular Pavilion",
            license_no="MED-IL-89421-C"
        )
        db.session.add(user_doctor)

    db.session.flush()

    # 2. ELDERLY PROFILES
    profile_eleanor = ElderlyProfile.query.filter_by(full_name="Eleanor Vance").first()
    if not profile_eleanor:
        profile_eleanor = ElderlyProfile(
            user_id=user_eleanor.id,
            full_name="Eleanor Vance",
            date_of_birth="1952-04-12",
            age=74,
            blood_group="A+",
            allergies="Penicillin, Sulfa drugs",
            chronic_conditions="Type 2 Diabetes, Hypertension, Mild Osteoarthritis",
            address="742 Evergreen Terrace, Chicago, IL",
            emergency_contact_name="David Vance (Son)",
            emergency_contact_phone="+1 (555) 345-6789",
            emergency_contact_email="david.vance@example.com",
            primary_physician="Dr. Robert Evans (Cardiology)",
            family_passcode="CARE74",
            senior_pin="1234",
            notes="Prefers large print. Enjoys morning garden walks. Needs reminders to drink adequate water."
        )
        db.session.add(profile_eleanor)

    profile_arthur = ElderlyProfile.query.filter_by(full_name="Arthur Pendelton").first()
    if not profile_arthur:
        profile_arthur = ElderlyProfile(
            full_name="Arthur Pendelton",
            date_of_birth="1945-09-28",
            age=81,
            blood_group="O+",
            allergies="Aspirin (Causes stomach bleeding)",
            chronic_conditions="Atrial Fibrillation, Chronic Kidney Disease Stage 2",
            address="108 Oakwood Ave, Chicago, IL",
            emergency_contact_name="Sarah Jenkins (Daughter)",
            emergency_contact_phone="+1 (555) 890-1234",
            emergency_contact_email="sarah.jenkins@example.com",
            primary_physician="Dr. Maya Patel (Internal Medicine)",
            family_passcode="CARE81",
            senior_pin="4321",
            notes="Uses a walking cane. Needs blood thinner INR monitoring bi-weekly."
        )
        db.session.add(profile_arthur)

    db.session.flush()

    # 3. CARE CIRCLE MEMBERSHIPS
    if not CareCircleMember.query.filter_by(profile_id=profile_eleanor.id).first():
        circle1 = CareCircleMember(
            profile_id=profile_eleanor.id,
            user_id=user_david.id,
            relation="Son (Primary Caregiver)",
            can_manage_meds=True,
            receive_email_alerts=True,
            is_primary=True
        )
        circle2 = CareCircleMember(
            profile_id=profile_eleanor.id,
            user_id=user_maria.id,
            relation="Visiting Home Nurse",
            can_manage_meds=True,
            receive_email_alerts=True,
            is_primary=False
        )
        db.session.add_all([circle1, circle2])

    # 4. MEDICATIONS FOR ELEANOR
    if not Medication.query.filter_by(profile_id=profile_eleanor.id).first():
        med1 = Medication(
            profile_id=profile_eleanor.id,
            name="Metformin",
            dosage="500 mg",
            form="Pill",
            color_shape="White Oval",
            instructions="Take with meals (breakfast & dinner) to reduce stomach upset.",
            purpose="Type 2 Diabetes / Blood Glucose Control",
            prescribing_doctor="Dr. Maya Patel",
            current_stock=24,
            refill_threshold=7,
            is_active=True
        )
        med2 = Medication(
            profile_id=profile_eleanor.id,
            name="Lisinopril",
            dosage="10 mg",
            form="Pill",
            color_shape="Pink Round",
            instructions="Take in the morning with a full glass of water. Rise slowly if dizzy.",
            purpose="High Blood Pressure (Hypertension)",
            prescribing_doctor="Dr. Robert Evans",
            current_stock=18,
            refill_threshold=6,
            is_active=True
        )
        med3 = Medication(
            profile_id=profile_eleanor.id,
            name="Atorvastatin",
            dosage="20 mg",
            form="Pill",
            color_shape="White Round",
            instructions="Take at bedtime. Avoid grapefruit and grapefruit juice.",
            purpose="Cholesterol Management / Heart Protection",
            prescribing_doctor="Dr. Robert Evans",
            current_stock=4, # LOW STOCK trigger demo
            refill_threshold=7,
            is_active=True
        )
        med4 = Medication(
            profile_id=profile_eleanor.id,
            name="Vitamin D3",
            dosage="1,000 IU",
            form="Capsule",
            color_shape="Golden Gel",
            instructions="Take in the morning after breakfast.",
            purpose="Bone Density & Joint Health",
            prescribing_doctor="Dr. Robert Evans",
            current_stock=45,
            refill_threshold=10,
            is_active=True
        )
        db.session.add_all([med1, med2, med3, med4])
        db.session.flush()

        # SCHEDULES FOR ELEANOR
        sched_met_morn = MedicationSchedule(medication_id=med1.id, time_slot="Morning", scheduled_time="08:00", days_of_week="Daily")
        sched_met_eve = MedicationSchedule(medication_id=med1.id, time_slot="Evening", scheduled_time="19:00", days_of_week="Daily")
        sched_lis_morn = MedicationSchedule(medication_id=med2.id, time_slot="Morning", scheduled_time="08:00", days_of_week="Daily")
        sched_ator_bed = MedicationSchedule(medication_id=med3.id, time_slot="Bedtime", scheduled_time="21:30", days_of_week="Daily")
        sched_vit_morn = MedicationSchedule(medication_id=med4.id, time_slot="Morning", scheduled_time="08:30", days_of_week="Daily")
        db.session.add_all([sched_met_morn, sched_met_eve, sched_lis_morn, sched_ator_bed, sched_vit_morn])
        db.session.flush()

        # TODAY'S LOGS FOR ELEANOR
        today = date.today()
        today_str = today.strftime('%Y-%m-%d')
        log_today_met_morn = MedicationLog(
            medication_id=med1.id, schedule_id=sched_met_morn.id, profile_id=profile_eleanor.id,
            scheduled_date=today_str, scheduled_time="08:00", status='taken',
            logged_at=datetime.now(), logged_by_name="Eleanor Vance"
        )
        log_today_lis = MedicationLog(
            medication_id=med2.id, schedule_id=sched_lis_morn.id, profile_id=profile_eleanor.id,
            scheduled_date=today_str, scheduled_time="08:00", status='taken',
            logged_at=datetime.now(), logged_by_name="Eleanor Vance"
        )
        log_today_met_eve = MedicationLog(
            medication_id=med1.id, schedule_id=sched_met_eve.id, profile_id=profile_eleanor.id,
            scheduled_date=today_str, scheduled_time="19:00", status='pending'
        )
        log_today_ator = MedicationLog(
            medication_id=med3.id, schedule_id=sched_ator_bed.id, profile_id=profile_eleanor.id,
            scheduled_date=today_str, scheduled_time="21:30", status='pending'
        )
        db.session.add_all([log_today_met_morn, log_today_lis, log_today_met_eve, log_today_ator])

    # 5. UPCOMING APPOINTMENTS FOR ELEANOR
    if not Appointment.query.filter_by(profile_id=profile_eleanor.id).first():
        today = date.today()
        appt1_date = (today + timedelta(days=2)).strftime('%Y-%m-%d')
        appt2_date = (today + timedelta(days=9)).strftime('%Y-%m-%d')

        appt1 = Appointment(
            profile_id=profile_eleanor.id,
            doctor_name="Robert Evans",
            specialty="Cardiology",
            clinic_name="Heart Health Pavilion, Suite 402",
            location_address="450 Medical Center Blvd, Chicago, IL",
            appointment_date=appt1_date,
            appointment_time="10:30",
            transport_needed=True,
            transport_status="Arranged by Family (David)",
            accompanying_person="David Vance",
            preparation_notes="Bring recent blood pressure logs and current medication list. Fasting not required.",
            status="Scheduled"
        )
        appt2 = Appointment(
            profile_id=profile_eleanor.id,
            doctor_name="Clara Harris",
            specialty="Ophthalmology",
            clinic_name="Precision Eye Care Center",
            location_address="1200 Lakeview Parkway, Chicago, IL",
            appointment_date=appt2_date,
            appointment_time="14:15",
            transport_needed=True,
            transport_status="Needs Ride / Volunteer",
            accompanying_person="Nurse Maria Santos",
            preparation_notes="Pupil dilation test planned. Bring dark sunglasses for ride home.",
            status="Scheduled"
        )
        db.session.add_all([appt1, appt2])

    # 6. HISTORICAL HEALTH VITALS (for trend graphs)
    if not HealthVitalLog.query.filter_by(profile_id=profile_eleanor.id).first():
        today = date.today()
        vital_samples = [
            (6, "08:15", 136, 88, 128.0, 78, 5, "good", "Normal morning walk", False),
            (5, "08:20", 132, 84, 122.0, 76, 6, "good", "Felt comfortable", False),
            (4, "08:10", 128, 82, 118.0, 74, 6, "happy", "Active in garden", False),
            (3, "08:30", 142, 92, 146.0, 84, 4, "tired", "Slight headache, rested after lunch", False), # Abnormal sample
            (2, "08:15", 128, 80, 116.0, 72, 7, "good", "Felt much better", False),
            (1, "08:20", 124, 78, 112.0, 70, 6, "good", "Dr. Evans routine review", True), # Doctor checked
            (0, "08:15", 122, 78, 110.0, 70, 7, "happy", "Gentle stretching and tea", False)
        ]
        for days_ago, v_time, sbp, dbp, glu, hr, water, mood, notes, by_doc in vital_samples:
            d_str = (today - timedelta(days=days_ago)).strftime('%Y-%m-%d')
            v = HealthVitalLog(
                profile_id=profile_eleanor.id,
                log_date=d_str,
                log_time=v_time,
                systolic_bp=sbp,
                diastolic_bp=dbp,
                blood_glucose=glu,
                heart_rate=hr,
                water_glasses=water,
                mood=mood,
                notes=notes,
                logged_by_doctor=by_doc,
                doctor_name="Dr. Robert Evans" if by_doc else None
            )
            v.check_abnormality()
            db.session.add(v)

    # 7. MEDICAL REPORTS UPLOADED BY DOCTOR
    if not MedicalReport.query.filter_by(profile_id=profile_eleanor.id).first():
        rep1 = MedicalReport(
            profile_id=profile_eleanor.id,
            doctor_id=user_doctor.id,
            doctor_name="Dr. Robert Evans, MD",
            title="Comprehensive Metabolic Panel & Lipid Profile",
            report_type="Lab Test",
            summary_findings="Total Cholesterol: 184 mg/dL (Improved from 215 mg/dL). HDL: 52 mg/dL. LDL: 104 mg/dL. Kidney BUN & Creatinine normal. Liver enzymes within standard reference bounds.",
            doctor_recommendations="Continue Atorvastatin 20mg at bedtime. Maintain Mediterranean diet low in saturated fats. Repeat lipid panel in 6 months.",
            report_date=(date.today() - timedelta(days=5)).strftime('%Y-%m-%d')
        )
        rep2 = MedicalReport(
            profile_id=profile_eleanor.id,
            doctor_id=user_doctor.id,
            doctor_name="Dr. Robert Evans, MD",
            title="12-Lead Diagnostic Electrocardiogram (ECG)",
            report_type="ECG",
            summary_findings="Normal sinus rhythm with a resting heart rate of 72 bpm. PR interval 160 ms. No acute ischemic ST-T changes. Voltage criteria consistent with mild left ventricular hypertrophy secondary to chronic hypertension.",
            doctor_recommendations="Continue Lisinopril 10mg daily. Good blood pressure control is successfully preventing cardiac remodeling. Followup cardiology consultation scheduled.",
            report_date=(date.today() - timedelta(days=12)).strftime('%Y-%m-%d')
        )
        db.session.add_all([rep1, rep2])

    db.session.commit()
    print("[Seed] Successfully populated demo database (No active ambulance by default; dispatches only on request).")
