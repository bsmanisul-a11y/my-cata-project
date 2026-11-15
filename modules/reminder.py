"""
Automated Proactive Reminder Daemon for Elderly Care Platform
Periodically checks for:
1. Missed medication doses (overdue by >= 30 minutes) -> triggers care circle alert
2. Upcoming medication doses (within 30 minutes) -> triggers reminder
3. Upcoming doctor appointments (24-hour and 2-hour windows) -> triggers transport/prep reminder
"""

import threading
import time
from datetime import datetime, timedelta
from modules.models import db, MedicationLog, Medication, Appointment, ElderlyProfile
from modules.email_notification import notify_missed_dose, notify_upcoming_dose, notify_appointment

_scheduler_running = False

def run_reminder_check(app):
    """
    Executes one comprehensive scan across all profiles for missed meds,
    upcoming doses, and appointments. Can be called manually or via background loop.
    """
    with app.app_context():
        now = datetime.now()
        today_str = now.strftime('%Y-%m-%d')
        current_time_str = now.strftime('%H:%M')
        current_minutes = now.hour * 60 + now.minute

        # 1. CHECK MEDICATION LOGS FOR TODAY
        pending_logs = (
            MedicationLog.query.filter_by(scheduled_date=today_str)
            .filter(MedicationLog.status.in_(['pending', 'missed']))
            .all()
        )

        for log in pending_logs:
            try:
                med_hour, med_min = map(int, log.scheduled_time.split(':'))
                sched_minutes = med_hour * 60 + med_min
                diff_minutes = current_minutes - sched_minutes

                profile = log.medication.profile
                if not profile:
                    continue

                # MISSED DOSE CHECK: >= 30 minutes overdue and not yet notified
                if diff_minutes >= 30 and not log.missed_alert_sent:
                    log.status = 'missed'
                    log.missed_alert_sent = True
                    db.session.commit()
                    print(f"[Proactive Alert] Triggering Missed Dose email for {profile.full_name}: {log.medication.name} (scheduled {log.scheduled_time})")
                    notify_missed_dose(profile, log.medication, log.scheduled_time)

                # UPCOMING DOSE CHECK: Scheduled within next 30 minutes (-30 <= diff <= 0)
                elif -30 <= diff_minutes <= 0 and not log.upcoming_alert_sent:
                    log.upcoming_alert_sent = True
                    db.session.commit()
                    print(f"[Proactive Alert] Triggering Upcoming Dose email for {profile.full_name}: {log.medication.name} (scheduled {log.scheduled_time})")
                    notify_upcoming_dose(profile, log.medication, log.scheduled_time)

            except Exception as e:
                print(f"[Reminder Check Error - Med Log {log.id}]: {e}")

        # 2. CHECK UPCOMING APPOINTMENTS
        upcoming_appts = Appointment.query.filter(
            Appointment.status == 'Scheduled',
            Appointment.appointment_date >= today_str
        ).all()

        for appt in upcoming_appts:
            try:
                appt_dt = datetime.strptime(f"{appt.appointment_date} {appt.appointment_time}", "%Y-%m-%d %H:%M")
                hours_until = (appt_dt - now).total_seconds() / 3600.0

                profile = appt.profile
                if not profile:
                    continue

                # 24-HOUR ADVANCE ALERT (Between 20 and 26 hours away)
                if 20 <= hours_until <= 26 and not appt.reminder_sent_24h:
                    appt.reminder_sent_24h = True
                    db.session.commit()
                    print(f"[Proactive Alert] Triggering 24h Appointment Reminder for {profile.full_name} with Dr. {appt.doctor_name}")
                    notify_appointment(profile, appt, "Tomorrow / 24-Hour Notice")

                # 2-HOUR URGENT ALERT (Between 0 and 2.5 hours away)
                elif 0 <= hours_until <= 2.5 and not appt.reminder_sent_2h:
                    appt.reminder_sent_2h = True
                    db.session.commit()
                    print(f"[Proactive Alert] Triggering 2h Appointment Reminder for {profile.full_name} with Dr. {appt.doctor_name}")
                    notify_appointment(profile, appt, "Today in 2 Hours")

            except Exception as e:
                print(f"[Reminder Check Error - Appointment {appt.id}]: {e}")

def _background_loop(app, interval_seconds=60):
    global _scheduler_running
    print("[Reminder Service] Proactive reminder background worker started.")
    while _scheduler_running:
        try:
            run_reminder_check(app)
        except Exception as e:
            print(f"[Reminder Service Exception]: {e}")
        time.sleep(interval_seconds)

def start_reminder_scheduler(app, interval_seconds=60):
    """Launches the background daemon thread for proactive email monitoring."""
    global _scheduler_running
    if not _scheduler_running:
        _scheduler_running = True
        t = threading.Thread(target=_background_loop, args=(app, interval_seconds), daemon=True)
        t.start()
        return t
    return None
