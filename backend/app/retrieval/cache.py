"""In-memory caches so per-query work stays in milliseconds.

- Vectors + BM25 index: loaded once, auto-refresh when ingest rewrites files (mtime check).
- Embedding model: warmed at server startup via warmup() (FastAPI lifespan),
  so the ~8s first-load cost happens at boot, never inside a user request.
"""
from __future__ import annotations
import json
from pathlib import Path

from backend.app.paths import VEC_PATH, BM25_PATH

_vec = {"mtime": -1.0, "rows": [], "by_id": {}}
_bm25 = {"mtime": -1.0, "metas": [], "tokenized": []}


def get_store() -> tuple[list[dict], dict]:
    try:
        mtime = VEC_PATH.stat().st_mtime
    except OSError:
        return [], {}
    if mtime != _vec["mtime"]:
        try:
            rows = json.loads(VEC_PATH.read_text(encoding="utf-8"))
        except Exception:
            rows = []
        _vec.update(mtime=mtime, rows=rows, by_id={r["chunk_id"]: r for r in rows})
    return _vec["rows"], _vec["by_id"]


def get_bm25() -> tuple[list[dict], list[list[str]]]:
    try:
        mtime = BM25_PATH.stat().st_mtime
    except OSError:
        return [], []
    if mtime != _bm25["mtime"]:
        try:
            data = json.loads(BM25_PATH.read_text(encoding="utf-8"))
            metas, tokenized = data["metas"], data["tokenized"]
        except Exception:
            metas, tokenized = [], []
        _bm25.update(mtime=mtime, metas=metas, tokenized=tokenized)
    return _bm25["metas"], _bm25["tokenized"]


def warmup() -> dict:
    """Preload everything slow. Call once at server startup, not per query."""
    import time
    t0 = time.time()
    rows, _ = get_store()
    metas, _ = get_bm25()
    embed_ms = None
    try:
        from backend.app.ingest.embed import embed_query
        t1 = time.time()
        embed_query("warmup")
        embed_ms = round((time.time() - t1) * 1000)
    except Exception:
        pass
    reranker = None
    try:
        from backend.app.config import settings
        if getattr(settings, "reranker", "auto") != "heuristic":
            from backend.app.retrieval.reranker import rerank as _rerank
            t1 = time.time()
            # probe once so the first real query never pays model-download cost
            _, info = _rerank("warmup", [{"chunk_id": "w", "doc_id": "w", "text": "warmup"}], top_n=1)
            reranker = f"{info.get('method')} ({round((time.time() - t1) * 1000)}ms probe)"
    except Exception:
        pass
    return {"vectors": len(rows), "bm25_docs": len(metas),
            "embed_warm_ms": embed_ms, "reranker": reranker,
            "total_ms": round((time.time() - t0) * 1000)}


# --- answer cache: repeat questions return in ~ms (session-less only,
# since session history changes the prompt). TTL keeps drift fixes flowing.
import time as _time

_ACACHE: dict[tuple, tuple[float, dict]] = {}
ACACHE_TTL_S = 600
ACACHE_MAX = 128


def answer_key(query: str, top_k: int, use_agent: bool, use_graph: bool) -> tuple:
    # index mtime in the key: re-ingest (new vectors file) instantly invalidates
    # cached answers with NO cross-process IPC — critical because /ingest runs
    # as a subprocess with its own memory. (Multi-replica still needs shared
    # storage for the index; see OPERATIONS.md.)
    try:
        idx_mtime = VEC_PATH.stat().st_mtime
    except OSError:
        idx_mtime = -1.0
    return (query.strip().lower(), top_k, use_agent, use_graph, idx_mtime)


def answer_get(key: tuple) -> dict | None:
    hit = _ACACHE.get(key)
    if not hit:
        return None
    ts, res = hit
    if _time.time() - ts > ACACHE_TTL_S:
        _ACACHE.pop(key, None)
        return None
    return {**res, "cached": True}


def answer_set(key: tuple, res: dict) -> None:
    if len(_ACACHE) >= ACACHE_MAX:
        _ACACHE.pop(next(iter(_ACACHE)))
    _ACACHE[key] = (_time.time(), {k: v for k, v in res.items() if k != "cached"})


# --- hot retrieval structures: normalized numpy matrix + built BM25 object.
# Both cost O(corpus) to build and were rebuilt on EVERY query (800ms + 200ms
# at 3.5k chunks). Built once here, invalidated by file mtime.
_mat = {"mtime": -1.0, "mat": None, "rows": []}
_bm25obj = {"mtime": -1.0, "obj": None, "kind": ""}


def get_matrix(searchable_only: bool = False):
    """(matrix[N,dim] L2-normalized, rows) — one matmul per query instead of a Python loop."""
    import numpy as np
    rows, _ = get_store()
    if searchable_only:
        rows = [r for r in rows if r.get("role", "child") != "parent"]
    if not rows:
        return None, []
    try:
        mtime = VEC_PATH.stat().st_mtime
    except OSError:
        return None, []
    if mtime != _mat["mtime"] or _mat["mat"] is None or _mat.get("searchable_only") != searchable_only:
        m = np.array([r["vector"] for r in rows], dtype=np.float32)
        m /= (np.linalg.norm(m, axis=1, keepdims=True) + 1e-9)
        _mat.update(mtime=mtime, mat=m, rows=rows, searchable_only=searchable_only)
    return _mat["mat"], _mat["rows"]


def get_bm25_obj():
    """Constructed BM25 scorer (BM25Okapi build is the expensive part, not scoring)."""
    metas, tokenized = get_bm25()
    if not metas:
        return None, "none"  # empty index: BM25Okapi([]) would ZeroDivisionError
    try:
        mtime = BM25_PATH.stat().st_mtime
    except OSError:
        return None, "none"
    if mtime != _bm25obj["mtime"] or _bm25obj["obj"] is None:
        try:
            from rank_bm25 import BM25Okapi
            _bm25obj.update(mtime=mtime, obj=BM25Okapi(tokenized), kind="okapi")
        except Exception:
            from backend.app.retrieval.bm25 import PureBM25
            _bm25obj.update(mtime=mtime, obj=PureBM25(tokenized), kind="pure")
    return _bm25obj["obj"], _bm25obj["kind"]
