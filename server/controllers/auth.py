from flask import Blueprint, request, jsonify
from ..models import db
from ..models.user import User
import jwt, datetime, os

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/debug/whoami', methods=['GET'])
def debug_whoami():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({'error': 'missing token in Authorization header'}), 400
    token = auth.split(' ',1)[1]
    try:
        # decode WITHOUT verifying signature so we can inspect expiry/payload
        payload = jwt.decode(token, options={"verify_signature": False})
        return jsonify({'decoded': payload}), 200
    except Exception as e:
        return jsonify({'error': 'decode_failed', 'msg': str(e)}), 400

def create_token(user):
    payload = {
        'sub': user.id,
        'username': user.username,
        'role': user.role,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    token = jwt.encode(payload, os.environ.get('SECRET_KEY', 'devkey'), algorithm='HS256')
    return token

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({'error': 'missing fields'}), 400

    if User.query.filter((User.username == username) | (User.email == email)).first():
        return jsonify({'error': 'user exists'}), 400

    u = User(username=username, email=email)
    u.set_password(password)

    db.session.add(u)
    db.session.commit()

    token = create_token(u)
    return jsonify({'message': 'registered', 'token': token, 'user': u.to_dict()}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'missing fields'}), 400

    user = User.query.filter((User.username == username) | (User.email == username)).first()

    if not user or not user.check_password(password):
        return jsonify({'error': 'invalid credentials'}), 401

    token = create_token(user)
    return jsonify({'message': 'ok', 'token': token, 'user': user.to_dict()}), 200
