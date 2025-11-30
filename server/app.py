from flask import Flask, jsonify, request, make_response
from .config import Config
from .models import db
from .models.user import User
from .models.lot import ParkingLot
from .models.spot import ParkingSpot
from .models.reservation import Reservation
from .controllers.auth import auth_bp
from .controllers.admin import admin_bp
from .controllers.user import user_bp
from .controllers.api import api_bp
from .controllers.export import export_bp
from flask_cors import CORS
import os
from sqlalchemy.exc import IntegrityError
import traceback
import logging

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.logger.setLevel(logging.DEBUG)
    logging.getLogger('werkzeug').setLevel(logging.DEBUG)

    # Development-friendly
    app.config['DEBUG'] = True
    app.config['PROPAGATE_EXCEPTIONS'] = True

    # Robust CORS config. In dev allow localhost origin(s).
    CORS(app,
         resources={r"/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173", "*"]}},
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization", "Access-Control-Allow-Origin", "Access-Control-Allow-Headers"],
         expose_headers=["Content-Type", "Authorization"])

    db.init_app(app)

    try:
        import redis as _redis
        redis_url = app.config.get('REDIS_URL')
        if redis_url:
            # decode_responses -> return strings instead of bytes
            app.redis = _redis.from_url(redis_url, decode_responses=True, socket_timeout=5)
            app.logger.info("Redis client initialized from %s", redis_url)
            # also print for immediate console visibility
            print(f"[APP] Redis initialized: {redis_url}")
        else:
            app.redis = None
            app.logger.warning("REDIS_URL not set; caching disabled.")
            print("[APP] REDIS_URL not set; caching disabled.")
    except Exception as e:
        app.redis = None
        app.logger.exception("Failed to initialize Redis client: %s", e)
        print("[APP] Failed to initialize Redis:", e)

    # register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(export_bp, url_prefix='/export')

    # analytics (admin)
    try:
        from .controllers.analytics import analytics_bp
        app.register_blueprint(analytics_bp, url_prefix='/admin/analytics')
    except Exception as e:
        app.logger.warning("Failed to register analytics blueprint: %s", e)

    @app.route('/ping')
    def ping():
        return jsonify({'status': 'ok'})

    # ensure CORS headers are present on every response (fallback)
    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get('Origin')
        if origin:
            response.headers.setdefault('Access-Control-Allow-Origin', origin)
            response.headers.setdefault('Access-Control-Allow-Credentials', 'true')
            response.headers.setdefault('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            response.headers.setdefault('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
        return response

    # dev error handler: returns JSON and logs traceback
    @app.errorhandler(Exception)
    def handle_exception(e):
        tb = traceback.format_exc()
        app.logger.error("Unhandled Exception: %s\n%s", e, tb)
        payload = {
            'error': 'internal_server_error',
            'message': str(e),
            # include a small slice of the traceback for debugging
            'traceback': tb.splitlines()[-20:]
        }
        resp = make_response(jsonify(payload), 500)
        origin = request.headers.get('Origin')
        if origin:
            resp.headers['Access-Control-Allow-Origin'] = origin
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
        return resp

    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
        # create admin if not present (safe)
        if not User.query.filter_by(username='admin').first() and not User.query.filter_by(email='root@parking.local').first():
            try:
                u = User(username='admin', email='root@parking.local', role='admin')
                u.set_password('admin')
                db.session.add(u)
                db.session.commit()
                print('Created admin user with password admin')
            except IntegrityError:
                db.session.rollback()
    # bind to 0.0.0.0 to be reachable from localhost / other hosts
    app.run(host='0.0.0.0', port=5001, debug=True)