from functools import wraps
from flask import request, jsonify, make_response
import jwt, os
from ..models.user import User

def token_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        # Allow preflight OPTIONS to proceed without token
        if request.method == 'OPTIONS':
            return make_response(('', 200))

        auth = request.headers.get('Authorization', '')
        if not auth or not auth.startswith('Bearer '):
            return jsonify({'error': 'missing token'}), 401

        token = auth.split(' ', 1)[1]

        try:
            data = jwt.decode(
                token,
                os.environ.get('SECRET_KEY', 'devkey'),
                algorithms=['HS256']
            )
            user = User.query.get(data['sub'])
            if not user:
                return jsonify({'error': 'invalid token'}), 401
            request.current_user = user
        except Exception as e:
            return jsonify({'error': 'invalid token', 'msg': str(e)}), 401

        return f(*args, **kwargs)
    return wrapper
