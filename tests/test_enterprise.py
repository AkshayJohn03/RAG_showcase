"""Enterprise layer tests: sessions, feedback/history stores, metrics, edge middleware."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_session_memory_capped():
    from backend.app.ops import sessions
    sessions._sessions.clear()
    for i in range(10):
        sessions.remember("s1", f"q{i}", f"a{i}")
    assert len(sessions.recall("s1")) == sessions.TURNS_KEPT
    assert sessions.recall("s1")[-1]["q"] == "q9"


def test_feedback_stats_with_tmp(monkeypatch, tmp_path):
    import backend.app.eval.history as h
    monkeypatch.setattr(h, "FEED", tmp_path / "feedback.jsonl")
    h.record_feedback("sess", "q?", "up")
    h.record_feedback("sess", "q?", "down")
    assert h.feedback_stats() == {"up": 1, "down": 1}


def test_history_roundtrip_with_tmp(monkeypatch, tmp_path):
    import backend.app.eval.history as h
    monkeypatch.setattr(h, "HIST", tmp_path / "history.jsonl")
    h.record_eval({"gate": "PASS", "faith": 1.0}, strategy="parent_child")
    rows = h.read_history()
    assert len(rows) == 1 and rows[0]["summary"]["gate"] == "PASS"


def test_metrics_exposition():
    from backend.app.ops.metrics import observe, exposition, set_gauge
    observe("/query", 200, 120)
    set_gauge("chunks_indexed", 10)
    out = exposition()
    assert 'rag_requests_total{route="/query",status="200"}' in out
    assert "rag_request_ms_p95" in out


def test_tracing_disabled_without_keys(monkeypatch):
    import backend.app.ops.tracing as tr
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    tr._client = None
    assert tr.enabled() is False
    with tr.trace_query("q", "hello") as t:
        with t.span("embed", input="x"):
            pass
        t.score("faithfulness", 1.0)
        assert t.url() is None and t.trace_id() is None


def test_answer_cache_hit_and_expiry():
    from backend.app.retrieval.cache import answer_key, answer_get, answer_set, _ACACHE
    _ACACHE.clear()
    key = answer_key("Hello?", 10, True, True)
    assert answer_get(key) is None
    answer_set(key, {"answer": "hi"})
    hit = answer_get(key)
    assert hit and hit["answer"] == "hi" and hit["cached"] is True
    # expiry
    import backend.app.retrieval.cache as c
    ts, res = _ACACHE[key]
    _ACACHE[key] = (ts - c.ACACHE_TTL_S - 1, res)
    assert answer_get(key) is None


def test_auth_and_rate_limit_middleware(monkeypatch):
    import os
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient
    from backend.app.ops.middleware import AuthMiddleware, RateLimitMiddleware, _hits
    from backend.app.ops.logging import RequestIdMiddleware

    async def ok(request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/query", ok, methods=["POST"])])
    # SAME order as main.py (added inside-out: Auth executes before RateLimit,
    # so rejected calls never consume budget)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(RequestIdMiddleware)
    _hits.clear()
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "2")
    c = TestClient(app, raise_server_exceptions=False)
    r401 = c.post("/query")
    assert r401.status_code == 401
    assert "X-Request-ID" in r401.headers  # logged even when rejected
    headers = {"X-API-Key": "secret"}
    assert c.post("/query", headers=headers).status_code == 200
    assert c.post("/query", headers=headers).status_code == 200
    assert c.post("/query", headers=headers).status_code == 429  # only authed hits counted
    monkeypatch.delenv("API_KEY")
    _hits.clear()
    assert c.post("/query").status_code == 200  # open mode when unset
