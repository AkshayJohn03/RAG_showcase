"""BEIR SciFact through OUR pipeline (dense / BM25 / hybrid / hybrid+rerank).

Zero-shot: same MiniLM embeddings + rank-bm25 + RRF + FlashRank TinyBERT as the
app — no SciFact tuning. Metrics: nDCG@10, Recall@10, MRR@10 vs official qrels.
Saves data/eval/beir_scifact.json. Retrieval-only (BEIR is a retrieval benchmark;
generation quality is covered by golden_qa + llm_eval).
"""
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BEIR = ROOT / "data" / "beir" / "scifact"


def load():
    docs = {}
    for line in (BEIR / "corpus.jsonl").open(encoding="utf-8"):
        d = json.loads(line)
        docs[str(d["_id"])] = f"{d.get('title', '')} {d.get('text', '')}".strip()
    queries = {}
    for line in (BEIR / "queries.jsonl").open(encoding="utf-8"):
        q = json.loads(line)
        queries[str(q["_id"])] = q["text"]
    qrels: dict[str, dict[str, int]] = {}
    for line in (BEIR / "qrels" / "test.tsv").open(encoding="utf-8"):
        parts = line.strip().split()
        if len(parts) < 3 or parts[0] == "query-id":
            continue
        qrels.setdefault(parts[0], {})[parts[1]] = int(float(parts[2]))
    return docs, queries, qrels


def ndcg10(ranked: list[str], rel: dict[str, int]) -> float:
    dcg = sum((2 ** rel.get(d, 0) - 1) / math.log2(i + 2) for i, d in enumerate(ranked[:10]))
    ideal = sorted((2 ** v - 1 for v in rel.values()), reverse=True)[:10]
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def recall10(ranked: list[str], rel: dict[str, int]) -> float:
    got = {d for d in ranked[:10] if rel.get(d, 0) > 0}
    need = {d for d, v in rel.items() if v > 0}
    return len(got) / len(need) if need else 0.0


def mrr10(ranked: list[str], rel: dict[str, int]) -> float:
    for i, d in enumerate(ranked[:10], start=1):
        if rel.get(d, 0) > 0:
            return 1.0 / i
    return 0.0


def main():
    import numpy as np
    from backend.app.ingest.embed import embed_texts
    from backend.app.retrieval.bm25 import tokenize, PureBM25

    t0 = time.time()
    docs, queries, qrels = load()
    ids = list(docs.keys())
    print(f"docs={len(ids)} queries_total={len(queries)} test_queries={len(qrels)}", flush=True)

    print("embedding corpus...", flush=True)
    mat = np.array(embed_texts([docs[i] for i in ids]), dtype=np.float32)
    mat /= (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)
    print(f"embedded in {round(time.time()-t0)}s", flush=True)

    print("building bm25...", flush=True)
    tok = [tokenize(docs[i]) for i in ids]
    try:
        from rank_bm25 import BM25Okapi
        bm25 = BM25Okapi(tok)
        bm25_scores = lambda q: bm25.get_scores(tokenize(q))
    except Exception:
        pure = PureBM25(tok)
        bm25_scores = lambda q: np.array(pure.scores(tokenize(q)))
    print("index ready.", flush=True)

    try:
        from flashrank import Ranker, RerankRequest
        fr = Ranker(model_name="ms-marco-TinyBERT-L-2-v2")
    except Exception as e:
        fr = None
        print(f"flashrank unavailable: {e}", flush=True)

    qids = [q for q in qrels if q in queries]
    print(f"embedding {len(qids)} queries...", flush=True)
    qmat = np.array(embed_texts([queries[q] for q in qids]), dtype=np.float32)
    qmat /= (np.linalg.norm(qmat, axis=1, keepdims=True) + 1e-9)

    agg = {m: {"ndcg": [], "recall": [], "mrr": []} for m in ("dense", "bm25", "hybrid", "hybrid+rerank")}
    for qi, qid in enumerate(qids):
        q = queries[qid]
        rel = qrels[qid]
        dense_rank = np.argsort(-(qmat[qi] @ mat.T))[:50]
        sp = np.asarray(bm25_scores(q))
        bm25_rank = np.argsort(-sp)[:50]
        # RRF fusion of the two top-50s
        fused: dict[int, float] = {}
        for rank, idx in enumerate(dense_rank, 1):
            fused[int(idx)] = fused.get(int(idx), 0) + 1 / (60 + rank)
        for rank, idx in enumerate(bm25_rank, 1):
            fused[int(idx)] = fused.get(int(idx), 0) + 1 / (60 + rank)
        hybrid_rank = sorted(fused, key=fused.get, reverse=True)[:50]
        runs = {"dense": [ids[i] for i in dense_rank[:10]],
                "bm25": [ids[i] for i in bm25_rank[:10]],
                "hybrid": [ids[i] for i in hybrid_rank[:10]]}
        if fr is not None:
            cands = hybrid_rank[:50]
            req = RerankRequest(query=q, passages=[
                {"id": str(pos), "text": docs[ids[i]][:1500]} for pos, i in enumerate(cands)])
            runs["hybrid+rerank"] = [ids[cands[int(r["id"])]] for r in fr.rerank(req)[:10]]
        else:
            runs["hybrid+rerank"] = runs["hybrid"]
        for m, ranked in runs.items():
            agg[m]["ndcg"].append(ndcg10(ranked, rel))
            agg[m]["recall"].append(recall10(ranked, rel))
            agg[m]["mrr"].append(mrr10(ranked, rel))
        if (qi + 1) % 50 == 0:
            print(f"  {qi+1}/{len(qids)} ({round(time.time()-t0)}s)", flush=True)

    out = {m: {k: round(sum(v) / len(v), 4) for k, v in s.items()} for m, s in agg.items()}
    out["_meta"] = {"dataset": "BEIR SciFact/test", "n_queries": len(qids), "n_docs": len(ids),
                    "note": "zero-shot; same components as the app (MiniLM + rank-bm25 + RRF + TinyBERT)"}
    (ROOT / "data" / "eval" / "beir_scifact.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"total {round(time.time()-t0)}s", flush=True)
    for m, s in out.items():
        if m.startswith("_"):
            continue
        print(f"{m:>15}: " + "  ".join(f"{k}={v}" for k, v in s.items()))


if __name__ == "__main__":
    main()
