"""CLI query: python scripts/query_cli.py --q "..." [--no-agent]"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.ingest.embed import embed_query
from backend.app.retrieval.hybrid import hybrid_search
from backend.app.retrieval.reranker import rerank
from backend.app.agent.react import run_agent
from backend.app.security.guardrails import build_prompt, redact_pii
from backend.app.retrieval.generate import generate
from backend.app.config import settings


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", required=True)
    ap.add_argument("--no-agent", action="store_true")
    ap.add_argument("--top-k", type=int, default=10)
    args = ap.parse_args()

    import io
    qvec = embed_query(args.q)
    if args.no_agent:
        cands, dbg = hybrid_search(args.q, qvec, top_k=args.top_k, backend=settings.vector_backend)
        ranked, rinfo = rerank(args.q, cands, top_n=settings.rerank_top_n)
        trace = [{"step": "retrieve-direct", "detail": str(dbg)}, {"step": "rerank", "detail": str(rinfo)}]
    else:
        ranked, trace = run_agent(args.q, qvec, top_k=args.top_k, backend=settings.vector_backend)
    prompt = build_prompt(*redact_pii(args.q)[:1], ranked)
    answer, model = generate(prompt, args.q, ranked)
    print(f"\nQ: {args.q}\n[{model}]\n{answer}\n")
    print("--- trace ---")
    for t in trace:
        print(f"· {t['step']}: {t['detail']}")
    print("--- top chunks ---")
    for c in ranked:
        print(f"· {c['chunk_id']} ({c.get('doc_id')}) rerank={c.get('rerank_score')} rrf={c.get('rrf')}")


if __name__ == "__main__":
    main()
