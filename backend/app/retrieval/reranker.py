"""Reranking cascade: cross-encoder → FlashRank (ONNX) → lexical heuristic.

Tier 1 (best): sentence-transformers CrossEncoder ms-marco-MiniLM.
Tier 2: FlashRank ms-marco-TinyBERT-L-2-v2 — ONNX, CPU-fast, no torch/transformers
  dependency risk (this env's transformers v5 breaks ST's CrossEncoder import).
Tier 3: token-overlap + exact-code boost — zero deps, fixes near-duplicate codes
  (SAF-114 vs SAF-118) even with nothing installed.
The active method + load errors are returned in info (silent fallbacks hide drift).
RERANKER env: auto (default) | cross-encoder | flashrank | heuristic.
"""
from __future__ import annotations
import re

_ce = None
_ce_failed: str | None = None
_fr = None
_fr_failed: str | None = None

CODE = re.compile(r"\b[A-Z]{2,}-\d+\b", re.IGNORECASE)  # SAF-114, XK-7 — any case


def _load_ce():
    global _ce, _ce_failed
    if _ce is not None or _ce_failed:
        return _ce
    try:
        from sentence_transformers import CrossEncoder
        _ce = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        return _ce
    except Exception as e:
        _ce_failed = f"{e.__class__.__name__}: {str(e)[:120]}"
        return None


def _load_flashrank():
    global _fr, _fr_failed
    if _fr is not None or _fr_failed:
        return _fr
    try:
        from flashrank import Ranker
        _fr = Ranker(model_name="ms-marco-TinyBERT-L-2-v2")
        return _fr
    except Exception as e:
        _fr_failed = f"{e.__class__.__name__}: {str(e)[:120]}"
        return None


def _heuristic(query: str, text: str) -> float:
    qtok = set(re.findall(r"[a-z0-9]+", query.lower()))
    ttok = set(re.findall(r"[a-z0-9]+", text.lower()))
    overlap = len(qtok & ttok) / max(1, len(qtok))
    # normalize case BEFORE intersecting: re.IGNORECASE matches, but set() on
    # raw strings does not ('saf-114' != 'SAF-114')
    qcodes = {c.upper() for c in CODE.findall(query)}
    tcodes = {c.upper() for c in CODE.findall(text)}
    code_boost = 0.5 if (qcodes & tcodes) else 0.0
    return round(overlap + code_boost, 4)


def _apply_heuristic(query: str, candidates: list[dict], top_n: int) -> tuple[list[dict], dict]:
    for c in candidates:
        c["rerank_score"] = _heuristic(query, c.get("text", ""))
    ranked = sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)[:top_n]
    pre = [c["chunk_id"] for c in candidates[:top_n]]
    post = [c["chunk_id"] for c in ranked]
    info = {"method": "heuristic(overlap+code-boost)", "rerank_delta": len(set(post) - set(pre))}
    if _ce_failed:
        info["cross_encoder_error"] = _ce_failed
    if _fr_failed:
        info["flashrank_error"] = _fr_failed
    return ranked, info


def rerank(query: str, candidates: list[dict], top_n: int = 5) -> tuple[list[dict], dict]:
    from backend.app.config import settings
    mode = getattr(settings, "reranker", "auto")
    if not candidates:
        return [], {"method": "none(empty)"}

    if mode in ("auto", "cross-encoder"):
        ce = _load_ce()
        if ce is not None:
            try:
                pairs = [(query, c.get("text", "")[:2000]) for c in candidates]
                scores = ce.predict(pairs).tolist()
                for c, s in zip(candidates, scores):
                    c["rerank_score"] = round(float(s), 4)
                ranked = sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)[:top_n]
                return ranked, {"method": "cross-encoder/ms-marco-MiniLM-L-6-v2"}
            except Exception:
                pass
        elif mode == "cross-encoder":
            return _apply_heuristic(query, candidates, top_n)

    if mode in ("auto", "flashrank"):
        fr = _load_flashrank()
        if fr is not None:
            try:
                from flashrank import RerankRequest
                req = RerankRequest(query=query, passages=[
                    {"id": str(i), "text": c.get("text", "")[:1500]} for i, c in enumerate(candidates)])
                scored = fr.rerank(req)
                order = [int(r["id"]) for r in scored]
                for rank, idx in enumerate(order):
                    candidates[idx]["rerank_score"] = round(float(scored[rank]["score"]), 4)
                ranked = [candidates[i] for i in order[:top_n]]
                return ranked, {"method": "flashrank/ms-marco-TinyBERT-L-2-v2"}
            except Exception:
                pass
        elif mode == "flashrank":
            return _apply_heuristic(query, candidates, top_n)

    return _apply_heuristic(query, candidates, top_n)
