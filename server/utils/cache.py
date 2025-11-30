# server/utils/cache.py
import json
from flask import current_app

DEFAULT_TTL = 30  # seconds

def _get_redis():
    r = getattr(current_app, 'redis', None)
    return r

def cache_get(key):
    r = _get_redis()
    if not r:
        current_app.logger.debug("[CACHE] redis not configured; cache_get skip %s", key)
        return None
    try:
        val = r.get(key)
        if val is None:
            current_app.logger.debug("[CACHE] MISS %s", key)
            return None
        current_app.logger.debug("[CACHE] HIT %s", key)
        return json.loads(val)
    except Exception as e:
        current_app.logger.exception("Redis get error for key=%s: %s", key, e)
        return None

def cache_set(key, value, ttl=DEFAULT_TTL):
    r = _get_redis()
    if not r:
        current_app.logger.debug("[CACHE] redis not configured; cache_set skip %s", key)
        return
    try:
        r.set(key, json.dumps(value), ex=ttl)
        current_app.logger.debug("[CACHE] SET %s ttl=%s", key, ttl)
    except Exception as e:
        current_app.logger.exception("Redis set error for key=%s: %s", key, e)

def cache_delete(*keys):
    r = _get_redis()
    if not r:
        current_app.logger.debug("[CACHE] redis not configured; cache_delete skip %s", keys)
        return
    try:
        for k in keys:
            r.delete(k)
            current_app.logger.debug("[CACHE] DEL %s", k)
    except Exception as e:
        current_app.logger.exception("Redis del error: %s", e)
