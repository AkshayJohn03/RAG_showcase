"""HTTP routes: health / metrics / ingest / query(+stream) / eval(+history) / feedback / graph."""
from __future__ import annotations
import json
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, StreamingResponse
from backend.app.api.schemas import QueryRequest, IngestRequest, FeedbackRequest
from backend.app.config import settings

router = APIRouter()


@router.get("/health")
def health():
    """Deep health: index present, models loadable, backends reachable.

    Returns 503 when degraded so Kubernetes readiness/liveness probes actually
    remove failing pods (a 200-OK-everything health endpoint makes probes theater).
    """
    from fastapi.responses import JSONResponse
    from backend.app.retrieval.cache import get_store, get_bm25
    rows, _ = get_store()
    metas, _ = get_bm25()
    checks: dict[str, str] = {}
    checks["index"] = "ok" if rows else "empty — run scripts/ingest.py (not ready to serve)"
    try:
        from backend.app.ingest.embed import embed_query_cached
        embed_query_cached("health")
        checks["embed_model"] = "ok"
    except Exception as e:
        checks["embed_model"] = f"fail: {e.__class__.__name__}"
    if settings.vector_backend in ("qdrant", "qdrant-local"):
        try:
            # get_collections() is NOT enough: the server can be up with our
            # collection missing (fresh provision). Check the collection itself.
            from backend.app.retrieval.vector_store import _qdrant_client
            client = _qdrant_client(settings.vector_backend)
            info = client.get_collection(settings.qdrant_collection)
            checks["qdrant"] = "ok" if info.points_count else "empty collection — run push_qdrant.py"
        except Exception as e:
            checks["qdrant"] = f"fail: {e.__class__.__name__}: {str(e)[:100]}"
    ok = all(v == "ok" for v in checks.values())
    try:
        from backend.app.ops.metrics import set_gauge
        set_gauge("chunks_indexed", len(rows))
    except Exception:
        pass
    body = {"status": "ok" if ok else "degraded", "checks": checks,
            "chunks_indexed": len(rows), "bm25_docs": len(metas),
            "llm": settings.llm_provider, "vector_backend": settings.vector_backend,
            "strategy": settings.chunk_strategy, "tracing": _tracing_status()}
    return body if ok else JSONResponse(body, status_code=503)


def _tracing_status() -> str:
    try:
        from backend.app.ops.tracing import enabled
        return "langfuse" if enabled() else "off (set LANGFUSE_* keys to enable)"
    except Exception:
        return "off"


@router.get("/metrics", response_class=PlainTextResponse)
def metrics():
    from backend.app.ops.metrics import exposition
    return exposition()


@router.post("/ingest")
def ingest(req: IngestRequest):
    import subprocess, sys
    r = subprocess.run([sys.executable, "scripts/ingest.py", "--strategy", req.strategy],
                       capture_output=True, text=True)
    return {"ok": r.returncode == 0, "strategy": req.strategy,
            "stdout": r.stdout[-2000:], "stderr": r.stderr[-2000:]}


def _needs_coref(query: str) -> bool:
    """Anaphora gate: expand with history entities only when the query cannot
    stand alone — contains a pronoun (it/its/they/this/...) or is too short to
    carry its own entities. Anything else retrieves on its own terms."""
    import re
    q = query.lower()
    if re.search(r"\b(it|its|they|them|their|this|that|these|those|he|she|him|her)\b", q):
        return True
    return len(re.findall(r"[a-z0-9]+", q)) <= 4


def _retrieve(req: QueryRequest, qvec: list[float]):
    """Shared retrieval + prep stage. Returns (ranked, trace, safe_q, safe_ctx, prompt)."""
    from backend.app.retrieval.hybrid import hybrid_search
    from backend.app.retrieval.reranker import rerank
    from backend.app.agent.react import run_agent
    from backend.app.security.guardrails import redact_pii, build_prompt
    from backend.app.ops.sessions import history_block, recall
    from backend.app.retrieval.graph import extract_entities

    rquery, expansion = req.query, []
    if req.session_id and _needs_coref(req.query):
        # conversational retrieval ONLY for anaphoric follow-ups ("what is ITS
        # warranty?"). Unconditional expansion poisoned unrelated questions:
        # history entities ("Product X") hijacked "what are the leave policies"
        # into supplier docs. Anaphora-gating fixes it.
        for turn in recall(req.session_id):
            for e in extract_entities(turn.get("q", "")):
                if e.lower() not in rquery.lower() and e not in expansion and len(expansion) < 3:
                    expansion.append(e)
    if expansion:
        rquery = f"{req.query} {' '.join(expansion)}"
        from backend.app.ingest.embed import embed_query_cached
        qvec = list(embed_query_cached(rquery.strip().lower()))  # both branches see it

    if req.use_agent:
        ranked, trace = run_agent(rquery, qvec, top_k=req.top_k, backend=settings.vector_backend)
    else:
        cands, dbg = hybrid_search(rquery, qvec, top_k=req.top_k, backend=settings.vector_backend)
        ranked, rinfo = rerank(rquery, cands, top_n=settings.rerank_top_n)
        trace = [{"step": "retrieve", "detail": f"hybrid direct ({rinfo['method']})", "debug": dbg}]
    if expansion:
        trace.append({"step": "coref", "detail": f"follow-up expanded with history entities: {expansion}"})
    contexts = _to_parents(ranked)
    safe_q, _ = redact_pii(req.query)
    safe_ctx, redactions = [], []
    for c in contexts:
        txt, f = redact_pii(c.get("text", ""))
        redactions += f
        safe_ctx.append({**c, "text": txt})
    prompt = build_prompt(safe_q, safe_ctx, history=history_block(req.session_id or ""))
    return ranked, trace, safe_q, safe_ctx, prompt, sorted(set(redactions))


def _verification(provider: str, trace_id, trace_url) -> dict:
    """What proves this answer: Langfuse trace when keyed, else last eval gate."""
    from backend.app.eval.history import read_history
    last = read_history(1)
    gate = dict(last[0]["summary"]) if last else {}
    if not gate:  # fresh container: history.jsonl isn't baked in, baseline.json is
        try:
            from backend.app.paths import BASELINE_PATH
            if BASELINE_PATH.exists():
                gate = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
                gate["source"] = "baseline"
        except Exception:
            pass
    return {"provider": provider, "trace_id": trace_id, "trace_url": trace_url,
            "eval_gate": gate.get("gate"), "eval_faithfulness": gate.get("faith")}


def _local_verification() -> dict:
    return _verification("local", None, None)


def _answer(req: QueryRequest):
    from backend.app.ingest.embed import embed_query_cached
    from backend.app.retrieval.hybrid import hybrid_search
    from backend.app.retrieval.reranker import rerank
    from backend.app.agent.react import run_agent
    from backend.app.security.guardrails import redact_pii, injection_flag, build_prompt
    from backend.app.retrieval.generate import generate
    from backend.app.retrieval.graph import neighbors
    from backend.app.retrieval.cache import answer_key, answer_get, answer_set
    from backend.app.ops.sessions import remember, history_block
    from backend.app.ops.tracing import trace_query, enabled
    from backend.app.eval.metrics import faithfulness

    if injection_flag(req.query):
        return {"answer": "That request looks like a prompt-injection attempt, so I won't comply. Please ask about the indexed documents.",
                "citations": [], "contexts": [], "trace": [{"step": "guardrail", "detail": "injection blocked"}],
                "model": "guardrail", "pii_redactions": [], "usage": {"prompt_tokens": 0, "completion_tokens": 0},
                "verification": _local_verification()}
    use_cache = not (req.session_id or "")
    key = answer_key(req.query, req.top_k, req.use_agent, req.use_graph) if use_cache else None
    if use_cache:
        hit = answer_get(key)
        if hit:
            return hit
    with trace_query("rag.query", req.query, {"agent": req.use_agent}) as t:
        with t.span("embed", input=req.query):
            qvec = list(embed_query_cached(req.query.strip().lower()))
        with t.span("retrieve+prepare"):
            ranked, trace, safe_q, safe_ctx, prompt, redactions = _retrieve(req, qvec)
        with t.span("generate", input=prompt[:2000]):
            answer, model = generate(prompt, safe_q, safe_ctx)
        t.score("faithfulness", round(faithfulness(answer, safe_ctx), 3))
        t.score("rerank_top1", float(ranked[0].get("rerank_score") or 0) if ranked else 0.0)
        verification = _verification("langfuse" if enabled() else "local", t.trace_id(), t.url())
    if req.session_id:
        remember(req.session_id, req.query, answer)
    usage = {"prompt_tokens": len(prompt) // 4, "completion_tokens": len(answer) // 4}
    from backend.app.retrieval.graph import extract_entities
    graph = [t for e in extract_entities(req.query) for t in neighbors(e)][:8] if req.use_graph else []
    res = {"answer": answer, "citations": [{"chunk_id": c["chunk_id"], "doc_id": c.get("doc_id", "")} for c in safe_ctx],
           "contexts": safe_ctx, "trace": trace, "model": model,
           "graph_triples": graph[:8], "pii_redactions": sorted(set(redactions)), "usage": usage,
           "verification": verification}
    if use_cache:
        answer_set(key, res)
    return res


def _to_parents(ranked: list[dict]) -> list[dict]:
    from backend.app.retrieval.cache import get_store
    _, by_id = get_store()
    out = []
    for c in ranked:
        pid = c.get("parent_id")
        if pid and pid in by_id:
            p = by_id[pid]
            out.append({"chunk_id": pid, "doc_id": p.get("doc_id", ""), "text": p.get("text", ""),
                        "retrieved_via": c["chunk_id"], "rerank_score": c.get("rerank_score")})
        else:
            full = by_id.get(c["chunk_id"], {})
            out.append({"chunk_id": c["chunk_id"], "doc_id": c.get("doc_id", full.get("doc_id", "")),
                        "text": full.get("text", c.get("text", "")), "rerank_score": c.get("rerank_score")})
    seen, ded = set(), []
    for c in out:
        if c["chunk_id"] not in seen:
            seen.add(c["chunk_id"])
            ded.append(c)
    return ded[: settings.rerank_top_n]


@router.post("/query")
def query(req: QueryRequest):
    return _answer(req)


@router.get("/query/stream")
def query_stream(query: str, top_k: int = 10, use_agent: bool = True,
                 use_graph: bool = True, session_id: str = ""):
    """SSE stream: ack → retrieval trace → LIVE generation tokens → done envelope.

    Retrieval runs first (~100ms warmed); then generation tokens stream as the
    model produces them (Ollama) or in word-chunks (extractive fallback). The UI
    shows trace + first words in well under a second even when the full answer
    takes 30s on CPU — perceived latency stays near zero."""
    import asyncio
    import threading

    from backend.app.security.guardrails import injection_flag

    async def gen():
        yield f"event: stage\ndata: {json.dumps({'stage': 'started'})}\n\n"
        if injection_flag(query):
            refusal = "That request looks like a prompt-injection attempt, so I will not comply."
            yield f"event: token\ndata: {json.dumps({'text': refusal})}\n\n"
            yield f"event: done\ndata: {json.dumps({'answer': refusal, 'citations': [], 'contexts': [], 'model': 'guardrail'})}\n\n"
            return
        # stream serves the answer cache too (session-less repeats only — same
        # rule as POST /query, otherwise conversational answers would go stale)
        if not session_id:
            from backend.app.retrieval.cache import answer_key, answer_get
            hit = answer_get(answer_key(query, top_k, use_agent, use_graph))
            if hit:
                for t in hit.get("trace", []):
                    yield f"event: trace\ndata: {json.dumps(t)}\n\n"
                words = hit["answer"].split(" ")
                for i in range(0, len(words), 8):
                    yield f"event: token\ndata: {json.dumps({'text': ' '.join(words[i:i+8]) + ' '})}\n\n"
                yield f"event: done\ndata: {json.dumps({**{k: hit[k] for k in ('answer','citations','contexts','model','graph_triples','pii_redactions','usage','verification') if k in hit}, 'cached': True})}\n\n"
                return
        loop = asyncio.get_running_loop()
        req = QueryRequest(query=query, top_k=top_k, use_agent=use_agent,
                           use_graph=use_graph, session_id=session_id)
        from backend.app.ingest.embed import embed_query_cached
        from backend.app.retrieval.generate import generate_stream
        from backend.app.retrieval.graph import neighbors
        from backend.app.ops.sessions import remember
        from backend.app.ops.tracing import trace_query, enabled
        from backend.app.eval.metrics import faithfulness

        with trace_query("rag.query.stream", query, {"agent": use_agent}) as t:
            qvec = await loop.run_in_executor(None, lambda: list(embed_query_cached(query.strip().lower())))
            ranked, trace, safe_q, safe_ctx, prompt, redactions = await loop.run_in_executor(None, _retrieve, req, qvec)
            for step in trace:
                yield f"event: trace\ndata: {json.dumps(step)}\n\n"
            # ONE background thread produces tokens into an UNBOUNDED asyncio.Queue.
            # Why unbounded: answers are length-capped (num_predict 250 / top-3
            # quotes), so worst-case memory is ~KBs; a bounded queue + put_nowait
            # raises QueueFull when the producer outruns the consumer, dropping
            # tokens and possibly the None sentinel (permanent consumer hang).
            # Disconnect cancels gen(): worker is daemon + stop flag checked.
            aq: asyncio.Queue = asyncio.Queue()
            stop = threading.Event()
            failure: list[str] = []

            def worker():
                try:
                    for tok in generate_stream(prompt, safe_q, safe_ctx):
                        if stop.is_set():
                            break
                        try:
                            loop.call_soon_threadsafe(aq.put_nowait, tok)
                        except Exception:
                            break
                except Exception as e:  # model/transport failure: surfaced below, never silent
                    failure.append(f"{e.__class__.__name__}: {str(e)[:200]}")
                finally:
                    try:
                        loop.call_soon_threadsafe(aq.put_nowait, None)
                    except Exception:
                        pass

            threading.Thread(target=worker, daemon=True).start()
            parts = []
            try:
                while True:
                    tok = await aq.get()
                    if tok is None:
                        break
                    parts.append(tok)
                    yield f"event: token\ndata: {json.dumps({'text': tok})}\n\n"
            finally:
                stop.set()
            if failure and not parts:
                # total generation failure: explicit error event, NOT a fake done
                yield f"event: error\ndata: {json.dumps({'detail': 'generation failed: ' + failure[0]})}\n\n"
                return
            answer = "".join(parts)
            t.score("faithfulness", round(faithfulness(answer, safe_ctx), 3))
            if session_id:
                remember(session_id, query, answer)
            usage = {"prompt_tokens": len(prompt) // 4, "completion_tokens": len(answer) // 4}
            from backend.app.retrieval.graph import extract_entities as _ee
            graph = [t for e in _ee(query) for t in neighbors(e)][:8] if use_graph else []
            done = {"answer": answer,
                    "citations": [{"chunk_id": c["chunk_id"], "doc_id": c.get("doc_id", "")} for c in safe_ctx],
                    "contexts": safe_ctx, "model": "stream",
                    "graph_triples": graph[:8], "pii_redactions": redactions, "usage": usage,
                    "verification": _verification("langfuse" if enabled() else "local", t.trace_id(), t.url())}
            if failure:  # partial stream: flag it instead of silently truncating
                done["truncated"] = True
                done["error"] = "generation failed: " + failure[0]
            if not session_id and not failure:
                from backend.app.retrieval.cache import answer_key as _ak, answer_set as _aset
                _aset(_ak(query, top_k, use_agent, use_graph),
                      {**done, "trace": trace})
            yield f"event: done\ndata: {json.dumps(done)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/eval")
def eval_route():
    from backend.app.eval.run_eval import run_all
    from backend.app.eval.history import record_eval
    from backend.app.ops.metrics import set_gauge
    res = run_all()
    try:
        record_eval(res["summary"], strategy=settings.chunk_strategy)
        set_gauge("eval_gate_pass", 1 if res["summary"].get("gate") == "PASS" else 0)
        for k, v in res["summary"].items():
            if isinstance(v, (int, float)):
                set_gauge(f"eval_{k}", v)
    except Exception:
        pass
    return res


@router.get("/eval/history")
def eval_history(limit: int = 30):
    from backend.app.eval.history import read_history
    return {"runs": read_history(limit)}


@router.post("/feedback")
def feedback(req: FeedbackRequest):
    from backend.app.eval.history import record_feedback
    from backend.app.ops.metrics import bump
    if req.vote not in ("up", "down"):
        return {"ok": False, "detail": "vote must be up|down"}
    record_feedback(req.session_id, req.query, req.vote, req.note)
    try:
        bump("feedback", {"vote": req.vote})
    except Exception:
        pass
    return {"ok": True}


@router.get("/graph/neighbors")
def graph_neighbors(entity: str = "Product X", hops: int = 2):
    from backend.app.retrieval.graph import neighbors
    return {"entity": entity, "triples": neighbors(entity, hops)}


@router.get("/feedback/stats")
def feedback_stats():
    from backend.app.eval.history import feedback_stats as stats
    return stats()
