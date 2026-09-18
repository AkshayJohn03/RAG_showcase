"""BM25 sparse retrieval. Uses rank-bm25 when installed, else a pure-python Okapi fallback."""
from __future__ import annotations
import json
import math
import re

TOK = re.compile(r"[a-z0-9]+(?:[-_/][a-z0-9]+)*")
# NOTE: index paths live in backend.app.paths (single source of truth); no
# module-level relative paths here — they break when cwd != repo root.


def tokenize(s: str) -> list[str]:
    return TOK.findall(s.lower())


class PureBM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.docs = docs
        self.N = len(docs)
        self.avgdl = sum(len(d) for d in docs) / max(1, self.N)
        df: dict[str, int] = {}
        for d in docs:
            for t in set(d):
                df[t] = df.get(t, 0) + 1
        self.idf = {t: math.log(1 + (self.N - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.k1, self.b = k1, b

    def scores(self, q: list[str]) -> list[float]:
        out = []
        for d in self.docs:
            dl = len(d) or 1
            tf: dict[str, int] = {}
            for t in d:
                tf[t] = tf.get(t, 0) + 1
            s = 0.0
            for t in q:
                f = tf.get(t, 0)
                if not f:
                    continue
                idf = self.idf.get(t, 0.0)
                s += idf * (f * (self.k1 + 1)) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            out.append(s)
        return out


def _load_index():
    from backend.app.retrieval.cache import get_bm25
    return get_bm25()


def bm25_search(query: str, top_k: int = 20) -> list[dict]:
    from backend.app.retrieval.cache import get_bm25_obj
    scorer, kind = get_bm25_obj()
    if scorer is None:
        return []
    metas, _ = _load_index()
    qtok = tokenize(query)
    try:
        if kind == "okapi":
            scores = scorer.get_scores(qtok).tolist()
        else:
            scores = scorer.scores(qtok)
    except Exception:
        return []
    ranked = sorted(zip(metas, scores), key=lambda t: t[1], reverse=True)[:top_k]
    return [{"chunk_id": m["chunk_id"], "doc_id": m["doc_id"], "text": m.get("text", ""),
             "parent_id": m.get("parent_id"), "bm25_score": round(float(s), 4)}
            for m, s in ranked if s > 0]
