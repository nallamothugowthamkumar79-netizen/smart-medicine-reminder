import functools
import jwt
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app
from models import db, User
from config import Config

auth_bp = Blueprint('auth', __name__)

def token_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'error': 'Authorization token is missing'}), 401
        
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return jsonify({'error': 'Invalid Authorization header format. Expected: Bearer <token>'}), 401
        
        token = parts[1]
        try:
            payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
            user_id = int(payload.get('sub'))
            current_user = db.session.get(User, user_id)
            if not current_user:
                return jsonify({'error': 'User not found or account deactivated'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Session expired. Please log in again.'}), 401
        except jwt.InvalidTokenError as err:
            return jsonify({'error': f'Invalid or corrupted session token: {str(err)}'}), 401
        except Exception as e:
            return jsonify({'error': f'Authentication error: {str(e)}'}), 401

        return f(current_user, *args, **kwargs)
    return decorated


def generate_token(user_id):
    now_utc = datetime.now(timezone.utc)
    payload = {
        'sub': str(user_id),
        'iat': now_utc,
        'exp': now_utc + Config.JWT_ACCESS_TOKEN_EXPIRES
    }
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm='HS256')


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')
    notification_pref = data.get('notification_preference', 'both')

    if not name or not email or not password:
        return jsonify({'error': 'Full Name, Email, and Password are required.'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters long.'}), 400

    if confirm_password and password != confirm_password:
        return jsonify({'error': 'Passwords do not match.'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'An account with this email already exists.'}), 409

    try:
        user = User(
            name=name,
            email=email,
            phone=phone,
            notification_preference=notification_pref
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        token = generate_token(user.id)
        return jsonify({
            'message': 'Account registered successfully!',
            'token': token,
            'user': user.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Please provide both email and password.'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid email address or password.'}), 401

    token = generate_token(user.id)
    return jsonify({
        'message': 'Login successful!',
        'token': token,
        'user': user.to_dict()
    }), 200


@auth_bp.route('/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    return jsonify({'user': current_user.to_dict()}), 200


@auth_bp.route('/profile', methods=['PUT'])
@token_required
def update_profile(current_user):
    data = request.get_json() or {}
    
    if 'name' in data and data['name'].strip():
        current_user.name = data['name'].strip()
    if 'phone' in data:
        current_user.phone = data['phone'].strip()
    if 'notification_preference' in data:
        pref = data['notification_preference'].lower()
        if pref in ['email', 'sms', 'both']:
            current_user.notification_preference = pref
            
    if 'password' in data and data['password']:
        if len(data['password']) < 6:
            return jsonify({'error': 'New password must be at least 6 characters.'}), 400
        current_user.set_password(data['password'])

    try:
        db.session.commit()
        return jsonify({
            'message': 'Profile updated successfully!',
            'user': current_user.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Update failed: {str(e)}'}), 500
