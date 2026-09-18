"""Vector store abstraction: local JSON/numpy store by default, Qdrant when configured.

Prod path (docker compose): VECTOR_BACKEND=qdrant → real Qdrant collection.
Local path: cosine search over data/04_vectors/vectors.json — zero infra.
"""
from __future__ import annotations
import json
import math
import threading
from pathlib import Path

_qdrant_lock = threading.Lock()  # module level: created under the import lock, race-free


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


class LocalStore:
    def __init__(self):
        from backend.app.retrieval.cache import get_store
        self.rows, _ = get_store()

    def search(self, qvec: list[float], top_k: int = 20) -> list[dict]:
        # parent-child contract: parents are stored for context expansion but
        # only children (role != "parent") participate in retrieval.
        try:  # numpy path: one matmul (~ms at 3.5k chunks)
            import numpy as np
            from backend.app.retrieval.cache import get_matrix
            mat, rows = get_matrix(searchable_only=True)
            q = np.array(qvec, dtype=np.float32)
            q /= (np.linalg.norm(q) + 1e-9)
            sims = mat @ q
            k = min(top_k, len(rows))
            idx = np.argpartition(-sims, k - 1)[:k]
            idx = idx[np.argsort(-sims[idx])]
            return [{"chunk_id": rows[i]["chunk_id"], "doc_id": rows[i]["doc_id"],
                     "text": rows[i].get("text", ""), "parent_id": rows[i].get("parent_id"),
                     "dense_score": round(float(sims[i]), 4)} for i in idx]
        except Exception:
            pass  # pure-python fallback below
        rows = [r for r in self.rows if r.get("role", "child") != "parent"]
        scored = [({"score": _cos(qvec, r["vector"]), **{k: v for k, v in r.items() if k != "vector"}}, _cos(qvec, r["vector"])) for r in rows]
        scored.sort(key=lambda t: t[1], reverse=True)
        return [{"chunk_id": s[0]["chunk_id"], "doc_id": s[0]["doc_id"], "text": s[0].get("text", ""),
                 "parent_id": s[0].get("parent_id"), "dense_score": round(s[1], 4)} for s in scored[:top_k]]


_qdrant_clients: dict[tuple, object] = {}


def _qdrant_client(backend: str):
    """Shared clients keyed by (backend, target) — connection pooling, a single
    lock-holder for qdrant-local, and test isolation: monkeypatching
    QDRANT_LOCAL_PATH yields a distinct client instead of reusing prod's."""
    import os
    from qdrant_client import QdrantClient
    from backend.app.config import settings
    from backend.app.paths import QDRANT_LOCAL_PATH
    target = os.getenv("QDRANT_LOCAL_PATH", str(QDRANT_LOCAL_PATH)) if backend == "qdrant-local" else settings.qdrant_url
    key = (backend, target)
    # double-checked locking on a MODULE-LEVEL lock (safe: import lock owns creation)
    if key not in _qdrant_clients:
        with _qdrant_lock:
            if key not in _qdrant_clients:
                _qdrant_clients[key] = QdrantClient(path=target) if backend == "qdrant-local" else QdrantClient(url=target)
    return _qdrant_clients[key]


def qdrant_search(qvec: list[float], top_k: int = 20, backend: str = "qdrant") -> list[dict]:
    from backend.app.config import settings
    client = _qdrant_client(backend)
    # parent-child contract holds here too: filter stored parent chunks server-side
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        qfilter = Filter(must_not=[FieldCondition(key="role", match=MatchValue(value="parent"))])
    except Exception:
        qfilter = None
    res = client.query_points(collection_name=settings.qdrant_collection, query=qvec,
                              limit=top_k, **({"query_filter": qfilter} if qfilter is not None else {}))
    # NOTE: shared client — closed at app shutdown (main.lifespan), not per query.
    return [{"chunk_id": str(p.payload.get("chunk_id", p.id)), "doc_id": (p.payload or {}).get("doc_id", ""),
             "text": (p.payload or {}).get("text", ""), "parent_id": (p.payload or {}).get("parent_id"),
             "dense_score": round(float(p.score), 4)} for p in res.points]


def dense_search(qvec: list[float], top_k: int = 20, backend: str = "local") -> list[dict]:
    if backend in ("qdrant", "qdrant-local"):
        try:
            return qdrant_search(qvec, top_k, backend)
        except Exception as e:
            # LOUD fallback: Qdrant failures must page, not silently degrade.
            try:
                from backend.app.ops.logging import logger
                logger.warning(f"qdrant {backend} failed ({e.__class__.__name__}); falling back to local store")
            except Exception:
                pass
            try:
                from backend.app.ops.metrics import set_gauge
                set_gauge("qdrant_fallback", 1)
            except Exception:
                pass
    return LocalStore().search(qvec, top_k)
