from datetime import datetime
from flask import Blueprint, request, jsonify
from models import db, Notification, Medicine
from routes.auth import token_required
from services.sns_service import sns_service

notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('', methods=['GET'])
@token_required
def get_notifications(current_user):
    """
    Fetch previous reminders and alerts for the user.
    """
    limit = int(request.args.get('limit', 50))
    notifs = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.sent_at.desc())
        .limit(limit)
        .all()
    )
    return jsonify({
        'notifications': [n.to_dict() for n in notifs]
    }), 200


@notifications_bp.route('/test', methods=['POST'])
@token_required
def trigger_test_reminder(current_user):
    """
    Triggers an immediate test reminder to verify AWS SNS integration.
    """
    data = request.get_json() or {}
    custom_msg = data.get('message')

    first_med = Medicine.query.filter_by(user_id=current_user.id, active=True).first()
    med_name = first_med.medicine_name if first_med else "Daily Multi-Vitamin"
    dosage = first_med.dosage if first_med else "1 Tablet"
    current_time_str = datetime.now().strftime("%I:%M %p")

    message = custom_msg or (
        f"Smart Medicine Test Alert: Hello {current_user.name}! Your reminder service is working. "
        f"Scheduled: {med_name} — {dosage} at {current_time_str}."
    )

    results = {}
    pref = current_user.notification_preference or 'both'
    
    if pref in ['sms', 'both'] and current_user.phone:
        results['sms'] = sns_service.send_sms(current_user.phone, message)
    if pref in ['email', 'both'] and current_user.email:
        results['email'] = sns_service.send_email(
            current_user.email,
            "Smart Medicine Reminder Test",
            message
        )

    # Save to notification history
    notif = Notification(
        user_id=current_user.id,
        medicine_id=first_med.id if first_med else None,
        message=message,
        notification_type='alert',
        status='delivered' if any(r.get('success') for r in results.values()) else 'sent'
    )
    db.session.add(notif)
    db.session.commit()

    return jsonify({
        'message': 'Test reminder dispatched successfully!',
        'delivery_details': results,
        'notification': notif.to_dict()
    }), 200
