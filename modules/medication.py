"""
Medication Management Module for Elderly Care Platform
Handles schedule management, daily pillbox generation, adherence logging & analytics,
stock tracking, and interaction safety checks.
"""

from datetime import datetime, date, timedelta, timezone
from modules.models import db, Medication, MedicationSchedule, MedicationLog, ElderlyProfile
from modules.safety import check_drug_interactions, get_medication_advice
from modules.email_notification import notify_low_refill

def get_profile_medications(profile_id, active_only=True):
    """Retrieves all medications for a profile."""
    query = Medication.query.filter_by(profile_id=profile_id)
    if active_only:
        query = query.filter_by(is_active=True)
    return query.order_by(Medication.name.asc()).all()

def add_medication(profile_id, name, dosage, form="Pill", color_shape="White Round",
                   instructions="", purpose="", prescribing_doctor="", stock=30,
                   refill_threshold=7, schedule_times=None):
    """
    Creates a new medication with associated daily schedule slots.
    schedule_times is a list of dicts: [{'time_slot': 'Morning', 'time': '08:00', 'days': 'Daily'}]
    """
    med = Medication(
        profile_id=profile_id,
        name=name.strip(),
        dosage=dosage.strip(),
        form=form,
        color_shape=color_shape,
        instructions=instructions.strip() or get_medication_advice(name),
        purpose=purpose.strip(),
        prescribing_doctor=prescribing_doctor.strip(),
        current_stock=int(stock),
        refill_threshold=int(refill_threshold),
        is_active=True
    )
    db.session.add(med)
    db.session.flush()

    # Add schedule times
    if schedule_times:
        for item in schedule_times:
            sched = MedicationSchedule(
                medication_id=med.id,
                time_slot=item.get('time_slot', 'Morning'),
                scheduled_time=item.get('time', '08:00'),
                days_of_week=item.get('days', 'Daily')
            )
            db.session.add(sched)
    else:
        # Default morning schedule
        sched = MedicationSchedule(
            medication_id=med.id,
            time_slot='Morning',
            scheduled_time='08:00',
            days_of_week='Daily'
        )
        db.session.add(sched)

    db.session.commit()
    # Populate today's log entry right away
    ensure_daily_logs_for_profile(profile_id, datetime.now().strftime('%Y-%m-%d'))
    return med

def ensure_daily_logs_for_profile(profile_id, target_date_str=None):
    """
    Ensures that for target_date_str (defaults to today), every active medication
    schedule has a corresponding MedicationLog row.
    """
    if not target_date_str:
        target_date_str = datetime.now().strftime('%Y-%m-%d')

    meds = Medication.query.filter_by(profile_id=profile_id, is_active=True).all()
    for med in meds:
        for sched in med.schedules:
            # Check if log already exists
            existing = MedicationLog.query.filter_by(
                medication_id=med.id,
                schedule_id=sched.id,
                scheduled_date=target_date_str
            ).first()

            if not existing:
                new_log = MedicationLog(
                    medication_id=med.id,
                    schedule_id=sched.id,
                    profile_id=profile_id,
                    scheduled_date=target_date_str,
                    scheduled_time=sched.scheduled_time,
                    status='pending'
                )
                db.session.add(new_log)
    db.session.commit()

def record_dose_action(log_id, action, actor_name="Elderly User", notes=""):
    """
    Records an action ('taken', 'skipped', 'snoozed') on a medication log.
    If 'taken', decrements medication stock and triggers refill check.
    """
    log = db.session.get(MedicationLog, log_id)
    if not log:
        return None, "Log not found"

    prev_status = log.status
    log.status = action
    log.logged_at = datetime.now(timezone.utc)
    log.logged_by_name = actor_name
    if notes:
        log.notes = notes

    med = log.medication
    # If transitioning to 'taken' from non-taken, decrement stock
    if action == 'taken' and prev_status != 'taken':
        if med.current_stock > 0:
            med.current_stock -= 1
            if med.current_stock <= med.refill_threshold:
                # Dispatch refill warning
                try:
                    notify_low_refill(med.profile, med)
                except Exception as e:
                    print(f"Refill notification error: {e}")

    # If undoing a 'taken' status, restore stock
    elif prev_status == 'taken' and action != 'taken':
        med.current_stock += 1

    db.session.commit()
    return log, "Success"

def get_today_pillbox(profile_id):
    """
    Organizes today's medication logs into standard pillbox compartments:
    Morning, Afternoon, Evening, Bedtime.
    """
    today_str = datetime.now().strftime('%Y-%m-%d')
    ensure_daily_logs_for_profile(profile_id, today_str)

    logs = (
        MedicationLog.query.filter_by(profile_id=profile_id, scheduled_date=today_str)
        .join(Medication)
        .order_by(MedicationLog.scheduled_time.asc())
        .all()
    )

    pillbox = {
        'Morning': {'icon': '🌅', 'label': 'Morning', 'time_hint': '6:00 AM - 11:59 AM', 'doses': []},
        'Afternoon': {'icon': '☀️', 'label': 'Afternoon', 'time_hint': '12:00 PM - 4:59 PM', 'doses': []},
        'Evening': {'icon': '🌆', 'label': 'Evening', 'time_hint': '5:00 PM - 8:59 PM', 'doses': []},
        'Bedtime': {'icon': '🌙', 'label': 'Night / Bedtime', 'time_hint': '9:00 PM onwards', 'doses': []}
    }

    for log in logs:
        slot = 'Morning'
        if log.schedule and log.schedule.time_slot in pillbox:
            slot = log.schedule.time_slot
        else:
            # Categorize by hour
            try:
                hour = int(log.scheduled_time.split(':')[0])
                if hour < 12:
                    slot = 'Morning'
                elif hour < 17:
                    slot = 'Afternoon'
                elif hour < 21:
                    slot = 'Evening'
                else:
                    slot = 'Bedtime'
            except Exception:
                slot = 'Morning'

        pillbox[slot]['doses'].append({
            'log_id': log.id,
            'med_id': log.medication.id,
            'name': log.medication.name,
            'dosage': log.medication.dosage,
            'form': log.medication.form,
            'color_shape': log.medication.color_shape,
            'instructions': log.medication.instructions,
            'scheduled_time': log.scheduled_time,
            'status': log.status,
            'logged_at': log.logged_at.strftime('%H:%M') if log.logged_at else None,
            'logged_by': log.logged_by_name,
            'stock': log.medication.current_stock
        })

    return pillbox

def calculate_adherence_stats(profile_id):
    """
    Computes real-time adherence rates:
    - Today's adherence %
    - 7-day adherence %
    - 30-day adherence %
    - Current consecutive adherence streak (days)
    - Total doses taken, missed, skipped
    """
    today = date.today()
    today_str = today.strftime('%Y-%m-%d')
    seven_days_ago_str = (today - timedelta(days=7)).strftime('%Y-%m-%d')
    thirty_days_ago_str = (today - timedelta(days=30)).strftime('%Y-%m-%d')

    # Today
    today_logs = MedicationLog.query.filter(
        MedicationLog.profile_id == profile_id,
        MedicationLog.scheduled_date == today_str
    ).all()
    today_total = len(today_logs)
    today_taken = sum(1 for l in today_logs if l.status == 'taken')
    today_rate = int((today_taken / today_total * 100)) if today_total > 0 else 100

    # 7 Days
    logs_7d = MedicationLog.query.filter(
        MedicationLog.profile_id == profile_id,
        MedicationLog.scheduled_date >= seven_days_ago_str,
        MedicationLog.scheduled_date <= today_str
    ).all()
    total_7d = len(logs_7d)
    taken_7d = sum(1 for l in logs_7d if l.status == 'taken')
    rate_7d = int((taken_7d / total_7d * 100)) if total_7d > 0 else 100

    # 30 Days
    logs_30d = MedicationLog.query.filter(
        MedicationLog.profile_id == profile_id,
        MedicationLog.scheduled_date >= thirty_days_ago_str,
        MedicationLog.scheduled_date <= today_str
    ).all()
    total_30d = len(logs_30d)
    taken_30d = sum(1 for l in logs_30d if l.status == 'taken')
    missed_30d = sum(1 for l in logs_30d if l.status == 'missed')
    skipped_30d = sum(1 for l in logs_30d if l.status == 'skipped')
    rate_30d = int((taken_30d / total_30d * 100)) if total_30d > 0 else 100

    # Calculate streak (working backwards day-by-day)
    streak = 0
    curr_date = today - timedelta(days=1)
    for _ in range(60):
        d_str = curr_date.strftime('%Y-%m-%d')
        d_logs = MedicationLog.query.filter_by(profile_id=profile_id, scheduled_date=d_str).all()
        if not d_logs:
            break
        all_taken = all(l.status == 'taken' for l in d_logs)
        if all_taken:
            streak += 1
            curr_date -= timedelta(days=1)
        else:
            break

    # If today is complete, add 1 to streak
    if today_total > 0 and today_taken == today_total:
        streak += 1

    return {
        'today_rate': today_rate,
        'today_taken': today_taken,
        'today_total': today_total,
        'rate_7d': rate_7d,
        'rate_30d': rate_30d,
        'total_30d': total_30d,
        'taken_30d': taken_30d,
        'missed_30d': missed_30d,
        'skipped_30d': skipped_30d,
        'streak': streak
    }

def analyze_profile_drug_safety(profile_id):
    """Evaluates all active medications against the clinical interaction engine."""
    meds = Medication.query.filter_by(profile_id=profile_id, is_active=True).all()
    med_names = [m.name for m in meds]
    return check_drug_interactions(med_names)
