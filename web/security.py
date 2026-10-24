import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

CSRF_COOKIE = "ug_csrf"
SESSION_COOKIE = "ug_session"
SESSION_SECONDS = 8 * 60 * 60

PAGE_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                               "frame-ancestors 'none'; form-action 'self'; base-uri 'none'; object-src 'none'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cache-Control": "no-store",
}

REPORT_POLICY = "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


def add_security_headers(response, is_report=False):
    for name, value in PAGE_HEADERS.items():
        response.headers[name] = value
    if is_report:
        response.headers["Content-Security-Policy"] = REPORT_POLICY
    return response


def new_csrf_token():
    return secrets.token_urlsafe(32)


def csrf_matches(cookie_value, form_value):
    if not cookie_value or not form_value:
        return False
    return hmac.compare_digest(cookie_value.encode(), form_value.encode())


def same_origin(headers):
    origin = headers.get("Origin") or headers.get("Referer")
    if not origin:
        return True
    return urlparse(origin).netloc == headers.get("Host", "")


class RateLimiter:
    def __init__(self, limit, window_seconds):
        self.limit = limit
        self.window_seconds = window_seconds
        self.hits = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key, now=None):
        now = time.time() if now is None else now
        with self.lock:
            recent = self.hits[key]
            while recent and recent[0] <= now - self.window_seconds:
                recent.popleft()
            if len(recent) >= self.limit:
                return False
            recent.append(now)
            return True


class AccessGate:
    def __init__(self, access_token, secret):
        self.access_token = access_token
        self.secret = secret.encode()

    @property
    def enabled(self):
        return bool(self.access_token)

    def token_is_valid(self, supplied):
        if not self.enabled or not supplied:
            return False
        return hmac.compare_digest(supplied.encode(), self.access_token.encode())

    def make_session(self, now=None):
        expires = str(int((time.time() if now is None else now) + SESSION_SECONDS))
        return "%s.%s" % (expires, self.sign(expires))

    def session_is_valid(self, cookie_value, now=None):
        if not cookie_value or "." not in cookie_value:
            return False
        expires, signature = cookie_value.split(".", 1)
        if not expires.isdigit() or int(expires) < (time.time() if now is None else now):
            return False
        return hmac.compare_digest(signature, self.sign(expires))

    def sign(self, text):
        return hmac.new(self.secret, text.encode(), hashlib.sha256).hexdigest()


def is_loopback(host):
    return host in ("127.0.0.1", "localhost", "::1")
