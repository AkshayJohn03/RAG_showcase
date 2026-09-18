"""Edge middleware: API-key auth + per-IP rate limiting (in-memory).

Auth: if API_KEY env is set, /query, /ingest, /eval, /feedback require
X-API-Key header. /health, /metrics, /docs stay open (documented in OPERATIONS.md).
Rate limit: 30 req/min per IP on query endpoints. NOTE: in-memory = per-process;
put a real gateway (Kong/AWS API GW/Cloudflare) in front for multi-replica prod.
"""
from __future__ import annotations
import os
import time
from collections import defaultdict, deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

PROTECTED = ("/query", "/ingest", "/eval", "/feedback")


def _limit() -> int:
    try:
        return int(os.getenv("RATE_LIMIT_PER_MIN", "30"))
    except ValueError:
        return 30


def _client_ip(request: Request) -> str:
    """Real client IP behind proxies — hop-counted from the RIGHT.

    Each proxy appends the socket IP it saw; clients can prepend anything, so
    the leftmost entry is attacker-controlled. With TRUST_PROXY=N (number of
    trusted hops: 1 for a single ingress), take the Nth entry from the right —
    the one YOUR infrastructure appended. Default off: without a proxy in front,
    XFF is pure spoofing surface. (Per-proxy CIDR allowlisting is the stricter
    follow-up; hop-count is the standard proportionate control here.)
    """
    try:
        hops = int(os.getenv("TRUST_PROXY", "0"))
    except ValueError:
        hops = 0
    if hops > 0:
        xff = request.headers.get("X-Forwarded-For", "")
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if len(parts) >= hops:
            return parts[-hops]
        # Fewer hops than configured = request bypassed expected infrastructure
        # (or attacker omitted XFF to reach the X-Real-IP fallback below, which
        # no longer exists). Fall through to the direct socket IP.
    return request.client.host if request.client else "?"

_hits: dict[str, deque] = defaultdict(deque)
MAX_TRACKED_IPS = 10000


def _prune(now: float) -> None:
    """Bound memory: drop quiet IPs; if still huge (botnet scan), drop oldest."""
    for ip in [k for k, w in _hits.items() if not w or now - w[-1] > 60]:
        _hits.pop(ip, None)
    while len(_hits) > MAX_TRACKED_IPS:
        _hits.pop(next(iter(_hits)))


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        key = os.getenv("API_KEY", "")
        if key and any(request.url.path.startswith(p) for p in PROTECTED):
            if request.headers.get("X-API-Key", "") != key:
                return JSONResponse({"detail": "missing or invalid X-API-Key"}, status_code=401)
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if any(request.url.path.startswith(p) for p in ("/query",)):
            ip = _client_ip(request)
            now = time.time()
            window = _hits[ip]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= _limit():
                return JSONResponse({"detail": f"rate limit exceeded ({_limit()}/min)"}, status_code=429)
            window.append(now)
            if len(_hits) % 64 == 0:  # amortized prune, not per-request
                _prune(now)
        return await call_next(request)
