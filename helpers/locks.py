# helpers/locks.py
import os
import logging

logger = logging.getLogger("locks")
logger.setLevel(logging.INFO)

REDIS_URL = os.getenv("REDIS_URL")

# r será None si no hay REDIS_URL o si la inicialización falla.
r = None
if REDIS_URL:
    try:
        import redis
        r = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=5)
    except Exception:
        logger.exception("No se pudo inicializar Redis con REDIS_URL. Continuando sin locks (modo bypass).")
        r = None
else:
    logger.warning("REDIS_URL no configurada: locks funcionarán en modo bypass (sin exclusión).")

def acquire_lock(key: str, ttl: int = 600) -> bool:
    """
    Intenta adquirir un lock. Devuelve True si se adquirió el lock (o si estamos en modo bypass).
    En modo bypass (sin Redis) devolvemos True para no bloquear el flujo de pruebas.
    """
    lock_key = f"lock:{key}"
    if not r:
        logger.debug("acquire_lock bypass for key=%s", key)
        return True
    try:
        return bool(r.set(lock_key, "1", nx=True, ex=ttl))
    except Exception:
        logger.exception("Error al intentar set en Redis; devolviendo False")
        return False

def release_lock(key: str):
    """
    Libera el lock. En modo bypass no hace nada.
    """
    lock_key = f"lock:{key}"
    if not r:
        logger.debug("release_lock bypass for key=%s", key)
        return
    try:
        r.delete(lock_key)
    except Exception:
        logger.exception("Error al liberar lock en Redis para key=%s", key)
