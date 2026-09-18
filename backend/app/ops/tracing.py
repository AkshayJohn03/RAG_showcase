"""Langfuse tracing for pipeline verification (env-gated, never breaks local runs).

Set LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY (+ optional LANGFUSE_HOST) and every
/query gets a trace: spans per stage (embed → hybrid → rerank → graph → generate)
plus scores (recall proxy, faithfulness, answer relevance). Without keys everything
is a silent no-op and the API reports provider="local" with the last eval gate.
"""
from __future__ import annotations
import os
from contextlib import contextmanager, nullcontext

_client = None
_disabled_reason = "keys not set"


def _get_client():
    global _client, _disabled_reason
    if _client is not None:
        return _client
    pk, sk = os.getenv("LANGFUSE_PUBLIC_KEY", ""), os.getenv("LANGFUSE_SECRET_KEY", "")
    if not (pk and sk):
        return None
    try:
        from langfuse import Langfuse
        _client = Langfuse(public_key=pk, secret_key=sk,
                           host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"))
        return _client
    except Exception as e:
        _disabled_reason = f"init failed: {e.__class__.__name__}"
        return None


def enabled() -> bool:
    return _get_client() is not None


@contextmanager
def trace_query(name: str, question: str, meta: dict | None = None):
    """Yield a tracer handle (real or no-op). Use: with trace_query(...) as t: ..."""
    client = _get_client()
    if client is None:
        yield _NoopTracer()
        return
    try:
        cm = client.start_observation(name=name, input={"question": question}, metadata=meta or {})
        with cm:
            yield _LiveTracer(client)
    except Exception:
        yield _NoopTracer()


class _NoopTracer:
    def span(self, name: str, **kw):
        return nullcontext()

    def score(self, name: str, value: float, comment: str = ""):
        pass

    def url(self):
        return None

    def trace_id(self):
        return None


class _LiveTracer:
    def __init__(self, client):
        self._client = client

    def span(self, name: str, **kw):
        try:
            return self._client.start_observation(name=name, input=kw.get("input"))
        except Exception:
            return nullcontext()

    def score(self, name: str, value: float, comment: str = ""):
        try:
            self._client.score_current_trace(name=name, value=value, comment=comment)
        except Exception:
            pass

    def url(self):
        try:
            return self._client.get_trace_url()
        except Exception:
            return None

    def trace_id(self):
        try:
            return self._client.get_current_trace_id()
        except Exception:
            return None
