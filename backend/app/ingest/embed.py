"""Embeddings with graceful degradation.

1. sentence-transformers (all-MiniLM-L6-v2, 384-d) when installed — real quality.
2. Hashing-TFIDF fallback (384-d, L2-normalized) — zero deps, deterministic,
   good enough to demo hybrid lift offline.
"""
from __future__ import annotations
import hashlib
import math
import re

_DIM = 384
_model = None
_model_failed = False

TOK = re.compile(r"[a-z0-9]+(?:[-_/][a-z0-9]+)*")


def _load_st():
    global _model, _model_failed
    if _model is not None or _model_failed:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        from backend.app.config import settings
        _model = SentenceTransformer(settings.embed_model)
        return _model
    except Exception:
        _model_failed = True
        return None


def _hash_vec(text: str, dim: int = _DIM) -> list[float]:
    toks = TOK.findall(text.lower())
    vec = [0.0] * dim
    for t in toks:
        h = int(hashlib.md5(t.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0 + math.log(1 + toks.count(t)) * 0.1
    n = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / n for v in vec]


def embed_texts(texts: list[str]) -> list[list[float]]:
    texts = [t or "" for t in texts]
    st = _load_st()
    if st is not None:
        try:
            return [v.tolist() if hasattr(v, "tolist") else list(v) for v in st.encode(texts, normalize_embeddings=True)]
        except Exception:
            pass
    return [_hash_vec(t) for t in texts]


def embed_query(q: str) -> list[float]:
    return embed_texts([q])[0]


from functools import lru_cache

@lru_cache(maxsize=512)
def embed_query_cached(q: str) -> tuple:
    """Cache repeat questions (dashboards retry, evals re-run). Returns tuple for hashability."""
    return tuple(embed_query(q))
