from datetime import datetime, date, timedelta, timezone
from flask import Blueprint, request, jsonify
from models import db, Medicine, MedicineSchedule, MedicineLog, Notification
from routes.auth import token_required
from services.scheduler_service import get_current_local_time

doses_bp = Blueprint('doses', __name__)

@doses_bp.route('/today', methods=['GET'])
@token_required
def get_today_doses(current_user):
    """
    Returns today's doses for the dashboard, along with summary counts
    and next upcoming reminder information.
    """
    now = get_current_local_time()
    today = now.date()
    current_time_str = now.strftime('%H:%M')

    # Ensure all active medicines have logs generated for today
    active_medicines = Medicine.query.filter(
        Medicine.user_id == current_user.id,
        Medicine.active == True,
        Medicine.start_date <= today,
        (Medicine.end_date == None) | (Medicine.end_date >= today)
    ).all()

    for med in active_medicines:
        for sched in med.schedules:
            log = MedicineLog.query.filter_by(
                medicine_id=med.id,
                user_id=current_user.id,
                scheduled_date=today,
                scheduled_time=sched.scheduled_time
            ).first()
            if not log:
                log = MedicineLog(
                    medicine_id=med.id,
                    user_id=current_user.id,
                    scheduled_date=today,
                    scheduled_time=sched.scheduled_time,
                    status='pending'
                )
                db.session.add(log)
    db.session.commit()

    # Query all logs for today
    today_logs = (
        MedicineLog.query.filter_by(user_id=current_user.id, scheduled_date=today)
        .order_by(MedicineLog.scheduled_time.asc())
        .all()
    )

    total_count = len(today_logs)
    taken_count = sum(1 for log in today_logs if log.status == 'taken')
    missed_count = sum(1 for log in today_logs if log.status == 'missed')
    pending_count = sum(1 for log in today_logs if log.status == 'pending')

    # Find the next upcoming reminder
    upcoming_dose = None
    next_time = None
    for log in today_logs:
        if log.status == 'pending' and log.scheduled_time >= current_time_str:
            upcoming_dose = log.to_dict()
            next_time = log.scheduled_time
            break

    # If no pending dose left today, check if there are any pending earlier
    if not upcoming_dose and pending_count > 0:
        for log in today_logs:
            if log.status == 'pending':
                upcoming_dose = log.to_dict()
                next_time = log.scheduled_time
                break

    return jsonify({
        'date': today.isoformat(),
        'current_time': current_time_str,
        'summary': {
            'total': total_count,
            'taken': taken_count,
            'missed': missed_count,
            'pending': pending_count,
            'next_reminder_time': next_time,
            'upcoming_dose': upcoming_dose
        },
        'doses': [l.to_dict() for l in today_logs]
    }), 200


@doses_bp.route('/doses/<int:log_id>/taken', methods=['PUT', 'POST'])
@doses_bp.route('/<int:log_id>/taken', methods=['PUT', 'POST'])
@token_required
def mark_dose_taken(current_user, log_id):
    """
    Mark a scheduled dose as Taken, recording the exact timestamp.
    """
    log = MedicineLog.query.filter_by(id=log_id, user_id=current_user.id).first()
    if not log:
        return jsonify({'error': 'Dose record not found'}), 404

    now = datetime.now()
    log.status = 'taken'
    log.taken_time = now

    # Also record audit notification
    med_name = log.medicine.medicine_name if log.medicine else "Medicine"
    notif = Notification(
        user_id=current_user.id,
        medicine_id=log.medicine_id,
        message=f"Success: Marked {med_name} ({log.scheduled_time}) as Taken.",
        notification_type='alert',
        status='delivered'
    )
    db.session.add(notif)
    db.session.commit()

    return jsonify({
        'message': f'{med_name} marked as Taken!',
        'dose': log.to_dict()
    }), 200


@doses_bp.route('/doses/<int:log_id>/missed', methods=['PUT', 'POST'])
@doses_bp.route('/<int:log_id>/missed', methods=['PUT', 'POST'])
@token_required
def mark_dose_missed(current_user, log_id):
    """
    Manually mark a scheduled dose as Missed.
    """
    log = MedicineLog.query.filter_by(id=log_id, user_id=current_user.id).first()
    if not log:
        return jsonify({'error': 'Dose record not found'}), 404

    log.status = 'missed'
    med_name = log.medicine.medicine_name if log.medicine else "Medicine"

    notif = Notification(
        user_id=current_user.id,
        medicine_id=log.medicine_id,
        message=f"Dose of {med_name} ({log.scheduled_time}) was marked as Missed.",
        notification_type='missed',
        status='delivered'
    )
    db.session.add(notif)
    db.session.commit()

    return jsonify({
        'message': f'{med_name} marked as Missed.',
        'dose': log.to_dict()
    }), 200
