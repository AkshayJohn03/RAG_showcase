# Session Journal — rag-senior-showcase build log

> Reconstructed build record (not a verbatim transcript). Covers the full session:
> scaffold → scale → hardening → four adversarial audit rounds.
> Date: 2026-09-17/18. Stack: Python 3.11, FastAPI, Nuxt 3, Qdrant, Ollama.

## 1. Origin & goal
Build a senior-level RAG portfolio project in `D:\aria\rag-senior-showcase` that clears
the "wrapper vs engineer" bar: custom chunking, hybrid search, reranking, evals,
GraphRAG, agentic retrieval, guardrails, ops. Target: Senior/Lead AI Engineer hiring
signal (later: MAANG/FAANG/OpenAI-calibre credibility).

## 2. Skills installed (skills.sh, project-scoped)
`ui-ux-pro-max`, `nuxt-ui`, `hybrid-search-implementation`, `rag-implementation`,
`evaluate-rag`, `qdrant-search-quality`, `postgres-hybrid-text-search`.
(`qdrant-hybrid-search` didn't exist — substituted `qdrant-search-quality`.)

## 3. Architecture as built
- **Lifecycle:** `data/01_raw → 02_cleaned → 03_chunked → 04_vectors`, content-hashed
  incremental ingest (unchanged docs reuse vectors; removed docs purged).
- **Chunking:** sliding-window (sentence-aware + overlap), semantic (table-safe),
  parent-child (child retrieves, parent generates). Measured: avg 194 tok/chunk,
  mean consecutive overlap 0.294.
- **Retrieval:** BM25 + dense (MiniLM-L6-v2) with RRF fusion → FlashRank TinyBERT
  rerank (cross-encoder → flashrank → heuristic cascade).
- **Agent:** ReAct loop (plan → hybrid → reflect/retry with re-embed → graph merge →
  rerank), graph-driven query expansion, convergence-breaking tried-set.
- **GraphRAG:** regex + LLM extraction, entity canonicalization, relation-direction
  guards (`Product X → uses → Component XK-7 → supplied_by → Nordwerk Precision`).
- **Generation:** Ollama (`qwen3:1.7b`, think disabled, token-capped) / OpenAI /
  extractive fallback with source-weighted, complete-sentence quoting.
- **Guardrails:** PII redaction, injection flag on both query paths,
  `<retrieved-context>` delimiters with breakout sanitization, closed citation sets.
- **Ops:** API-key auth, rate limiting (XFF-aware), JSON logs + request IDs,
  Prometheus metrics, deep `/health` (503 when degraded), SSE streaming,
  sessions, feedback loop, Langfuse tracing (env-gated), Dockerfile, k8s
  (API + Qdrant StatefulSet + provision Job), runbooks, CI eval gate.

## 4. Corpora
- 12 enterprise `.md` docs (catalog, suppliers, SLA, safety, HR, API ref, runbook,
  changelog, postmortem, returns, security) + 1,862 real 20 Newsgroups distractors.
  Index: 1,874 docs / 5,757 chunks. Golden set: 16 questions.
- BEIR SciFact (5,183 abstracts, 300 test queries) for external credibility.

## 5. Measured evidence (final)
- Ablation (16Q): dense collapses (R@5 0.41); BM25 leads ranking (NDCG 0.902);
  hybrid+rerank matches it (0.890) while carrying dense recall (→0.91).
- Generation: extractive faith 0.878/rel 0.938; qwen faith 0.719/rel 0.948
  (paraphrase vs heuristic-faithfulness tension, documented).
- BEIR SciFact nDCG@10: ours BM25 0.633 (≈ paper 0.665, harness validated);
  ours hybrid+TinyBERT **0.659** (≈ ColBERT 0.671, beats TAS-B 0.643).
- Latency: p50 885ms → **33ms**, p95 → **53ms** (cached numpy matrix + BM25 object);
  repeats ~0ms; boot pays ~8s once.

## 6. Adversarial audit rounds (all closed)
- **R1 (~25 findings):** NDCG math error, stream guardrail bypass, parent/child
  index asymmetry, XK-7 code-boost exclusion, silent Qdrant fallback, pgvector
  facade (removed entirely), JSON truncation, middleware order, health-always-200.
- **R2 (9 findings):** stream QueueFull deadlock, empty-text graph merge,
  one-way polarity guard, test/prod middleware mismatch, Qdrant parent filter,
  NDCG dedup positions, k8s provisioning.
- **R3 (3 edge cases):** Job startup race (`--wait` + `/readyz`), client cache
  keying `(backend, target)`, duplicate close.
- **R4 (13 findings):** Prometheus label escaping, stream error events + stream
  caching, tag-breakout sanitization, CODE case-insensitivity, citation-parser
  edges (leading/multi/extension), abstention variants, XFF trust flag, client
  init lock, graph-driven rewrite (hardcoded strings deleted), idempotent push
  (no more `delete_collection`), answer-cache mtime keying.
- Final state at close: **24/24 tests green**, eval gate PASS, zero drift.

## 7. Round 5 audit (all closed)
XFF hop-count-from-right, stream cached-`answer` key + frontend error/model fix,
module-level client lock, sentence-aware citation splitter (adjacent-only
attachment, no bleed), `doc_id` sanitization, Job split to `provision-job.yaml`,
qdrant test finalizer. Agent rewrite now graph-driven with zero hardcoded entity
strings (verified by grep) and chained progressive hops. Push is idempotent
(upsert + scroll-diff prune, `--wait` probes TCP then `/readyz`).
Final: **26/26 tests green**.

## 8. Key decisions & why
- FlashRank over broken ST-CrossEncoder (transformers-v5 import break; diagnosed,
  cascade built, failures surfaced not silent).
- Unbounded stream queue over per-token executor (answers length-capped).
- Honest BM25-wins narrative in README instead of metric cherry-picking.
- Extractive default (instant) + LLM opt-in (quality) with live token streaming.
- `think=False` for qwen3 (111s → 32s per answer on CPU).
- Answer-cache key includes index mtime (subprocess ingest can't IPC-invalidate).

## 9. Known limits (stated, not hidden)
- No production traffic history; 100k-scale server Qdrant untested here.
- Faithfulness is a heuristic (LLM judge = next upgrade); Presidio/Rebuff deferred.
- Per-process rate limiter; multi-replica needs gateway limiter + shared volume.
- Embedded-Qdrant bulk indexing is slow on Windows (~90s/256 pts).
- Torch/torchvision DLL mismatch in this laptop env (nothing imports torchvision;
  noted, not worked around).

## 10. File map (where things live)
- Backend: `backend/app/{api,agent,eval,ingest,ops,retrieval,security}/`
- Frontend: `frontend/` (Nuxt 3, SSE chat, trace inspector, eval/feedback panels)
- Data: `data/{01_raw (12 md + scale_20news/),eval (golden/baseline/ablation/llm/beir)}`
- Ops: `Dockerfile`, `docker-compose.yml`, `k8s/deployment.yaml`, `docs/OPERATIONS.md`,
  `docs/runbooks/retrieval_drift.md`, `.github/workflows/eval.yml`
- Reproduce everything: `make test && make eval-drift && python scripts/ablate.py`

## 11. Round 6 audit (all closed)
XFF hop-count-from-right (spoof-proof), `doc_id` sanitization, CODE upper()
normalization, frontend error-branch dedupe, dead-swap removal, dead path
constants removed, Qdrant `role` payload index, sentence-aware citation splitter
(no bleed), abstention variants, `--agent` eval (`data/eval/agent_eval.json`:
matches direct — rewrites correctly idle on this corpus), history-entity
follow-up expansion (live-verified: "its warranty" → Product X → correct
answer), MIT LICENSE, bge-reranker mention removed, journal renumbered.
Final: **26/26 tests green**, gate PASS, zero drift.
