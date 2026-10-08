from datetime import datetime, date, time
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    notification_preference = db.Column(db.String(20), default='both')  # 'email', 'sms', 'both'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    medicines = db.relationship('Medicine', backref='user', lazy=True, cascade='all, delete-orphan')
    logs = db.relationship('MedicineLog', backref='user', lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'notification_preference': self.notification_preference,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Medicine(db.Model):
    __tablename__ = 'medicines'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    medicine_name = db.Column(db.String(150), nullable=False)
    medicine_type = db.Column(db.String(50), default='Tablet')  # 'Tablet', 'Capsule', 'Syrup', 'Injection', 'Other'
    dosage = db.Column(db.String(80), nullable=False)          # e.g., '1 Tablet', '500mg', '10ml'
    quantity = db.Column(db.Integer, default=30)
    instructions = db.Column(db.String(100), default='After Food')  # 'Before Food', 'After Food', 'With Food', 'Other'
    start_date = db.Column(db.Date, nullable=False, default=date.today)
    end_date = db.Column(db.Date, nullable=True)
    active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    schedules = db.relationship('MedicineSchedule', backref='medicine', lazy='joined', cascade='all, delete-orphan')
    logs = db.relationship('MedicineLog', backref='medicine', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'medicine_name': self.medicine_name,
            'medicine_type': self.medicine_type,
            'dosage': self.dosage,
            'quantity': self.quantity,
            'instructions': self.instructions,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'schedules': [s.to_dict() for s in self.schedules]
        }


class MedicineSchedule(db.Model):
    __tablename__ = 'medicine_schedules'

    id = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id', ondelete='CASCADE'), nullable=False, index=True)
    scheduled_time = db.Column(db.String(5), nullable=False)  # HH:MM format (24hr), e.g. "08:00", "13:30", "20:00"
    reminder_method = db.Column(db.String(20), default='both') # 'email', 'sms', 'both'

    def to_dict(self):
        return {
            'id': self.id,
            'medicine_id': self.medicine_id,
            'scheduled_time': self.scheduled_time,
            'reminder_method': self.reminder_method
        }


class MedicineLog(db.Model):
    __tablename__ = 'medicine_logs'

    id = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    scheduled_date = db.Column(db.Date, nullable=False, index=True)
    scheduled_time = db.Column(db.String(5), nullable=False)
    taken_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='pending', index=True) # 'pending', 'taken', 'missed'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'medicine_id': self.medicine_id,
            'medicine_name': self.medicine.medicine_name if self.medicine else 'Unknown Medicine',
            'medicine_type': self.medicine.medicine_type if self.medicine else 'Tablet',
            'dosage': self.medicine.dosage if self.medicine else '',
            'instructions': self.medicine.instructions if self.medicine else '',
            'user_id': self.user_id,
            'scheduled_date': self.scheduled_date.isoformat() if self.scheduled_date else None,
            'scheduled_time': self.scheduled_time,
            'taken_time': self.taken_time.isoformat() if self.taken_time else None,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id', ondelete='SET NULL'), nullable=True)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), default='reminder')  # 'reminder', 'missed', 'alert', 'system'
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='sent')                  # 'sent', 'delivered', 'failed', 'simulated'

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'medicine_id': self.medicine_id,
            'message': self.message,
            'notification_type': self.notification_type,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'status': self.status
        }
