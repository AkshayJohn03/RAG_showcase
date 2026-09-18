"""Full eval run over data/eval/golden_qa.json — retrieval + generation metrics."""
from __future__ import annotations
import json
from pathlib import Path


def run_all(mode: str = "hybrid", use_rerank: bool = True, use_agent: bool = False) -> dict:
    from backend.app.ingest.embed import embed_query
    from backend.app.retrieval.hybrid import search_by_mode
    from backend.app.retrieval.reranker import rerank
    from backend.app.retrieval.generate import generate
    from backend.app.security.guardrails import build_prompt
    from backend.app.eval.metrics import (precision_at_k, recall_at_k, mrr, ndcg_at_k,
                                          faithfulness, answer_relevance)
    from backend.app.config import settings
    if use_agent:
        from backend.app.agent.react import run_agent

    from backend.app.paths import EVAL_DIR
    gold = json.loads((EVAL_DIR / "golden_qa.json").read_text(encoding="utf-8"))
    per_q, agg = [], {"p@5": [], "r@5": [], "mrr": [], "ndcg@5": [], "faith": [], "rel": []}
    for g in gold:
        qvec = embed_query(g["question"])
        if use_agent:
            # full agentic path (plan → hybrid → graph-merge → rerank), not just retrieval
            ranked, _ = run_agent(g["question"], list(qvec) if not isinstance(qvec, list) else qvec,
                                  top_k=10, backend=settings.vector_backend)
        else:
            cands, _ = search_by_mode(g["question"], qvec, top_k=10, backend=settings.vector_backend, mode=mode)
            ranked = rerank(g["question"], cands, top_n=5)[0] if use_rerank else cands[:5]
        rel = set(g["relevant_docs"])
        cids = [c["chunk_id"] for c in ranked]
        docs = [c.get("doc_id", "") for c in ranked]
        prompt = build_prompt(g["question"], ranked)
        answer, _ = generate(prompt, g["question"], ranked)
        row = {"id": g["id"], "p@5": round(precision_at_k(cids, rel), 3),
               "r@5": round(recall_at_k(docs, rel), 3), "mrr": round(mrr(cids, rel), 3),
               "ndcg@5": round(ndcg_at_k(cids, rel), 3),
               "faithfulness": round(faithfulness(answer, ranked), 3),
               "relevance": round(answer_relevance(answer, g["question"], g["answer_keywords"]), 3)}
        for k, ak in [("p@5", "p@5"), ("r@5", "r@5"), ("mrr", "mrr"), ("ndcg@5", "ndcg@5"),
                      ("faith", "faithfulness"), ("rel", "relevance")]:
            agg[k].append(row[ak])
        per_q.append(row)
    summary = {k: round(sum(v) / max(1, len(v)), 3) for k, v in agg.items()}
    summary["gate"] = "PASS" if summary.get("faith", 0) >= 0.6 and summary.get("r@5", 0) >= 0.6 else "REVIEW"
    summary["config"] = f"{mode}{'+rerank' if use_rerank else ''}{'+agent' if use_agent else ''}"
    return {"summary": summary, "per_question": per_q, "n": len(per_q)}
