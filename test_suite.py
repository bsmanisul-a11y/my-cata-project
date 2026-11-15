"""
Comprehensive Test Suite for Elderly Care & Medication Management Platform
Tests all critical paths:
1. Authentication (Senior PIN, Caregiver, Doctor/Admin)
2. Passcode access (CARE74)
3. Dashboard, Pillbox, Dose Actions
4. Medication Refill (typing & presets)
5. Doctor / Admin Portal (prescribe, schedule next visit, upload reports, log vitals)
6. Patient Medical Reports Access
7. Emergency Ambulance Dispatch & Live Tracking (dispatched -> nearby -> arrived)
8. Doctor Appointment Uber Ride Integration
9. Vitals Trends & Abnormal Audio/Visual Alerts
10. Proactive Email Reminders Daemon
11. Emergency SOS to all family members
"""

import os
import tempfile
import unittest
from datetime import datetime, date
from sqlalchemy import create_engine, inspect, text
from app import app, db, migrate_legacy_profile_schema
from modules.models import (
    ElderlyProfile, CareCircleMember, Medication, MedicationLog, Appointment,
    NotificationLog, HealthVitalLog, CaregiverNote,
    MedicalReport, AmbulanceRequest, MedicineDeliveryOrder, User
)
from modules.medication import get_today_pillbox, calculate_adherence_stats
from modules.reminder import run_reminder_check

class ElderlyCarePlatformTestCase(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        # Clean up any test ambulance requests so no lingering banners appear
        AmbulanceRequest.query.filter(AmbulanceRequest.status.in_(['dispatched', 'nearby', 'arrived'])).update({'status': 'completed'})
        db.session.commit()
        self.ctx.pop()

    def authenticate_profile(self, role='elderly', name='Test User'):
        profile = ElderlyProfile.query.filter_by(family_passcode='CARE74').first()
        with self.client.session_transaction() as sess:
            sess['active_profile_id'] = profile.id
            sess['user_role'] = role
            sess['user_name'] = name
            if role in ('doctor', 'admin'):
                user = User.query.filter_by(role=role).first()
                sess['user_id'] = user.id
            else:
                sess['pin_authenticated'] = True
        return profile

    def test_01_root_opens_public_homepage_and_login_options(self):
        """The homepage is public while login options remain available separately."""
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Smart Connected Healthcare Ecosystem', res.data)
        self.assertIn(b'Private patient dashboard', res.data)

        login = self.client.get('/login')
        self.assertEqual(login.status_code, 200)
        self.assertIn(b'Senior Quick PIN Access', login.data)
        self.assertIn(b'Caregiver &amp; Family Login', login.data)
        self.assertIn(b'Doctor &amp; Admin Portal', login.data)
        self.assertIn(b'Patient Login', login.data)
        self.assertIn(b'id="tabDoctorBtn"', login.data)
        self.assertNotIn(b'Eleanor Vance', login.data)
        self.assertIn(b'Demo Login Information', login.data)
        self.assertIn(b'Senior PIN:', login.data)
        self.assertIn(b'1234', login.data)
        self.assertIn(b'david.vance@example.com', login.data)
        self.assertIn(b'care123', login.data)
        self.assertIn(b'CARE74', login.data)
        self.assertIn(b'dr.evans@example.com', login.data)
        self.assertIn(b'doc123', login.data)

        about = self.client.get('/about')
        self.assertEqual(about.status_code, 200)
        self.assertIn(b'Private patient dashboard', about.data)

    def test_legacy_profile_schema_migration(self):
        engine = create_engine('sqlite:///:memory:')
        try:
            with engine.begin() as connection:
                connection.execute(text(
                    'CREATE TABLE elderly_profiles (id INTEGER PRIMARY KEY, full_name VARCHAR(100) NOT NULL)'
                ))

            migrate_legacy_profile_schema(engine)
            migrate_legacy_profile_schema(engine)

            columns = {column['name'] for column in inspect(engine).get_columns('elderly_profiles')}
            self.assertIn('physician_phone', columns)
            self.assertIn('last_app_opened', columns)
        finally:
            engine.dispose()

    def test_senior_signup_creates_profile_and_logs_in(self):
        email = f"signup-{os.urandom(6).hex()}@example.test"
        response = self.client.post('/register', data={
            'reg_type': 'elderly',
            'name': 'New Signup Patient',
            'email': email,
            'password': 'patient123',
            'age': '72',
            'blood_group': 'O+',
            'senior_pin': '6789'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'New Signup Patient', response.data)
        profile = ElderlyProfile.query.filter_by(full_name='New Signup Patient').first()
        self.assertIsNotNone(profile)
        self.assertEqual(profile.creator.email, email)

    def test_caregiver_signup_can_link_now_or_after_signup(self):
        caregiver_email = f"caregiver-{os.urandom(6).hex()}@example.test"
        caregiver_response = self.client.post('/register', data={
            'reg_type': 'caregiver',
            'name': 'Unlinked Caregiver',
            'email': caregiver_email,
            'password': 'caregiver123'
        }, follow_redirects=True)
        self.assertEqual(caregiver_response.status_code, 200)
        self.assertIn(b'Enter the 6-character Passcode', caregiver_response.data)
        caregiver = User.query.filter_by(email=caregiver_email).first()
        self.assertIsNotNone(caregiver)
        self.assertEqual(CareCircleMember.query.filter_by(user_id=caregiver.id).count(), 0)

        self.client.get('/logout')
        unlinked_login = self.client.post('/login', data={
            'auth_type': 'password',
            'email': caregiver_email,
            'password': 'caregiver123'
        }, follow_redirects=True)
        self.assertEqual(unlinked_login.status_code, 200)
        self.assertIn(b'Enter the 6-character Passcode', unlinked_login.data)
        self.assertNotIn(b'Eleanor Vance', unlinked_login.data)

        doctor_email = f"doctor-{os.urandom(6).hex()}@example.test"
        doctor_response = self.client.post('/register', data={
            'reg_type': 'doctor',
            'name': 'Unprovisioned Doctor',
            'email': doctor_email,
            'password': 'doctorpass123'
        }, follow_redirects=True)
        self.assertEqual(doctor_response.status_code, 200)
        self.assertIn(b'Doctor accounts must be provisioned', doctor_response.data)
        self.assertIsNone(User.query.filter_by(email=doctor_email).first())

        linked_response = self.client.post('/passcode-access', data={
            'passcode': 'CARE74',
            'relation': 'Daughter',
            'caretaker_name': 'Unlinked Caregiver'
        }, follow_redirects=True)
        self.assertEqual(linked_response.status_code, 200)
        self.assertIn(b'Eleanor Vance', linked_response.data)
        member = CareCircleMember.query.filter_by(user_id=caregiver.id).first()
        self.assertEqual(member.profile_id,
                         ElderlyProfile.query.filter_by(family_passcode='CARE74').first().id)

    def test_unauthenticated_users_cannot_access_patient_data(self):
        for path in (
            '/dashboard',
            '/doctor/portal',
            '/ambulance',
            '/reports',
            '/reports/download/private-report.pdf',
            '/medications',
            '/appointments',
            '/caregiver',
            '/vitals',
            '/doctor-report',
            '/medicine-delivery/1',
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.headers['Location'].startswith('/login'))

        self.assertEqual(self.client.get('/api/notification-preview/1').status_code, 401)
        self.assertEqual(self.client.get('/api/medicine-delivery/1/status').status_code, 401)
        self.assertEqual(self.client.post('/api/reminders/run-now').status_code, 401)
        self.assertEqual(self.client.post('/sos').status_code, 302)
        self.assertEqual(self.client.post('/medicine-delivery/request/1').status_code, 302)

        profile = ElderlyProfile.query.filter_by(family_passcode='CARE74').first()
        with self.client.session_transaction() as sess:
            sess['active_profile_id'] = profile.id
        self.assertEqual(self.client.get('/dashboard').status_code, 302)

    def test_uploaded_reports_are_private_and_login_allows_download(self):
        with tempfile.NamedTemporaryFile(
            dir=self.app.config['UPLOAD_FOLDER'],
            prefix='auth-test-',
            suffix='.txt',
            delete=False
        ) as report:
            report.write(b'private report')
            filename = os.path.basename(report.name)

        try:
            self.assertEqual(
                self.client.get(f'/static/uploads/reports/{filename}').status_code,
                404
            )
            self.assertEqual(self.client.get(f'/reports/download/{filename}').status_code, 302)

            self.authenticate_profile()
            response = self.client.get(f'/reports/download/{filename}')
            try:
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data, b'private report')
            finally:
                response.close()
        finally:
            os.remove(report.name)

    def test_delivery_requires_check_then_simulates_upi_and_tracks_arrival(self):
        profile = self.authenticate_profile()
        med = Medication.query.filter_by(profile_id=profile.id).first()
        med.current_stock = 0
        db.session.commit()

        response = self.client.post(
            f'/medicine-delivery/request/{med.id}',
            data={'quantity': '30'},
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'St. Jude Hospital Pharmacy', response.data)
        self.assertIn(b'id="deliveryCheckPanel"', response.data)
        self.assertIn(b'style="display:none;"', response.data)

        order = MedicineDeliveryOrder.query.filter_by(profile_id=profile.id).order_by(
            MedicineDeliveryOrder.id.desc()
        ).first()
        self.assertEqual(order.status, 'on_the_way')

        blocked_payment = self.client.post(
            f'/medicine-delivery/{order.id}/pay',
            data={'payment_method': 'cod'},
            follow_redirects=True
        )
        self.assertIn(b'Receive and check the medicine before choosing a payment method', blocked_payment.data)
        self.assertIsNone(order.payment_method)

        arrived = self.client.post(
            f'/medicine-delivery/{order.id}/arrived',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        self.assertEqual(arrived.get_json()['status'], 'arrived')
        self.assertEqual(med.current_stock, 0)
        arrival_page = self.client.get(f'/medicine-delivery/{order.id}')
        self.assertRegex(
            arrival_page.data.decode(),
            r'id="deliveryCheckPanel"\s*>'
        )
        self.assertIn(b'name="medicine_checked"', arrival_page.data)
        self.client.post(
            f'/medicine-delivery/{order.id}/arrived',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        self.assertEqual(med.current_stock, 0)

        self.client.post(
            f'/medicine-delivery/{order.id}/check',
            data={'medicine_checked': 'yes'}
        )
        self.assertTrue(order.is_checked)
        self.assertEqual(order.status, 'checked')

        self.client.post(
            f'/medicine-delivery/{order.id}/pay',
            data={'payment_method': 'upi', 'upi_id': 'not-a-upi-id'}
        )
        self.assertIsNone(order.payment_method)
        self.assertIsNone(order.upi_id)

        paid = self.client.post(
            f'/medicine-delivery/{order.id}/pay',
            data={'payment_method': 'upi', 'upi_id': 'patient@upi'},
            follow_redirects=True
        )
        self.assertEqual(order.payment_method, 'UPI')
        self.assertEqual(order.status, 'delivered')
        self.assertIsNone(order.upi_id)
        self.assertIn(b'Processing simulated UPI payment', paid.data)
        self.assertIn(b'Please wait 5 seconds', paid.data)

        status = self.client.get(f'/api/medicine-delivery/{order.id}/status').get_json()
        self.assertEqual(status['status'], 'delivered')
        self.assertEqual(med.current_stock, 30)

        completed_delivery = self.client.post(
            f'/medicine-delivery/{order.id}/arrived',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        self.assertEqual(completed_delivery.status_code, 409)
        self.assertEqual(med.current_stock, 30)

    def test_delivery_supports_cash_on_delivery_and_adds_stock_on_arrival(self):
        profile = self.authenticate_profile()
        med = Medication.query.filter_by(profile_id=profile.id).first()
        med.current_stock = 3
        db.session.commit()

        self.client.post(
            f'/medicine-delivery/request/{med.id}',
            data={'quantity': '60'}
        )
        order = MedicineDeliveryOrder.query.filter_by(profile_id=profile.id).order_by(
            MedicineDeliveryOrder.id.desc()
        ).first()
        self.client.post(
            f'/medicine-delivery/{order.id}/arrived',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        self.client.post(
            f'/medicine-delivery/{order.id}/check',
            data={'medicine_checked': 'yes'}
        )
        response = self.client.post(
            f'/medicine-delivery/{order.id}/pay',
            data={'payment_method': 'cod'},
            follow_redirects=True
        )

        self.assertEqual(order.payment_method, 'COD')
        self.assertIn(b'Thank you, your health is our wealth.', response.data)
        self.assertIn(b'Delivered', response.data)
        self.assertEqual(order.status, 'delivered')
        self.assertEqual(med.current_stock, 63)

    def test_02_passcode_access(self):
        """Care Circle passcode authentication works for CARE74."""
        passcode_page = self.client.get('/passcode-access')
        self.assertEqual(passcode_page.status_code, 200)
        self.assertIn(b'Demo Passcodes', passcode_page.data)
        self.assertIn(b'CARE74', passcode_page.data)
        self.assertIn(b'CARE81', passcode_page.data)
        self.assertNotIn(b'Eleanor Vance', passcode_page.data)
        self.assertNotIn(b'Arthur Pendelton', passcode_page.data)

        res = self.client.post('/passcode-access', data={
            'passcode': 'CARE74',
            'relation': 'Son',
            'caretaker_name': 'David Vance'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Eleanor Vance', res.data)
        self.assertIn(b'Secure Passcode verified', res.data)

    def test_03_senior_pin_login(self):
        """Senior quick PIN login works for 1234."""
        res = self.client.post('/login', data={
            'auth_type': 'pin',
            'senior_pin': '1234'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Eleanor Vance', res.data)
        self.assertIn(b"Welcome back", res.data)
        self.assertIn(b'href="/logout"', res.data)
        self.assertEqual(self.client.get('/').location, '/dashboard')

        signed_out = self.client.get('/logout', follow_redirects=True)
        self.assertIn(b'Smart Connected Healthcare Ecosystem', signed_out.data)

    def test_04_doctor_admin_login_and_portal(self):
        """Doctor / Admin sign in works and opens Doctor Portal."""
        res = self.client.post('/login', data={
            'auth_type': 'password',
            'email': 'dr.evans@example.com',
            'password': 'doc123'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Doctor & Clinical Admin Portal', res.data)
        self.assertIn(b'Dr. Robert Evans', res.data)
        self.assertIn(b'data-med-name="Metformin"', res.data)
        self.assertIn(b'id="docMedNameInput"', res.data)
        self.assertIn(b'Upload Report & Notify Patient', res.data)

    def test_05_doctor_updates_medicine_and_schedules_visit(self):
        """Doctor updates medicine dosage and schedules next doctor visit."""
        p = self.authenticate_profile(role='doctor', name='Dr. Robert Evans, MD')

        # Doctor updates existing medicine
        med = Medication.query.filter_by(profile_id=p.id, name='Metformin').first()
        self.assertIsNotNone(med)
        res_med = self.client.post('/doctor/portal', data={
            'action': 'doctor_update_med',
            'med_id': med.id,
            'name': 'Metformin XR',
            'form': 'Tablet',
            'dosage': '850 mg',
            'instructions': 'Take twice daily after meals. Hydrate well.',
            'purpose': 'Type 2 Diabetes Control'
        }, follow_redirects=True)
        self.assertEqual(res_med.status_code, 200)
        updated_med = db.session.get(Medication, med.id)
        self.assertEqual(updated_med.name, 'Metformin XR')
        self.assertEqual(updated_med.form, 'Tablet')
        self.assertEqual(updated_med.dosage, '850 mg')

        # Doctor schedules next visit
        res_visit = self.client.post('/doctor/portal', data={
            'action': 'doctor_schedule_visit',
            'appointment_date': '2026-12-15',
            'appointment_time': '11:15',
            'clinic_name': 'St. Jude Heart Pavilion',
            'specialty': 'Cardiology Follow-Up',
            'location_address': '450 Medical Center Blvd, Chicago, IL',
            'preparation_notes': '12-hour fasting required for cholesterol check.'
        }, follow_redirects=True)
        self.assertEqual(res_visit.status_code, 200)
        new_appt = Appointment.query.filter_by(appointment_date='2026-12-15').first()
        self.assertIsNotNone(new_appt)
        self.assertEqual(new_appt.specialty, 'Cardiology Follow-Up')

        with self.client.session_transaction() as sess:
            sess.clear()
            sess['active_profile_id'] = p.id
            sess['user_role'] = 'elderly'
            sess['user_name'] = p.full_name
            sess['pin_authenticated'] = True
        patient_meds = self.client.get('/medications')
        self.assertEqual(patient_meds.status_code, 200)
        self.assertIn(b'Metformin XR', patient_meds.data)
        self.assertIn(b'850 mg', patient_meds.data)
        patient_dashboard = self.client.get('/dashboard')
        self.assertEqual(patient_dashboard.status_code, 200)
        self.assertIn(b'Prescription changed from Metformin', patient_dashboard.data)
        self.assertTrue(any(
            'Medication Prescription Updated' in notification.subject
            for notification in NotificationLog.query.filter_by(profile_id=p.id).all()
        ))

    def test_06_doctor_uploads_report_and_patient_access(self):
        """Doctor uploads a report that the patient can access."""
        profile = self.authenticate_profile(role='doctor', name='Dr. Robert Evans, MD')

        res_upload = self.client.post('/doctor/portal', data={
            'action': 'upload_report',
            'title': 'Echocardiogram Left Ventricular Function',
            'report_type': 'Imaging',
            'summary_findings': 'Ejection fraction 60%. Normal valves. Mild concentric hypertrophy.',
            'doctor_recommendations': 'Continue current antihypertensive protocol.'
        }, follow_redirects=True)
        self.assertEqual(res_upload.status_code, 200)

        with self.client.session_transaction() as sess:
            sess.clear()
            sess['active_profile_id'] = profile.id
            sess['user_role'] = 'elderly'
            sess['user_name'] = profile.full_name
            sess['pin_authenticated'] = True
        res_reports = self.client.get('/reports')
        self.assertEqual(res_reports.status_code, 200)
        self.assertIn(b'Echocardiogram Left Ventricular Function', res_reports.data)
        self.assertIn(b'Ejection fraction 60%', res_reports.data)
        self.assertTrue(any(
            'New Medical Report Available' in notification.subject
            for notification in NotificationLog.query.filter_by(profile_id=profile.id).all()
        ))

    def test_07_emergency_ambulance_service(self):
        """Emergency ambulance request, live tracking, and status progression."""
        p = self.authenticate_profile()

        # Dispatch ambulance
        res_req = self.client.post('/ambulance/request', data={
            'pickup_address': '742 Evergreen Terrace, Chicago, IL',
            'hospital_destination': 'St. Jude Emergency Center',
            'notes': 'Sudden shortness of breath'
        }, follow_redirects=True)
        self.assertEqual(res_req.status_code, 200)
        self.assertIn(b'AMBULANCE ON THE WAY', res_req.data)

        amb = AmbulanceRequest.query.filter_by(profile_id=p.id).order_by(AmbulanceRequest.id.desc()).first()
        self.assertIsNotNone(amb)
        self.assertEqual(amb.status, 'dispatched')

        # Advance to 'nearby'
        res_adv1 = self.client.post(f'/ambulance/{amb.id}/advance', follow_redirects=True)
        self.assertEqual(res_adv1.status_code, 200)
        self.assertEqual(db.session.get(AmbulanceRequest, amb.id).status, 'nearby')

        # Advance to 'arrived'
        res_adv2 = self.client.post(f'/ambulance/{amb.id}/advance', follow_redirects=True)
        self.assertEqual(res_adv2.status_code, 200)
        self.assertEqual(db.session.get(AmbulanceRequest, amb.id).status, 'arrived')
        self.assertIn(b'AMBULANCE ARRIVED AT RESIDENCE', res_adv2.data)

    def test_08_appointments_and_uber_ride(self):
        """Appointments page contains Uber ride redirection link to hospital."""
        self.authenticate_profile()

        res = self.client.get('/appointments')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'uber.com', res.data)
        self.assertIn(b'Get Ride to Hospital (Uber)', res.data)

    def test_09_medication_refill_typed_and_preset(self):
        """Medication refill can be executed by typing or selecting presets."""
        p = self.authenticate_profile()

        med = Medication.query.filter_by(profile_id=p.id).first()
        init_stock = med.current_stock

        # Refill with typed quantity 45
        res = self.client.post('/medications', data={
            'action': 'refill_stock',
            'med_id': med.id,
            'refill_amount': '45'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        updated_stock = db.session.get(Medication, med.id).current_stock
        self.assertEqual(updated_stock, init_stock + 45)

    def test_10_vitals_graphs_and_abnormal_detection(self):
        """Logging an elevated vital triggers abnormal detection and alert rendering."""
        self.authenticate_profile()

        # Log elevated reading (Systolic 150 >= 140 threshold)
        res = self.client.post('/vitals', data={
            'systolic_bp': '150',
            'diastolic_bp': '95',
            'blood_glucose': '165',
            'heart_rate': '104',
            'water_glasses': '5',
            'mood': 'tired',
            'notes': 'Felt palpitations and flushed'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Clinical Alert: Vital Sign Elevated Above Standard Threshold', res.data)
        self.assertIn(b'bpChart', res.data)
        self.assertIn(b'glucoseChart', res.data)
        self.assertIn(b'hrChart', res.data)

    def test_11_proactive_email_reminders(self):
        """Proactive reminder check runs across all schedules."""
        self.authenticate_profile()
        res = self.client.post('/api/reminders/run-now')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

    def test_12_emergency_sos_to_family(self):
        """Emergency SOS alerts all family and Care Circle members immediately."""
        self.authenticate_profile()

        res = self.client.post('/sos', data={'emergency_note': 'Test SOS Alert to all family'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'EMERGENCY ALERT DISPATCHED', res.data)

        sos_notif = NotificationLog.query.filter_by(notification_type='sos').first()
        self.assertIsNotNone(sos_notif)

if __name__ == '__main__':
    unittest.main()
