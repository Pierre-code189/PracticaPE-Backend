"""Limitador ligero en memoria (ventana deslizante) para OTP y rutas sensibles.

Sin dependencias externas: suficiente para una instancia y para las pruebas.
Las claves son por email o por IP, no persistentes entre reinicios.
"""
import threading
import time

_hits: dict[str, list[float]] = {}
_lock = threading.Lock()
_PRUNE_EVERY = 500


def check(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Devuelve (permitido, retry_after_segundos)."""
    now = time.time()
    with _lock:
        bucket = [t for t in _hits.get(key, []) if now - t < window_seconds]
        if len(bucket) >= limit:
            retry = int(window_seconds - (now - bucket[0])) + 1
            _hits[key] = bucket
            return False, max(retry, 1)
        bucket.append(now)
        _hits[key] = bucket
        if len(_hits) > _PRUNE_EVERY:
            for k in list(_hits):
                _hits[k] = [t for t in _hits[k] if now - t < window_seconds]
                if not _hits[k]:
                    _hits.pop(k, None)
    return True, 0


def reset(key: str) -> None:
    with _lock:
        _hits.pop(key, None)
