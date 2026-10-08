from datetime import datetime, date
from flask import Blueprint, request, jsonify
from models import db, Medicine, MedicineSchedule, MedicineLog
from routes.auth import token_required

medicines_bp = Blueprint('medicines', __name__)

@medicines_bp.route('', methods=['GET'])
@token_required
def get_medicines(current_user):
    """Fetch all medicines for the current authenticated user."""
    medicines = Medicine.query.filter_by(user_id=current_user.id).order_by(Medicine.created_at.desc()).all()
    return jsonify({'medicines': [m.to_dict() for m in medicines]}), 200


@medicines_bp.route('/<int:med_id>', methods=['GET'])
@token_required
def get_medicine(current_user, med_id):
    medicine = Medicine.query.filter_by(id=med_id, user_id=current_user.id).first()
    if not medicine:
        return jsonify({'error': 'Medicine not found'}), 404
    return jsonify({'medicine': medicine.to_dict()}), 200


@medicines_bp.route('', methods=['POST'])
@token_required
def add_medicine(current_user):
    """
    Create a new medicine with multiple scheduled dose timings.
    """
    data = request.get_json() or {}
    med_name = data.get('medicine_name', '').strip()
    dosage = data.get('dosage', '').strip()
    med_type = data.get('medicine_type', 'Tablet').strip()
    quantity = int(data.get('quantity', 30))
    instructions = data.get('instructions', 'After Food').strip()
    start_date_str = data.get('start_date')
    end_date_str = data.get('end_date')
    schedules_data = data.get('schedules', []) # list of {'scheduled_time': '08:00', 'reminder_method': 'both'}

    if not med_name or not dosage:
        return jsonify({'error': 'Medicine Name and Dosage are required fields.'}), 400

    if not schedules_data:
        return jsonify({'error': 'At least one scheduled dosage time is required.'}), 400

    # Parse dates
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else date.today()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400

    if end_date and end_date < start_date:
        return jsonify({'error': 'End date cannot be earlier than start date.'}), 400

    try:
        medicine = Medicine(
            user_id=current_user.id,
            medicine_name=med_name,
            medicine_type=med_type,
            dosage=dosage,
            quantity=quantity,
            instructions=instructions,
            start_date=start_date,
            end_date=end_date,
            active=data.get('active', True)
        )
        db.session.add(medicine)
        db.session.flush() # obtain medicine.id

        today = date.today()
        # Add schedules
        for item in schedules_data:
            time_val = item.get('scheduled_time') if isinstance(item, dict) else str(item)
            rem_method = item.get('reminder_method', current_user.notification_preference or 'both') if isinstance(item, dict) else 'both'
            
            # Basic validation of HH:MM
            time_parts = time_val.strip().split(':')
            if len(time_parts) != 2:
                continue
            formatted_time = f"{int(time_parts[0]):02d}:{int(time_parts[1]):02d}"

            schedule = MedicineSchedule(
                medicine_id=medicine.id,
                scheduled_time=formatted_time,
                reminder_method=rem_method
            )
            db.session.add(schedule)

            # Pre-populate today's log if medicine is active and valid for today
            if medicine.active and start_date <= today and (end_date is None or end_date >= today):
                existing_log = MedicineLog.query.filter_by(
                    medicine_id=medicine.id,
                    user_id=current_user.id,
                    scheduled_date=today,
                    scheduled_time=formatted_time
                ).first()
                if not existing_log:
                    today_log = MedicineLog(
                        medicine_id=medicine.id,
                        user_id=current_user.id,
                        scheduled_date=today,
                        scheduled_time=formatted_time,
                        status='pending'
                    )
                    db.session.add(today_log)

        db.session.commit()
        return jsonify({
            'message': 'Medicine and schedules added successfully!',
            'medicine': medicine.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to add medicine: {str(e)}'}), 500


@medicines_bp.route('/<int:med_id>', methods=['PUT'])
@token_required
def update_medicine(current_user, med_id):
    medicine = Medicine.query.filter_by(id=med_id, user_id=current_user.id).first()
    if not medicine:
        return jsonify({'error': 'Medicine not found'}), 404

    data = request.get_json() or {}
    if 'medicine_name' in data:
        medicine.medicine_name = data['medicine_name'].strip()
    if 'medicine_type' in data:
        medicine.medicine_type = data['medicine_type'].strip()
    if 'dosage' in data:
        medicine.dosage = data['dosage'].strip()
    if 'quantity' in data:
        medicine.quantity = int(data['quantity'])
    if 'instructions' in data:
        medicine.instructions = data['instructions'].strip()
    if 'active' in data:
        medicine.active = bool(data['active'])

    if 'start_date' in data and data['start_date']:
        medicine.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
    if 'end_date' in data:
        medicine.end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date() if data['end_date'] else None

    # Replace schedules if provided
    if 'schedules' in data:
        # Clear existing schedules
        MedicineSchedule.query.filter_by(medicine_id=medicine.id).delete()
        schedules_data = data['schedules']
        for item in schedules_data:
            time_val = item.get('scheduled_time') if isinstance(item, dict) else str(item)
            rem_method = item.get('reminder_method', current_user.notification_preference or 'both') if isinstance(item, dict) else 'both'
            time_parts = time_val.strip().split(':')
            if len(time_parts) != 2:
                continue
            formatted_time = f"{int(time_parts[0]):02d}:{int(time_parts[1]):02d}"

            schedule = MedicineSchedule(
                medicine_id=medicine.id,
                scheduled_time=formatted_time,
                reminder_method=rem_method
            )
            db.session.add(schedule)

    try:
        db.session.commit()
        return jsonify({
            'message': 'Medicine updated successfully!',
            'medicine': medicine.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update medicine: {str(e)}'}), 500


@medicines_bp.route('/<int:med_id>/toggle', methods=['PATCH'])
@token_required
def toggle_medicine_status(current_user, med_id):
    medicine = Medicine.query.filter_by(id=med_id, user_id=current_user.id).first()
    if not medicine:
        return jsonify({'error': 'Medicine not found'}), 404

    medicine.active = not medicine.active
    db.session.commit()
    return jsonify({
        'message': f"Medicine marked as {'Active' if medicine.active else 'Inactive'}",
        'active': medicine.active
    }), 200


@medicines_bp.route('/<int:med_id>', methods=['DELETE'])
@token_required
def delete_medicine(current_user, med_id):
    medicine = Medicine.query.filter_by(id=med_id, user_id=current_user.id).first()
    if not medicine:
        return jsonify({'error': 'Medicine not found'}), 404

    try:
        db.session.delete(medicine)
        db.session.commit()
        return jsonify({'message': 'Medicine deleted successfully.'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete medicine: {str(e)}'}), 500
