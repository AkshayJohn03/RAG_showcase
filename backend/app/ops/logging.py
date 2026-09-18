"""Structured JSON logging + request-ID middleware (stdlib only, no new deps)."""
from __future__ import annotations
import json
import logging
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                   "level": record.levelname.lower(), "msg": record.getMessage()}
        for k in ("req_id", "method", "path", "status", "ms"):
            if hasattr(record, k):
                payload[k] = getattr(record, k)
        return json.dumps(payload)


def setup_logging() -> logging.Logger:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("rag")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


logger = setup_logging()


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        t0 = time.perf_counter()
        response = await call_next(request)
        ms = round((time.perf_counter() - t0) * 1000)
        response.headers["X-Request-ID"] = req_id
        logger.info("request", extra={"req_id": req_id, "method": request.method,
                                      "path": request.url.path, "status": response.status_code, "ms": ms})
        try:
            from backend.app.ops.metrics import observe
            observe(request.url.path, response.status_code, ms)
        except Exception:
            pass
        return response
