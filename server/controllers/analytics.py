# server/controllers/analytics.py
from flask import Blueprint, jsonify, request, current_app
from ._auth_utils import token_required
from ..models.lot import ParkingLot
from ..models.spot import ParkingSpot
from ..models.reservation import Reservation
from ..models.user import User
from ..models import db
from datetime import datetime, timedelta
from sqlalchemy import func

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/summary', methods=['GET'])
@token_required
def analytics_summary():
    """
    Admin-only analytics summary:
    - total_revenue (sum of Reservation.cost)
    - revenue_per_lot: list of {lot_id, lot_name, revenue}
    - occupancy: per-lot occupancy (occupied, total)
    - reservations_last_30_days: list of {date, count}
    - recent_reservations: last 20 reservations (enriched)
    """
    user = getattr(request, 'current_user', None)
    if not user or user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403

    try:
        now = datetime.utcnow()
        days = 30
        start_date = (now - timedelta(days=days-1)).replace(hour=0, minute=0, second=0, microsecond=0)

        # total revenue (only include reservations with non-null cost)
        total_revenue = db.session.query(func.coalesce(func.sum(Reservation.cost), 0.0)).scalar() or 0.0

        # revenue per lot: join reservations -> spots -> lots
        rev_q = db.session.query(
            ParkingLot.id.label('lot_id'),
            ParkingLot.name.label('lot_name'),
            func.coalesce(func.sum(Reservation.cost), 0.0).label('revenue')
        ).join(ParkingSpot, ParkingSpot.lot_id == ParkingLot.id) \
         .join(Reservation, Reservation.spot_id == ParkingSpot.id) \
         .group_by(ParkingLot.id).order_by(func.coalesce(func.sum(Reservation.cost), 0.0).desc())

        revenue_per_lot = []
        for r in rev_q:
            revenue_per_lot.append({
                'lot_id': r.lot_id,
                'lot_name': r.lot_name,
                'revenue': float(r.revenue or 0.0)
            })

        # occupancy per lot (current)
        lots = ParkingLot.query.all()
        occupancy = []
        for l in lots:
            total = len(l.spots)
            occupied = sum(1 for s in l.spots if s.status == 'O')
            occupancy.append({
                'lot_id': l.id,
                'lot_name': l.name,
                'total_spots': total,
                'occupied': occupied,
                'available': total - occupied
            })

        # reservations per day in last N days
        daily_counts = []
        # group by date (UTC) using SQL function
        day_counts_q = db.session.query(
            func.date(Reservation.start_time).label('d'),
            func.count(Reservation.id).label('cnt')
        ).filter(Reservation.start_time >= start_date) \
         .group_by(func.date(Reservation.start_time)).all()

        # map date -> count
        day_map = {str(row.d): int(row.cnt) for row in day_counts_q}

        for i in range(days):
            d = (start_date + timedelta(days=i)).date()
            daily_counts.append({'date': d.isoformat(), 'count': int(day_map.get(d.isoformat(), 0))})

        # recent reservations (last 20, enriched)
        recent_q = Reservation.query.order_by(Reservation.start_time.desc()).limit(20).all()
        recent = []
        for r in recent_q:
            spot = ParkingSpot.query.get(r.spot_id) if r.spot_id else None
            lot = ParkingLot.query.get(spot.lot_id) if spot and getattr(spot, 'lot_id', None) else None
            user_obj = User.query.get(r.user_id)
            recent.append({
                'id': r.id,
                'user': {'id': getattr(user_obj, 'id', None), 'username': getattr(user_obj, 'username', None)},
                'lot': {'id': getattr(lot, 'id', None), 'name': getattr(lot, 'name', None)},
                'spot_number': getattr(spot, 'number', None),
                'start_time': r.start_time.isoformat() if r.start_time else None,
                'end_time': r.end_time.isoformat() if r.end_time else None,
                'cost': float(r.cost or 0.0),
                'notes': getattr(r, 'notes', None)
            })

        payload = {
            'total_revenue': float(total_revenue),
            'revenue_per_lot': revenue_per_lot,
            'occupancy': occupancy,
            'reservations_last_30_days': daily_counts,
            'recent_reservations': recent
        }

        return jsonify(payload)
    except Exception as e:
        current_app.logger.exception("Analytics error: %s", e)
        return jsonify({'error': 'internal', 'message': str(e)}), 500
