from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.routes import router
from backend.app.ops.logging import RequestIdMiddleware
from backend.app.ops.middleware import AuthMiddleware, RateLimitMiddleware
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pay one-time costs here (not inside user requests):
    # 1. sync warmup: indexes + embedding model on the main thread
    # 2. thread warmup: requests run in a worker thread, and torch's first
    #    encode there costs ~2s — so run one encode via to_thread as well.
    # 3. sample prewarm: answer the 3 demo questions once so dashboard
    #    sample clicks return from cache instantly.
    try:
        import asyncio
        import os
        from backend.app.retrieval.cache import warmup
        print(f"[startup] warmup: {warmup()}", flush=True)
        from backend.app.ingest.embed import embed_query
        await asyncio.to_thread(embed_query, "warmup-thread")
        print("[startup] worker-thread encode warmed", flush=True)
        if os.getenv("PREWARM_SAMPLES", "1") == "1":
            from backend.app.api.schemas import QueryRequest
            from backend.app.api.routes import _answer
            for sq in ("Which supplier provides the component used in Product X?",
                       "What does SAF-114 require?",
                       "Which units failed and what revision were they?"):
                await asyncio.to_thread(_answer, QueryRequest(query=sq))
            print("[startup] sample answers prewarmed", flush=True)
    except Exception as e:
        print(f"[startup] warmup skipped: {e}", flush=True)
    yield
    try:
        from backend.app.retrieval.vector_store import _qdrant_clients
        for c in _qdrant_clients.values():
            c.close()
    except Exception:
        pass


import os

app = FastAPI(title="Senior RAG Showcase", version="1.0.0", lifespan=lifespan)
# NOTE on order: Starlette executes middleware in REVERSE addition order, so add
# them inside-out: RateLimit runs last (after Auth rejects unauthenticated calls,
# so attackers can't burn the shared budget), RequestId runs first (every
# response, including 401/429, gets an ID, a log line, and metrics).
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)
_frontend = [o for o in [os.getenv("FRONTEND_URL", ""), "http://localhost:3000"] if o]
app.add_middleware(CORSMiddleware, allow_origins=_frontend, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.add_middleware(RequestIdMiddleware)
app.include_router(router)


@app.get("/")
def root():
    return {"service": "senior-rag-showcase", "docs": "/docs", "health": "/health"}
