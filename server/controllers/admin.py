from flask import Blueprint, request, jsonify, current_app
from ..models import db
from ..models.lot import ParkingLot
from ..models.spot import ParkingSpot
from ..models.user import User
from ..models.reservation import Reservation
from ._auth_utils import token_required
import json

admin_bp = Blueprint('admin', __name__)

# short TTL for cache (seconds)
CACHE_TTL = 30

def _cache_get(key):
    r = getattr(current_app, 'redis', None)
    if not r:
        print(f"[CACHE] redis not configured; skip GET {key}")
        return None
    try:
        val = r.get(key)
        if val is None:
            current_app.logger.info("Cache MISS for key=%s", key)
            print(f"[CACHE] MISS {key}")
            return None
        current_app.logger.info("Cache HIT for key=%s", key)
        print(f"[CACHE] HIT {key}")
        return json.loads(val)
    except Exception as e:
        current_app.logger.info("Redis get error for key=%s: %s", key, e)
        print(f"[CACHE] GET ERROR {key}: {e}")
        return None

def _cache_set(key, value, ttl=CACHE_TTL):
    r = getattr(current_app, 'redis', None)
    if not r:
        print(f"[CACHE] redis not configured; skip SET {key}")
        return
    try:
        r.set(key, json.dumps(value), ex=ttl)
        current_app.logger.info("Cache SET for key=%s (ttl=%s)", key, ttl)
        print(f"[CACHE] SET {key} ttl={ttl}")
    except Exception as e:
        current_app.logger.info("Redis set error for key=%s: %s", key, e)
        print(f"[CACHE] SET ERROR {key}: {e}")

def _cache_delete(*keys):
    r = getattr(current_app, 'redis', None)
    if not r:
        print(f"[CACHE] redis not configured; skip DEL {keys}")
        return
    try:
        for k in keys:
            r.delete(k)
            current_app.logger.info("Cache DEL key=%s", k)
            print(f"[CACHE] DEL {k}")
    except Exception as e:
        current_app.logger.info("Redis del error: %s", e)
        print(f"[CACHE] DEL ERROR: {e}")


@admin_bp.route('/lots', methods=['POST'])
@token_required
def create_lot():
    user = getattr(request, 'current_user')
    if user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403

    data = request.get_json() or {}
    name = data.get('name')
    address = data.get('address')
    capacity = int(data.get('capacity', 0))
    price = float(data.get('price_per_hour', 0))

    lot = ParkingLot(name=name, address=address, capacity=capacity, price_per_hour=price)
    db.session.add(lot)
    db.session.flush()

    for i in range(1, capacity + 1):
        spot = ParkingSpot(lot_id=lot.id, number=str(i), status='A')
        db.session.add(spot)

    db.session.commit()

    # invalidate lots summary cache
    _cache_delete("lots:summary")

    return jsonify({'lot': lot.to_dict()}), 201

@admin_bp.route('/lots/<int:lot_id>', methods=['DELETE'])
@token_required
def delete_lot(lot_id):
    user = getattr(request, 'current_user')
    if user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403

    lot = ParkingLot.query.get_or_404(lot_id)
    occupied = any(s.status == 'O' for s in lot.spots)
    if occupied:
        return jsonify({'error': 'cannot delete: some spots are occupied'}), 400

    db.session.delete(lot)
    db.session.commit()

    # invalidate caches
    _cache_delete("lots:summary", f"lot:{lot_id}:spots")

    return jsonify({'message': 'deleted'}), 200

@admin_bp.route('/lots', methods=['GET'])
@token_required
def list_lots():
    user = getattr(request, 'current_user')
    if user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    lots = ParkingLot.query.all()
    return jsonify({'lots': [l.to_dict() for l in lots]})

@admin_bp.route('/lots/<int:lot_id>', methods=['PUT'])
@token_required
def edit_lot(lot_id):
    user = getattr(request, 'current_user')
    if user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403

    data = request.get_json() or {}
    lot = ParkingLot.query.get(lot_id)
    if not lot:
        return jsonify({'error': 'lot not found'}), 404

    if 'name' in data:
        lot.name = data['name']
    if 'address' in data:
        lot.address = data['address']
    if 'price_per_hour' in data:
        try:
            lot.price_per_hour = float(data['price_per_hour'])
        except:
            pass

    if 'capacity' in data:
        try:
            new_capacity = int(data['capacity'])
            if new_capacity < 0:
                raise ValueError()
        except:
            return jsonify({'error': 'invalid capacity'}), 400

        old_capacity = lot.capacity or 0
        if new_capacity == old_capacity:
            pass
        elif new_capacity > old_capacity:
            max_number = 0
            if lot.spots:
                try:
                    nums = [int(s.number) for s in lot.spots if str(s.number).isdigit()]
                    max_number = max(nums) if nums else 0
                except:
                    max_number = len(lot.spots)
            to_add = new_capacity - old_capacity
            for i in range(1, to_add + 1):
                sp = ParkingSpot(lot_id=lot.id, number=str(max_number + i), status='A')
                db.session.add(sp)
            lot.capacity = new_capacity
        else:
            to_remove = old_capacity - new_capacity
            avail_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='A').order_by(ParkingSpot.id.desc()).limit(to_remove).all()
            if len(avail_spots) < to_remove:
                return jsonify({'error': 'cannot decrease capacity: not enough available (free) spots to delete'}), 400
            for sp in avail_spots:
                db.session.delete(sp)
            lot.capacity = new_capacity

    db.session.commit()

    # invalidate caches for lots summary and this lot's spots
    _cache_delete("lots:summary", f"lot:{lot_id}:spots")

    return jsonify({'success': True, 'lot': lot.to_dict()})

@admin_bp.route('/lots/<int:lot_id>/spots', methods=['GET'])
@token_required
def lot_spots(lot_id):
    """
    Returns spots for a lot with enriched current reservation metadata:
    - reservation_id
    - user {id, username, email}
    - start_time (ISO)
    - end_time (ISO or None)
    - duration_seconds (int or None)
    - cost (if ended) or estimated_cost (if active)
    - notes
    """
    try:
        from datetime import datetime
        import math

        user = getattr(request, 'current_user')
        if user.role != 'admin':
            return jsonify({'error': 'forbidden'}), 403

        lot = ParkingLot.query.get(lot_id)
        if not lot:
            return jsonify({'error': 'lot not found'}), 404

        spots = ParkingSpot.query.filter_by(lot_id=lot.id).order_by(ParkingSpot.number.asc()).all()
        out = []
        for s in spots:
            item = {'id': s.id, 'number': s.number, 'status': s.status}
            if s.status == 'O':
                # find the active reservation (end_time is None) or most recent reservation
                res = Reservation.query.filter_by(spot_id=s.id).order_by(Reservation.start_time.desc()).first()
                # prefer the reservation that's currently active (end_time is None)
                if res and res.end_time is not None:
                    # try to find a truly active one
                    active = Reservation.query.filter_by(spot_id=s.id, end_time=None).order_by(Reservation.start_time.desc()).first()
                    if active:
                        res = active

                if res:
                    # user info
                    u = User.query.get(res.user_id) if res.user_id else None

                    # compute duration and cost
                    duration_seconds = None
                    est_cost = None
                    final_cost = getattr(res, 'cost', None)
                    try:
                        if res.start_time and res.end_time:
                            duration_seconds = int((res.end_time - res.start_time).total_seconds())
                        elif res.start_time and not res.end_time:
                            duration_seconds = int((datetime.utcnow() - res.start_time).total_seconds())
                    except Exception:
                        duration_seconds = None

                    # compute estimated cost for active reservation if lot price is available
                    try:
                        if res.end_time is None:
                            # ceil to hours
                            hrs = math.ceil((duration_seconds or 0) / 3600.0)
                            price = float(getattr(lot, 'price_per_hour', 0) or 0)
                            est_cost = hrs * price
                    except Exception:
                        est_cost = None

                    item['current_reservation'] = {
                        'reservation_id': res.id,
                        'user': {'id': u.id, 'username': u.username, 'email': u.email} if u else None,
                        'start_time': res.start_time.isoformat() if res.start_time else None,
                        'end_time': res.end_time.isoformat() if res.end_time else None,
                        'duration_seconds': duration_seconds,
                        # if reservation ended, return recorded cost; otherwise return estimated cost
                        'cost': final_cost if (res.end_time is not None and final_cost is not None) else None,
                        'estimated_cost': est_cost,
                        'notes': getattr(res, 'notes', None)
                    }

            out.append(item)

        return jsonify({'spots': out, 'lot': {'id': lot.id, 'name': lot.name, 'capacity': lot.capacity, 'price_per_hour': lot.price_per_hour}})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'internal', 'message': str(e)}), 500


@admin_bp.route('/users', methods=['GET'])
@token_required
def admin_list_users():
    user = getattr(request, 'current_user')
    if user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    users = User.query.order_by(User.created_at.desc()).all()
    out = []
    for u in users:
        out.append({
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'role': u.role,
            'created_at': u.created_at.isoformat() if u.created_at else None
        })
    return jsonify({'users': out})

@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@token_required
def admin_delete_user(user_id):
    """
    Delete a user (admin-only).
    Safety checks:
      - only admin can call
      - cannot delete users with active reservations (end_time is None)
      - cannot delete user with role 'admin'
      - cannot delete yourself (current admin)
    On success returns: {'message': 'deleted'}
    """
    try:
        current = getattr(request, 'current_user', None)
        if not current or current.role != 'admin':
            return jsonify({'error': 'forbidden'}), 403

        # cannot delete self
        if current.id == user_id:
            return jsonify({'error': 'cannot_delete_self'}), 400

        target = User.query.get(user_id)
        if not target:
            return jsonify({'error': 'user_not_found'}), 404

        # prevent deleting another admin
        if getattr(target, 'role', None) == 'admin':
            return jsonify({'error': 'cannot_delete_admin'}), 400

        # check for active reservations
        active_count = Reservation.query.filter_by(user_id=user_id, end_time=None).count()
        if active_count and active_count > 0:
            return jsonify({'error': 'cannot_delete_active_reservations', 'message': 'user has active reservation(s)'}), 400

        # delete user's reservations/history first (if you prefer to keep history, skip this)
        try:
            Reservation.query.filter_by(user_id=user_id).delete()
        except Exception:
            # ignore - we'll still attempt to delete user record
            pass

        db.session.delete(target)
        db.session.commit()

        # invalidate any caches that may include user data (optional)
        try:
            _cache_delete("lots:summary")
        except Exception:
            pass

        return jsonify({'message': 'deleted'}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Failed to delete user %s: %s", user_id, e)
        return jsonify({'error': 'delete_failed', 'message': str(e)}), 500


@admin_bp.route('/users/<int:user_id>/reservations', methods=['GET'])
@token_required
def admin_user_reservations(user_id):
    """
    Return all reservations for a specific user.
    Enriched with spot and lot details, duration (seconds), cost and notes.
    Admin-only endpoint.
    """
    try:
        user = getattr(request, 'current_user')
        if user.role != 'admin':
            return jsonify({'error': 'forbidden'}), 403

        # ensure target user exists
        target_user = User.query.get(user_id)
        if not target_user:
            return jsonify({'error': 'user not found'}), 404

        # fetch reservations (most recent first)
        resv_q = Reservation.query.filter_by(user_id=user_id).order_by(Reservation.start_time.desc()).all()

        out = []
        for r in resv_q:
            # get spot and lot (may be None)
            spot = ParkingSpot.query.get(r.spot_id) if r.spot_id else None
            lot = ParkingLot.query.get(spot.lot_id) if (spot and getattr(spot, "lot_id", None)) else None

            # compute duration_seconds if both timestamps present
            duration_seconds = None
            try:
                if r.start_time and r.end_time:
                    duration_seconds = int((r.end_time - r.start_time).total_seconds())
            except Exception:
                duration_seconds = None

            out.append({
                'id': r.id,
                'user_id': r.user_id,
                'start_time': r.start_time.isoformat() if r.start_time else None,
                'end_time': r.end_time.isoformat() if r.end_time else None,
                'duration_seconds': duration_seconds,
                'cost': getattr(r, 'cost', None),
                'notes': getattr(r, 'notes', None),

                # spot info
                'spot_id': getattr(spot, 'id', None),
                'spot_number': getattr(spot, 'number', None),
                'spot_status': getattr(spot, 'status', None),

                # lot info (nested)
                'lot': {
                    'id': getattr(lot, 'id', None),
                    'name': getattr(lot, 'name', None),
                    'address': getattr(lot, 'address', None),
                    'price_per_hour': getattr(lot, 'price_per_hour', None)
                } if lot else None
            })

        return jsonify({'user': {'id': target_user.id, 'username': target_user.username, 'email': target_user.email}, 'reservations': out}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'internal', 'message': str(e)}), 500



@admin_bp.route('/lots/<int:lot_id>/spots/<int:spot_id>', methods=['PUT'])
@token_required
def edit_spot(lot_id, spot_id):
    user = getattr(request, 'current_user')
    if user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    data = request.get_json() or {}
    sp = ParkingSpot.query.filter_by(id=spot_id, lot_id=lot_id).first_or_404()
    if 'status' in data:
        if data['status'] in ('A','O'):
            sp.status = data['status']
    if 'number' in data:
        sp.number = str(data['number'])
    db.session.commit()

    # invalidate cache for this lot's spots
    _cache_delete("lots:summary", f"lot:{lot_id}:spots")

    return jsonify({'spot': sp.to_dict()})

@admin_bp.route('/generate-monthly-reports-now', methods=['POST'])
@token_required
def generate_monthly_reports_now():
    """
    Admin-only endpoint to immediately enqueue the 'enqueue_monthly_reports'
    Celery job which will create monthly_report_task for every user.

    Returns:
      202 + {"task_id": "<celery-task-id>"} on success.
      500 if Celery/tasks module isn't available.
    """
    user = getattr(request, 'current_user', None)
    if not user or user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403

    try:
        # import inside function to avoid circular imports at module import time
        from server.tasks.tasks import enqueue_monthly_reports
    except Exception as e:
        current_app.logger.exception("Failed to import Celery tasks: %s", e)
        return jsonify({'error': 'tasks_unavailable', 'message': str(e)}), 500

    try:
        job = enqueue_monthly_reports.delay()
    except Exception as e:
        current_app.logger.exception("Failed to enqueue monthly reports: %s", e)
        return jsonify({'error': 'enqueue_failed', 'message': str(e)}), 500

    return jsonify({'message': 'enqueued', 'task_id': job.id}), 202

@admin_bp.route('/run-daily-reminder-now', methods=['POST'])
@token_required
def run_daily_reminder_now():
    """
    Admin-only endpoint to enqueue the send_daily_reminder Celery task.

    Optional JSON body:
      { "cutoff_days": 7 }

    Returns:
      202 + {"task_id": "<celery-task-id>", "cutoff_days": N}
    """
    user = getattr(request, 'current_user', None)
    if not user or user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403

    try:
        # import lazily to avoid circular imports
        from server.tasks.tasks import send_daily_reminder
    except Exception as e:
        current_app.logger.exception("Failed to import Celery tasks for daily reminder: %s", e)
        return jsonify({'error': 'tasks_unavailable', 'message': str(e)}), 500

    # default cutoff is 7 days, but allow override via JSON
    cutoff_days = 7
    try:
        if request.is_json:
            body = request.get_json(silent=True) or {}
            if 'cutoff_days' in body:
                cutoff_days = int(body['cutoff_days'])
    except Exception:
        cutoff_days = 7

    try:
        job = send_daily_reminder.delay(cutoff_days)
    except Exception as e:
        current_app.logger.exception("Failed to enqueue daily reminder: %s", e)
        return jsonify({'error': 'enqueue_failed', 'message': str(e)}), 500

    return jsonify({'message': 'enqueued',
                    'task_id': job.id,
                    'cutoff_days': cutoff_days}), 202

# Add this to server/controllers/admin.py (place near other admin endpoints)
@admin_bp.route('/send-daily-reminder', methods=['POST'])
@token_required
def send_daily_reminder_now():
    """
    Admin endpoint to enqueue send_daily_reminder Celery task.
    Expects optional JSON body: { "cutoff_days": <int> } - number of days of inactivity cutoff.
    Returns: 202 + {"task_id": "<celery-task-id>"}
    """
    user = getattr(request, 'current_user', None)
    if not user or user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403

    data = request.get_json() or {}
    cutoff_days = int(data.get('cutoff_days', 7))

    try:
        # import lazily
        from server.tasks.tasks import send_daily_reminder
    except Exception as e:
        current_app.logger.exception("Failed to import send_daily_reminder task: %s", e)
        return jsonify({'error': 'tasks_unavailable', 'message': str(e)}), 500

    try:
        job = send_daily_reminder.delay(cutoff_days)
    except Exception as e:
        current_app.logger.exception("Failed to enqueue daily reminder: %s", e)
        return jsonify({'error': 'enqueue_failed', 'message': str(e)}), 500

    return jsonify({'message': 'enqueued', 'task_id': job.id}), 202
