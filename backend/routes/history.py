from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify
from models import db, MedicineLog, Medicine
from routes.auth import token_required
from services.scheduler_service import get_current_local_time

history_bp = Blueprint('history', __name__)

@history_bp.route('', methods=['GET'])
@token_required
def get_history(current_user):
    """
    Fetch historical medicine doses with date filtering and adherence statistics.
    Filters: today, yesterday, 7days, 30days, all (default: 7days)
    """
    filter_type = request.args.get('filter', '7days').lower()
    now = get_current_local_time()
    today = now.date()

    query = MedicineLog.query.filter_by(user_id=current_user.id)

    if filter_type == 'today':
        query = query.filter(MedicineLog.scheduled_date == today)
    elif filter_type == 'yesterday':
        yesterday = today - timedelta(days=1)
        query = query.filter(MedicineLog.scheduled_date == yesterday)
    elif filter_type == '7days':
        start_7d = today - timedelta(days=7)
        query = query.filter(MedicineLog.scheduled_date >= start_7d, MedicineLog.scheduled_date <= today)
    elif filter_type == '30days':
        start_30d = today - timedelta(days=30)
        query = query.filter(MedicineLog.scheduled_date >= start_30d, MedicineLog.scheduled_date <= today)
    # 'all' has no date restrictions

    logs = query.order_by(MedicineLog.scheduled_date.desc(), MedicineLog.scheduled_time.desc()).all()

    total_doses = len(logs)
    taken_doses = sum(1 for l in logs if l.status == 'taken')
    missed_doses = sum(1 for l in logs if l.status == 'missed')
    pending_doses = sum(1 for l in logs if l.status == 'pending')

    completed_doses = taken_doses + missed_doses
    if completed_doses > 0:
        adherence_percentage = round((taken_doses / completed_doses) * 100, 1)
    elif total_doses > 0:
        adherence_percentage = 100.0 if taken_doses > 0 else 0.0
    else:
        adherence_percentage = 100.0

    return jsonify({
        'filter': filter_type,
        'statistics': {
            'total_doses': total_doses,
            'taken_doses': taken_doses,
            'missed_doses': missed_doses,
            'pending_doses': pending_doses,
            'adherence_percentage': adherence_percentage
        },
        'logs': [l.to_dict() for l in logs]
    }), 200
