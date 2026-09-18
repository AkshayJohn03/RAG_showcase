"""Hybrid fusion: BM25 + dense → Reciprocal Rank Fusion (k=60).

RRF needs no score normalization — ideal for heterogeneous branches.
Both branch scores are logged for the inspector UI (debuggability is senior-level).
"""
from __future__ import annotations


def rrf(dense: list[dict], sparse: list[dict], k: int = 60, top_n: int = 10) -> list[dict]:
    ranks: dict[str, dict] = {}

    def add(hits: list[dict], branch: str):
        for rank, h in enumerate(hits, start=1):
            cid = h["chunk_id"]
            e = ranks.setdefault(cid, {"chunk_id": cid, "doc_id": h.get("doc_id", ""),
                                       "text": h.get("text", ""), "parent_id": h.get("parent_id"),
                                       "dense_score": 0.0, "bm25_score": 0.0, "rrf": 0.0})
            e["rrf"] += 1.0 / (k + rank)
            if branch == "dense":
                e["dense_score"] = h.get("dense_score", 0.0)
            else:
                e["bm25_score"] = h.get("bm25_score", 0.0)

    add(dense, "dense")
    add(sparse, "sparse")
    fused = sorted(ranks.values(), key=lambda e: e["rrf"], reverse=True)[:top_n]
    for e in fused:
        e["rrf"] = round(e["rrf"], 5)
    return fused


def hybrid_search(query: str, qvec: list[float], top_k: int = 20, backend: str = "local") -> tuple[list[dict], dict]:
    from backend.app.retrieval.vector_store import dense_search
    from backend.app.retrieval.bm25 import bm25_search
    dense = dense_search(qvec, top_k=top_k, backend=backend)
    sparse = bm25_search(query, top_k=top_k)
    fused = rrf(dense, sparse, top_n=top_k)
    debug = {"dense_n": len(dense), "sparse_n": len(sparse),
             "dense_top": [d["chunk_id"] for d in dense[:3]],
             "sparse_top": [s["chunk_id"] for s in sparse[:3]]}
    return fused, debug


def search_by_mode(query: str, qvec: list[float], top_k: int = 20,
                   backend: str = "local", mode: str = "hybrid") -> tuple[list[dict], dict]:
    """Ablation-friendly retrieval: dense | bm25 | hybrid (RRF, no rerank here —
    reranking is toggled separately so its delta is measurable)."""
    from backend.app.retrieval.vector_store import dense_search
    from backend.app.retrieval.bm25 import bm25_search
    if mode == "dense":
        hits = dense_search(qvec, top_k=top_k, backend=backend)
        return hits, {"mode": "dense", "n": len(hits)}
    if mode == "bm25":
        hits = bm25_search(query, top_k=top_k)
        return hits, {"mode": "bm25", "n": len(hits)}
    return hybrid_search(query, qvec, top_k=top_k, backend=backend)
