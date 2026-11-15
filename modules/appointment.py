"""
Appointment Management Module for Elderly Care Platform
Handles doctor visits, clinic bookings, transportation coordination, and preparation instructions.
"""

from datetime import datetime, date, timedelta
from modules.models import db, Appointment, ElderlyProfile

def get_upcoming_appointments(profile_id):
    """Retrieves all scheduled appointments from today onwards, sorted chronologically."""
    today_str = datetime.now().strftime('%Y-%m-%d')
    return (
        Appointment.query.filter(
            Appointment.profile_id == profile_id,
            Appointment.appointment_date >= today_str,
            Appointment.status != 'Cancelled'
        )
        .order_by(Appointment.appointment_date.asc(), Appointment.appointment_time.asc())
        .all()
    )

def get_past_appointments(profile_id):
    """Retrieves past or completed appointments."""
    today_str = datetime.now().strftime('%Y-%m-%d')
    return (
        Appointment.query.filter(
            Appointment.profile_id == profile_id,
            (Appointment.appointment_date < today_str) | (Appointment.status.in_(['Completed', 'Cancelled']))
        )
        .order_by(Appointment.appointment_date.desc())
        .all()
    )

def add_appointment(profile_id, doctor_name, specialty, clinic_name, location_address,
                    appointment_date, appointment_time, transport_needed=False,
                    transport_status='Not Needed', accompanying_person="", preparation_notes=""):
    """Creates a new medical appointment."""
    appt = Appointment(
        profile_id=profile_id,
        doctor_name=doctor_name.strip(),
        specialty=specialty.strip(),
        clinic_name=clinic_name.strip(),
        location_address=location_address.strip(),
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        transport_needed=bool(transport_needed),
        transport_status=transport_status,
        accompanying_person=accompanying_person.strip(),
        preparation_notes=preparation_notes.strip(),
        status='Scheduled'
    )
    db.session.add(appt)
    db.session.commit()
    return appt

def update_appointment(appointment_id, **kwargs):
    """Updates fields of an existing appointment."""
    appt = db.session.get(Appointment, appointment_id)
    if not appt:
        return None
    for key, value in kwargs.items():
        if hasattr(appt, key):
            setattr(appt, key, value)
    db.session.commit()
    return appt

def format_relative_appointment_time(appt_date_str, appt_time_str):
    """Returns a friendly relative human string (e.g., 'Tomorrow at 2:00 PM', 'In 3 days')."""
    try:
        dt = datetime.strptime(f"{appt_date_str} {appt_time_str}", "%Y-%m-%d %H:%M")
        now = datetime.now()
        diff = dt - now

        if diff.total_seconds() < 0:
            return "Passed"

        days = diff.days
        hours = int(diff.seconds / 3600)

        if days == 0:
            if hours <= 1:
                return "In less than an hour"
            return f"Today in {hours} hours"
        elif days == 1:
            return f"Tomorrow at {appt_time_str}"
        elif days < 7:
            return f"In {days} days ({dt.strftime('%A')})"
        else:
            return f"On {dt.strftime('%b %d, %Y')}"
    except Exception:
        return f"{appt_date_str} {appt_time_str}"
