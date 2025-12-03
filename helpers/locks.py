# helpers/locks.py
import os
import redis

REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise RuntimeError("REDIS_URL not set in env")
r = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=5)

def acquire_lock(key, ttl=600):
    lock_key = f"lock:{key}"
    return r.set(lock_key, "1", nx=True, ex=ttl)

def release_lock(key):
    lock_key = f"lock:{key}"
    try:
        r.delete(lock_key)
    except Exception:
        pass
