# server/controllers/user.py
from flask import current_app
import traceback
from flask import Blueprint, request, jsonify
from ._auth_utils import token_required
from ..models import db
from ..models.spot import ParkingSpot
from ..models.reservation import Reservation
from ..models.lot import ParkingLot
from datetime import datetime
from ..utils.cache import cache_delete, cache_set, cache_get
import math

user_bp = Blueprint('user', __name__)

@user_bp.route('/reserve', methods=['POST'])
@token_required
def reserve():
    """
    Reserve the first available spot in the given lot for the current user.

    Safety:
    - Prevent user from having multiple active reservations.
    - Atomically mark a spot as occupied using an UPDATE ... WHERE status='A'
      to avoid double-booking in concurrent requests.
    """
    from datetime import datetime
    import time

    user = getattr(request, 'current_user')
    data = request.get_json() or {}
    lot_id = data.get('lot_id')
    notes = data.get('notes')  # optional notes provided by user

    # basic validations
    try:
        lot_id = int(lot_id)
    except Exception:
        return jsonify({'error': 'invalid lot_id'}), 400

    lot = ParkingLot.query.get(lot_id)
    if not lot:
        return jsonify({'error': 'lot not found'}), 404

    # 1) prevent user from having an active reservation already
    active = Reservation.query.filter_by(user_id=user.id, end_time=None).first()
    if active:
        return jsonify({'error': 'user already has an active reservation', 'reservation_id': active.id}), 400

    # 2) attempt to find the first available spot and reserve it atomically
    # We'll try a few times to handle races where another process updates the spot status between select and update.
    max_attempts = 3
    attempt = 0
    chosen_spot = None
    while attempt < max_attempts:
        attempt += 1
        # choose the first available spot deterministically (order by id)
        spot = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').order_by(ParkingSpot.id).first()
        if not spot:
            # no available spots
            return jsonify({'error': 'no spots available'}), 400

        # optimistic atomic update: only set status to 'O' if currently 'A'
        updated = ParkingSpot.query.filter_by(id=spot.id, status='A').update({'status': 'O'})
        if updated == 1:
            # we successfully claimed the spot
            chosen_spot = ParkingSpot.query.get(spot.id)  # reload
            break
        else:
            # another worker/process claimed it — retry a bit
            # small sleep to reduce hot-looping under heavy concurrency
            time.sleep(0.05)

    if not chosen_spot:
        return jsonify({'error': 'no spots available (concurrent conflicts)'}), 400

    # create reservation tied to the claimed spot
    try:
        reservation = Reservation(
            user_id=user.id,
            spot_id=chosen_spot.id,
            start_time=datetime.utcnow(),
            notes=notes
        )
        db.session.add(reservation)
        db.session.commit()
        # invalidate caches affected: lots summary and this lot's spots + analytics
        try:
            cache_delete("lots:summary", f"lot:{lot_id}:spots", "analytics:summary", f"user:{user.id}:reservations")
        except Exception:
            pass

    except Exception as e:
        # rollback and restore spot status if reservation creation failed
        db.session.rollback()
        try:
            ParkingSpot.query.filter_by(id=chosen_spot.id).update({'status': 'A'})
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({'error': 'failed to create reservation', 'message': str(e)}), 500

    return jsonify({'reservation': reservation.to_dict(), 'spot': chosen_spot.to_dict()}), 201

@user_bp.route('/release', methods=['POST'])
@token_required
def release():
    """
    Release (end) a reservation.

    Behavior:
    - Sets reservation.end_time to current UTC time if not already set (unless recalculate-only).
    - Computes cost using the lot.price_per_hour:
        cost = ceil(duration_seconds / 3600) * price_per_hour
    - Stores cost on reservation (if not present or if recalculate=True).
    - Marks spot.status = 'A' (available).
    - Returns reservation data and computed cost and hours used.

    Optional request body:
      {
        "reservation_id": <int>,          # required
        "notes": "<string>",              # optional - appended to reservation.notes
        "recalculate": true|false         # optional - if true, recompute cost even if already present
      }
    """
    from datetime import datetime
    import math

    data = request.get_json() or {}
    reservation_id = data.get('reservation_id')
    release_notes = data.get('notes')
    recalc_flag = bool(data.get('recalculate', False))

    # validate
    if not reservation_id:
        return jsonify({'error': 'missing reservation_id'}), 400

    try:
        reservation_id = int(reservation_id)
    except Exception:
        return jsonify({'error': 'invalid reservation_id'}), 400

    # load reservation
    res = Reservation.query.get(reservation_id)
    if not res:
        return jsonify({'error': 'reservation not found'}), 404

    # permission: user must be owner or admin
    current = getattr(request, 'current_user', None)
    if not current:
        return jsonify({'error': 'unauthenticated'}), 401
    if current.role != 'admin' and res.user_id != current.id:
        return jsonify({'error': 'forbidden'}), 403

    # If already released and recalc_flag is False, return current state and cost
    already_released = bool(res.end_time)
    if already_released and not recalc_flag:
        return jsonify({'reservation': res.to_dict(), 'cost': getattr(res, 'cost', None), 'message': 'already released'}), 200

    # set end_time if not already set
    if not res.end_time:
        res.end_time = datetime.utcnow()

    # append release notes if provided
    if release_notes:
        existing = res.notes or ""
        if existing:
            res.notes = existing + "\n" + release_notes
        else:
            res.notes = release_notes

    # find spot & lot
    try:
        spot = ParkingSpot.query.get(res.spot_id) if res.spot_id else None
    except Exception:
        spot = None

    lot = None
    if spot and getattr(spot, "lot_id", None):
        lot = ParkingLot.query.get(spot.lot_id)

    # compute duration_seconds and cost
    duration_seconds = None
    computed_cost = None
    hours_charged = None
    try:
        if res.start_time and res.end_time:
            duration_seconds = int((res.end_time - res.start_time).total_seconds())
            # round up to next whole hour
            hours_charged = math.ceil(max(0, duration_seconds) / 3600.0)
            price = float(getattr(lot, 'price_per_hour', 0.0) or 0.0)
            computed_cost = hours_charged * price
        else:
            # If timestamps missing, keep None
            duration_seconds = None
            hours_charged = None
            computed_cost = None
    except Exception as e:
        # fallback to None
        duration_seconds = None
        hours_charged = None
        computed_cost = None

    # decide whether to write cost to reservation:
    # - If reservation has no cost, or recalc_flag == True, update it.
    try:
        if computed_cost is not None and (getattr(res, 'cost', None) is None or recalc_flag):
            res.cost = float(computed_cost)
    except Exception:
        pass

    # mark spot available
    try:
        if spot:
            spot.status = 'A'
    except Exception:
        pass

    # commit changes
    try:
        db.session.commit()
        lot_id = getattr(lot, 'id', None)
        try:
            keys = ["lots:summary", "analytics:summary", f"user:{res.user_id}:reservations"]
            if lot_id:
                keys.append(f"lot:{lot_id}:spots")
            cache_delete(*keys)
        except Exception:
            pass
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'failed to save release', 'message': str(e)}), 500

    # Build response
    resp = {
        'reservation': res.to_dict(),
        'cost': getattr(res, 'cost', None),
        'duration_seconds': duration_seconds,
        'hours_charged': hours_charged,
        'lot_price_per_hour': getattr(lot, 'price_per_hour', None)
    }

    return jsonify(resp), 200


@user_bp.route('/reservations/<int:user_id>', methods=['GET', 'OPTIONS'])
@token_required
def reservations(user_id):
    cache_key = f"user:{user_id}:reservations"
    cached = cache_get(cache_key)
    if cached is not None:
        return jsonify({'reservations': cached})
    try:
        current = getattr(request, 'current_user', None)
        current_app.logger.debug(f"[DEBUG] reservations called. requester: {getattr(current,'id', None)} username: {getattr(current,'username', None)} target_user_id: {user_id}")

        if request.method == 'OPTIONS':
            return jsonify({}), 200

        if not current:
            current_app.logger.warning("[WARN] token_required did not set current_user")
            return jsonify({'error': 'unauthenticated'}), 401

        if current.id != user_id and current.role != 'admin':
            return jsonify({'error': 'forbidden'}), 403

        resvs = Reservation.query.filter_by(user_id=user_id).order_by(Reservation.start_time.desc()).all()

        out = []
        for r in resvs:
            # build enriched dict with spot/lot and durations
            spot = ParkingSpot.query.get(r.spot_id) if r.spot_id else None
            lot = ParkingLot.query.get(spot.lot_id) if (spot and getattr(spot, "lot_id", None)) else None

            # canonical fields returned to frontend
            rd = {
                'id': r.id,
                'user_id': r.user_id,
                'spot_id': r.spot_id,
                'spot_number': getattr(spot, "number", None),
                'lot_id': getattr(lot, "id", None),
                'lot_name': getattr(lot, "name", None),
                'start_time': r.start_time.isoformat() if r.start_time else None,
                'end_time': r.end_time.isoformat() if r.end_time else None,
                'cost': getattr(r, 'cost', None),
                'remarks': getattr(r, 'notes', None)
            }

            # compute duration_seconds if end_time exists
            duration_seconds = None
            try:
                if r.start_time and r.end_time:
                    duration_seconds = int((r.end_time - r.start_time).total_seconds())
                    rd['duration_seconds'] = duration_seconds
                else:
                    # optionally provide current duration for active reservations:
                    # uncomment next lines if you want live duration for active rows
                    # if r.start_time and not r.end_time:
                    #     duration_seconds_now = int((datetime.utcnow() - r.start_time).total_seconds())
                    #     rd['duration_seconds_current'] = duration_seconds_now
                    rd['duration_seconds'] = None
            except Exception:
                rd['duration_seconds'] = None

            out.append(rd)

        cache_set(cache_key, out, ttl=30)
        return jsonify({'reservations': out})

    except Exception as e:
        tb = traceback.format_exc()
        current_app.logger.error("Unhandled exception in /user/reservations: %s\n%s", e, tb)
        return jsonify({'error': 'internal', 'message': str(e), 'traceback': tb.splitlines()[-20:]}), 500

@user_bp.route('/history', methods=['GET'])
@token_required
def history():
    """
    Return reservation history for the currently authenticated user.
    Enriched with spot.number, lot.id/name, duration_seconds, cost and notes.
    """
    try:
        current = getattr(request, 'current_user', None)
        if not current:
            return jsonify({'error': 'unauthenticated'}), 401

        resvs = Reservation.query.filter_by(user_id=current.id).order_by(Reservation.start_time.desc()).all()

        out = []
        for r in resvs:
            spot = ParkingSpot.query.get(r.spot_id) if r.spot_id else None
            lot = ParkingLot.query.get(spot.lot_id) if (spot and getattr(spot, "lot_id", None)) else None

            duration_seconds = None
            try:
                if r.start_time and r.end_time:
                    duration_seconds = int((r.end_time - r.start_time).total_seconds())
            except Exception:
                duration_seconds = None

            out.append({
                'id': r.id,
                'start_time': r.start_time.isoformat() if r.start_time else None,
                'end_time': r.end_time.isoformat() if r.end_time else None,
                'duration_seconds': duration_seconds,
                'cost': getattr(r, 'cost', None),
                'notes': getattr(r, 'notes', None),
                'spot_id': getattr(spot, 'id', None),
                'spot_number': getattr(spot, 'number', None),
                'lot': {
                    'id': getattr(lot, 'id', None),
                    'name': getattr(lot, 'name', None),
                    'price_per_hour': getattr(lot, 'price_per_hour', None)
                } if lot else None
            })

        return jsonify({'user': {'id': current.id, 'username': current.username, 'email': current.email}, 'reservations': out}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'internal', 'message': str(e)}), 500
