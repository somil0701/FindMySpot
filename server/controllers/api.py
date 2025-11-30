from flask import Blueprint, jsonify, current_app
from ..models.lot import ParkingLot
from ..utils.cache import cache_get, cache_set
import json

api_bp = Blueprint('api', __name__)

# TTL for cached results (seconds)
CACHE_TTL = 30  # adjust as desired

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


@api_bp.route('/lots/summary')
def lots_summary():
    """
    Returns lots summary. This is cached in Redis for CACHE_TTL seconds.
    """
    cache_key = "lots:summary"
    data = cache_get(cache_key)
    if data is not None:
        return jsonify({'summary': data})

    lots = ParkingLot.query.all()
    result = []

    for l in lots:
        total = len(l.spots)
        occupied = sum(1 for s in l.spots if s.status == 'O')
        free = total - occupied
        result.append({
            'lot': l.to_dict(),
            'total_spots': total,
            'occupied': occupied,
            'available': free
        })

    cache_set(cache_key, result)
    return jsonify({'summary': result})
