"""Limitadores en memoria: OTP por email e IP, intake anti-duplicado."""
import time
from collections import defaultdict, deque


class Limiter:
    def __init__(self):
        self._otp_email = defaultdict(deque)
        self._otp_ip = defaultdict(deque)
        self._intake = defaultdict(float)

    def _trim(self, dq, window):
        now = time.time()
        while dq and dq[0] < now - window:
            dq.popleft()

    def otp_email(self, key: str, limit: int, window_min: int) -> tuple:
        dq = self._otp_email[key]
        self._trim(dq, window_min * 60)
        if len(dq) >= limit:
            return False, int(dq[0] + window_min * 60 - time.time()) + 1
        dq.append(time.time())
        return True, 0

    def otp_ip(self, key: str, limit: int, window_min: int) -> tuple:
        dq = self._otp_ip[key]
        self._trim(dq, window_min * 60)
        if len(dq) >= limit:
            return False, int(dq[0] + window_min * 60 - time.time()) + 1
        dq.append(time.time())
        return True, 0

    def intake(self, key: str, cooldown: int = 60) -> bool:
        now = time.time()
        if now - self._intake.get(key, 0) < cooldown:
            return False
        self._intake[key] = now
        return True

    def reset(self, prefix: str = ""):
        if not prefix:
            self._otp_email.clear(); self._otp_ip.clear(); self._intake.clear()
        else:
            for d in (self._otp_email, self._otp_ip, self._intake):
                for k in [k for k in d if k.startswith(prefix)]:
                    del d[k]


limiter = Limiter()
