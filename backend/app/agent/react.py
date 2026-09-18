"""ReAct agent: plan → retrieve → observe → self-correct (max 3 hops).

Tools: hybrid_search, graph_lookup. The loop detects weak retrieval
(empty / low RRF mass) and retries with a rewritten query (RE-EMBEDDED, so both
branches see it) plus graph expansion whose supporting chunks are MERGED into
the candidate set — never trace-only decoration. Every step is returned in
`trace` so the dashboard can render the reasoning.

Honest scope note: query rewriting here is graph-driven expansion + a generic
lexical fallback (or an LLM reformulation when a provider is configured) — no
hardcoded entity strings. The loop tracks tried queries and stops on
convergence instead of spinning identical retries. Method used is labeled in
the trace.
"""
from __future__ import annotations


def _rewrite_for_recall(query: str, tried: set[str]) -> tuple[str, str]:
    """Returns (rewritten_query, method_label). Prefers graph-driven expansion
    (entity neighbors from the ACTUAL index — no hardcoded entity strings);
    falls back to LLM rewriting, then deterministic generic rules."""
    from backend.app.retrieval.graph import extract_entities, neighbors
    entities = extract_entities(query)
    extras = []
    for e in entities:
        for t in neighbors(e):
            for side in (t["s"], t["o"]):
                s = side.strip()
                if s and s.lower() not in query.lower() and all(s.lower() not in x.lower() for x in extras):
                    extras.append(s)
    if extras:
        return f"{query} {' '.join(extras[:4])}", "graph-expansion"
    from backend.app.config import settings
    provider = settings.llm_provider.lower()
    if provider in ("ollama", "openai"):
        try:
            out = _llm_rewrite(query, provider)
            if out and out.lower() not in tried:
                return out, "llm-rewrite"
        except Exception:
            pass
    # generic lexical fallback (no entity names): relation synonyms that never
    # contain the trigger word itself (a self-containing expansion is dead code)
    import re
    q = query
    swaps = [("supplier", "supply supplying vendor"), ("suppliers", "supply supplying vendor"),
             ("uses", "used using component"), ("provides", "supply supplies vendor"),
             ("warranty", "guarantee coverage months"), ("requires", "requirement needs")]
    for a, b in swaps:
        if re.search(rf"\b{a}\b", q, re.I) and not any(w in q.lower() for w in b.split()):
            q += " " + b
            break
    return q, "lexical-rules"


def _llm_rewrite(query: str, provider: str) -> str:
    from backend.app.config import settings
    sys_msg = ("Rewrite the user question for keyword + vector retrieval over enterprise "
               "docs. Expand entities (e.g. 'supplier of Product X' → include likely component "
               "terms). Reply with ONLY the rewritten question, one line.")
    if provider == "ollama":
        import ollama
        r = ollama.chat(model=settings.ollama_model,
                        messages=[{"role": "system", "content": sys_msg},
                                  {"role": "user", "content": query}],
                        think=False, options={"temperature": 0.0, "num_predict": 80})
        return r["message"]["content"].strip().split("\n")[0]
    from openai import OpenAI
    client = OpenAI(api_key=settings.openai_api_key)
    r = client.chat.completions.create(model=settings.openai_model,
        messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": query}],
        temperature=0.0, max_tokens=80)
    return r.choices[0].message.content.strip().split("\n")[0]


def run_agent(query: str, qvec: list[float], top_k: int = 20, backend: str = "local", max_hops: int = 3) -> tuple[list[dict], list[dict]]:
    from backend.app.ingest.embed import embed_query
    from backend.app.retrieval.hybrid import hybrid_search
    from backend.app.retrieval.reranker import rerank
    from backend.app.retrieval.graph import neighbors, extract_entities

    trace: list[dict] = [{"step": "plan", "detail": f"Decompose: '{query}' — checking for multi-hop entities (Product/Component/Supplier)."}]
    candidates, dbg = hybrid_search(query, qvec, top_k=top_k, backend=backend)
    trace.append({"step": "retrieve", "detail": f"hybrid: dense={dbg['dense_n']} sparse={dbg['sparse_n']}", "debug": dbg})

    mass = sum(c.get("rrf", 0) for c in candidates[:5])
    hop = 1
    tried = {query.strip().lower()}
    current = query  # rewrites chain: each hop expands the PREVIOUS query, so hop 3
    while (not candidates or mass < 0.02) and hop < max_hops:  # walks a 2nd graph ring
        hop += 1
        rewritten, method = _rewrite_for_recall(current, tried)
        if rewritten.strip().lower() in tried:
            trace.append({"step": "reflect", "detail": f"Hop {hop}: rewrite converged (no new query) — stopping."})
            break
        tried.add(rewritten.strip().lower())
        current = rewritten
        # re-embed so BOTH branches (not just BM25) see the rewrite
        qvec = embed_query(rewritten)
        trace.append({"step": "reflect", "detail": f"Hop {hop}: weak recall (mass={mass:.4f}) — retrying via {method} as '{rewritten}'."})
        candidates, dbg = hybrid_search(rewritten, qvec, top_k=top_k, backend=backend)
        mass = sum(c.get("rrf", 0) for c in candidates[:5])

    # graph expansion that actually counts: entity mentions → traversed triples →
    # supporting chunks merged into candidates (tagged) before reranking.
    # Candidates carry REAL text/doc metadata from the store — an empty-text
    # candidate scores 0.0 in every reranker and is silently truncated, which is
    # decoration, not expansion.
    from backend.app.retrieval.cache import get_store
    entities = extract_entities(query)
    g_hits = [t for e in entities for t in neighbors(e)]
    if g_hits:
        _, by_id = get_store()
        have = {c["chunk_id"] for c in candidates}
        added = 0
        for t in g_hits:
            cid = t.get("chunk_id")
            if cid and cid != "seed" and cid not in have and cid in by_id:
                chunk = by_id[cid]
                candidates.append({"chunk_id": cid, "doc_id": chunk.get("doc_id", ""),
                                   "text": chunk.get("text", ""), "parent_id": chunk.get("parent_id"),
                                   "dense_score": 0.0, "bm25_score": 0.0,
                                   "rrf": 0.01, "via_graph": True})
                have.add(cid)
                added += 1
        trace.append({"step": "graph_lookup",
                      "detail": f"entities={entities or 'none'} → {len(g_hits)} triples, {added} chunks merged.",
                      "triples": g_hits[:6]})

    ranked, rinfo = rerank(query, candidates, top_n=5)
    trace.append({"step": "rerank", "detail": f"{rinfo['method']} → top {len(ranked)}", "info": rinfo})
    trace.append({"step": "answer", "detail": "Composing grounded answer with citations."})
    return ranked, trace
