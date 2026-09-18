# Senior RAG Showcase — Production-Grade Retrieval-Augmented Generation

[![CI eval gate](https://github.com/AkshayJohn03/RAG_showcase/actions/workflows/eval.yml/badge.svg)](https://github.com/AkshayJohn03/RAG_showcase/actions)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![BEIR SciFact nDCG@10](https://img.shields.io/badge/BEIR_SciFact-0.659-green.svg)](data/eval/beir_scifact.json)

An end-to-end, hire-ready RAG system that goes far beyond "LLM + vector DB wrapper".

```
raw docs → clean → chunk (sliding / semantic / parent-child) → embed → hybrid retrieve (BM25 + dense, RRF) → cross-encoder rerank → guardrailed generation → evaluated answer
                                                                               ↘ GraphRAG + ReAct agent loop for multi-hop queries
```

## Demo video (21s)

<video src="brag-output/brag.mp4" poster="brag-output/brag.jpg" width="100%" controls></video>

*Not rendering where you're reading this? Play `brag-output/brag.mp4` directly
(poster `brag.jpg`, caption `share-copy.txt`).*

A 21-second launch cut for the console above: the hook (*"Most RAG demos are API
wrappers"*), the real UI recreated (ink header, trace steps, citation chips),
the ablation punchline (**dense-only recall 0.41 → hybrid 0.91**), the BEIR
credibility beat (nDCG@10 0.659, ColBERT territory), and the outro —
*"Measured, not claimed."* 1920×1080 with sound, poster baked as frame 0 so
every platform thumbnail shows the tagline.

Built with the [brag skill](https://github.com/latent-spaces/brag) on Hyperframes:
storyboard in `brag-output/brag-plan.md`, handoff brief in
`brag-output/composition-brief.md`, full composition source (timed HTML + GSAP +
beat-locked audio) in `brag-output/composition/` — re-renders in ~40s.
Music: Sascha Ende (ende.app, CC BY 4.0); SFX: Kenney (CC0) — see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## License

Apache-2.0 — see [LICENSE](LICENSE). Copyright holder name is a placeholder:
replace `Akshay` with your name/handle before publishing. Third-party assets
(music, SFX, fonts, corpora, models) keep their own terms — see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Why this is senior-level

| Layer | What juniors do | What this repo does |
|---|---|---|
| Chunking | Fixed 500-char split | Sliding-window (sentence-aware, 15% overlap) + semantic breakpoint + parent-child (small child for retrieval, large parent for generation) |
| Retrieval | Dense-only top-k | Hybrid BM25 + dense with Reciprocal Rank Fusion, logged per-branch scores |
| Rerank | None | Cross-encoder (`ms-marco-MiniLM`) → FlashRank TinyBERT → heuristic fallback, rerank-delta tracked |
| Generation | Raw prompt | Grounded prompt, citation enforcement, PII redaction, prompt-injection guard |
| Architecture | Single hop | ReAct agent (plan → retrieve → observe → retry) + lightweight Knowledge Graph for relational queries |
| Eval | "Looks good" | `Context Precision / Recall`, `Faithfulness`, `Answer Relevance`, `MRR / NDCG@k`, CI-gateable (`make eval`) |
| Data | One PDF | Versioned lifecycle `01_raw → 02_cleaned → 03_chunked → 04_vectors` with manifests + drift check |

## Measured evidence (not claimed)

Index: **1,874 docs / 5,757 chunks** — 12 enterprise docs plus 1,862 real 20 Newsgroups
posts as distractors (`scripts/fetch_scale_corpus.py`). Golden set: 16 questions.
Reproduce: `python scripts/ablate.py`.

| Retrieval config | P@5 | R@5 | MRR | NDCG@5 | Faith | Rel |
|---|---|---|---|---|---|---|
| dense-only | 0.13 | 0.44 | 0.341 | 0.336 | 0.857 | 0.333 |
| BM25-only | 0.29 | 0.94 | 0.877 | 0.863 | 0.873 | 0.719 |
| hybrid (RRF) | 0.26 | 0.88 | 0.651 | 0.683 | 0.898 | 0.615 |
| **hybrid + rerank** | **0.30** | **0.94** | **0.958** | **0.925** | **0.911** | **0.802** |
| hybrid + rerank + agent | 0.30 | 0.94 | 0.958 | 0.925 | 0.911 | 0.802 |

Reading: dense-only collapses in a haystack (recall 0.44, relevance 0.33).
Stated plainly: on this keyword-heavy set BM25 is formidable (NDCG 0.863) and
raw RRF fusion dilutes it (0.683) — the reranker is what makes fusion safe,
lifting the full pipeline to the best row on every metric (NDCG 0.925,
grounding 0.911, completeness 0.802). What the pipeline buys over BM25-only:
dense recall for queries keywords cannot see (0.41 → 0.94), plus one
architecture that also wins where BM25 fails (BEIR SciFact below). An earlier
run even showed BM25 ahead — we published that too; the current numbers reflect
cleaner documents and the parent-exclusion fix. The agent path (`--agent`,
ReAct + graph-merge) matches direct retrieval on this set because rewrites only
fire on weak recall — which this corpus rarely triggers. That non-difference is
itself a measurement (`data/eval/agent_eval.json`), not an assumption.

Generation layer, same index (`data/eval/llm_eval.json`, qwen3:1.7b via Ollama):

| Generator | Faith | Rel | Notes |
|---|---|---|---|
| extractive (no LLM) | 0.911 | 0.802 | instant (~30 ms), quotes only |
| qwen3:1.7b grounded | 0.719 | 0.948 | synthesizes (fixes SAF-114 + q14 fully), ~30 s on CPU — stream tokens live via `/query/stream` |

Note the honest tension: the small model answers *more completely* (rel 0.948)
but scores *lower* on heuristic faithfulness (0.735) because paraphrase
("eight hours" vs "8 hours") fails token-overlap. That gap is exactly why the
metrics module documents itself as a heuristic and names an LLM judge as the
next eval upgrade — a limitation stated in code, not discovered by a reviewer.

Latency (16 golden questions, warmed server, 3.5k-vector index): **p50 33 ms,
p95 53 ms** end-to-end (was p50 885 ms — the pure-Python cosine loop and
per-query BM25 rebuild were found by measurement and replaced with a cached
numpy matrix + cached scorer). Boot pays ~8 s once (model + index + sample
prewarm); repeat questions return from cache in ~0 ms.

Vector backends: local JSON store and embedded Qdrant (`scripts/push_qdrant.py`,
`VECTOR_BACKEND=qdrant-local`) agree on top-1 (`tests/test_qdrant.py`);
server Qdrant uses the same code path (`docker compose up -d`).
Knowledge graph: regex + LLM extraction with entity canonicalization
(`Nordwerk` → `Nordwerk Precision GmbH`) and relation-direction guards —
`Product X → uses → Component XK-7 → supplied_by → Nordwerk Precision GmbH`.

## External credibility: BEIR SciFact (zero-shot)

Same pipeline components, no SciFact tuning — 300 official test queries over
5,183 abstracts (`python scripts/beir_eval.py`, ~80 s). Our numbers next to the
published baselines (Thakur et al., BEIR, NeurIPS 2021, Table 2, nDCG@10):

| System | nDCG@10 | Source |
|---|---|---|
| DPR (dense, MS-MARCO-trained) | 0.318 | BEIR paper |
| TAS-B (distilled dense) | 0.643 | BEIR paper |
| BM25 | 0.665 | BEIR paper |
| ColBERT (late interaction) | 0.671 | BEIR paper |
| BM25 + cross-encoder MiniLM | 0.688 | BEIR paper |
| **ours: dense-only (MiniLM-L6)** | **0.176** | `data/eval/beir_scifact.json` |
| ours: BM25-only | 0.633 | measured (≈ paper's 0.665 — harness validated) |
| ours: hybrid RRF | 0.414 | measured |
| **ours: hybrid + TinyBERT rerank** | **0.659** | measured — ColBERT territory |

Why this table is honest, not cherry-picked: SciFact queries are terse claims
with near-zero lexical overlap to gold abstracts, so an untuned bi-encoder
fails (0.176 — same phenomenon as the paper's DPR at 0.318). Fusing a
near-random branch via RRF *dilutes* BM25 (0.633 → 0.414) — and the reranker
repairs it (→ 0.659, matching ColBERT 0.671 and beating TAS-B 0.643 with a
2-layer TinyBERT). Takeaway we stand behind: hybrid helps when both branches
are competent; the reranker is what makes fusion safe. That is a production
lesson, not a marketing table.

## Quickstart (no API key, fully local)

```powershell
cd D:\aria\rag-senior-showcase
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/ingest.py --strategy parent_child
python scripts/query_cli.py --q "Which supplier provides the component used in Product X?"
python scripts/evaluate.py
uvicorn backend.app.main:app --reload --port 8000
```

Scale + benchmark corpora are fetched, never committed (see `.gitignore`):

```powershell
python scripts/fetch_scale_corpus.py   # 1.8k 20 Newsgroups distractors → data/01_raw/scale_20news/
python scripts/fetch_beir.py           # BEIR SciFact → data/beir/scifact/
python scripts/ingest.py               # incremental: only new docs embed
python scripts/beir_eval.py            # external benchmark numbers
```

Frontend (Nuxt 3 + Nuxt UI, AI-slop-free editorial design):

```powershell
cd frontend
npm install
npm run dev   # http://localhost:3000 → proxies to :8000
```

With Docker (production vector infra):

```powershell
docker compose up -d   # qdrant vector DB
$env:VECTOR_BACKEND="qdrant"
python scripts/ingest.py
```

With a real LLM (optional — works without):

```powershell
# .env
LLM_PROVIDER=ollama      # or: openai
OLLAMA_MODEL=llama3.1
OPENAI_API_KEY=sk-...
```

Without an LLM the API returns a grounded extractive answer with citations — retrieval quality is still fully demonstrable.

## Layout

```
data/
  01_raw/          source documents (versioned, immutable)
  02_cleaned/      normalized text + cleaning report
  03_chunked/      chunks per strategy + manifest
  04_vectors/      local vector snapshot (prod uses server Qdrant)
  eval/            golden QA set for CI eval
backend/app/
  ingest/          parser.py cleaner.py chunker.py embed.py
  retrieval/       vector_store.py bm25.py hybrid.py reranker.py graph.py multimodal.py
  agent/           react.py
  eval/            metrics.py run_eval.py
  security/        guardrails.py
  api/             routes.py schemas.py
  main.py config.py
scripts/           ingest.py query_cli.py evaluate.py
frontend/          Nuxt 3 chat + retrieval inspector + eval dashboard
```

## Skills used (skills.sh)

- `ui-ux-pro-max` (nextlevelbuilder) — dashboard design system, no-gradient editorial style
- `nuxt-ui` (nuxt/ui) — accessible Vue components
- `hybrid-search-implementation` (wshobson/agents) — BM25+dense RRF fusion
- `rag-implementation` (sickn33) — RAG lifecycle workflow
- `evaluate-rag` (hamelsmu) — retrieval vs generation eval discipline
- `qdrant-search-quality` + `postgres-hybrid-text-search` — vector infra ops

## Suggested documents (you have none yet — start here)

This repo ships with 12 synthetic enterprise docs covering every senior scenario:

1. `product_catalog.md` — Product X uses Component XK-7 (relational hop)
2. `supplier_registry.md` — XK-7 supplied by Nordwerk Precision (GraphRAG hop)
3. `safety_policy.md` — exact-match codes like `SAF-114` (BM25 wins, dense fails)
4. `q3_field_report.md` — table + narrative (multimodal: tables preserved as markdown + text)
5. `hr_leave_policy.md` — LEA-201 code + leave table (exact code + table)
6. `api_reference.md` — endpoint paths, API-009/FW-410 codes, 100/min rate limit
7. `support_runbook.md` — 5-step jitter procedure linking SAF-114, RMA-77, X-207
8. `supplier_sla.md` — 5%-per-week late penalty, extends the supplier entity cross-doc
9. `firmware_changelog.md` — Helios 4.2 fixed rev-B jitter (changelog synthesis)
10. `incident_postmortem.md` — X-207 root cause, links changelog + runbook
11. `returns_policy.md` — 30-day window vs 36-month warranty (near-miss trap)
12. `security_policy.md` — SEC-301 90-day rotation, mirrors api_reference (cross-doc)

Add your own: drop `.md/.txt/.pdf` into `data/01_raw/` and re-run `scripts/ingest.py`.
Good next corpora: support tickets, API docs, HR policies, financial filings — anything with
entities + relations + codes is ideal for showing hybrid + GraphRAG lift.

## API

- `GET /health` — deep status (index, embed model, Qdrant when configured)
- `GET /metrics` — Prometheus exposition (request counts, p50/p95 latency, eval gauges)
- `POST /ingest` — re-run pipeline `{strategy}` (incremental: unchanged docs reuse vectors)
- `POST /query` — `{query, top_k, use_agent, use_graph, session_id}` → answer + citations + trace + usage
- `GET /query/stream?...` — same answer as SSE (trace → tokens → done) for progressive UI render
- `POST /eval` — golden set + records to history; `GET /eval/history` — trend
- `POST /feedback` — `{session_id, query, vote: up|down, note}` thumbs loop
- `GET /graph/neighbors?entity=X` — knowledge-graph traversal demo

Set `API_KEY` env to require `X-API-Key` on all write/query routes. See `docs/OPERATIONS.md`.
Deploy: `docker build -t rag-showcase:1.0.0 .` + `k8s/deployment.yaml`. Reproducible deps in `requirements.lock`.

## Verification (proving the pipeline works)

Two layers, both visible in the dashboard's *Pipeline verification* panel:

1. **Local gate (always on)** — every answer carries the last eval result
   (`faithfulness`, gate PASS/FAIL from `data/eval/history.jsonl`).
2. **Langfuse traces (one env change)** — set `LANGFUSE_PUBLIC_KEY` /
   `LANGFUSE_SECRET_KEY` (free tier at cloud.langfuse.com), restart, and every
   answer gets per-stage spans (embed → hybrid → rerank → graph → generate) plus
   `faithfulness` / `rerank_top1` scores, linked from each chat bubble as
   *verified trace ↗*. No code changes; without keys it's a silent no-op.

Repeat questions return from cache (`instant · cached` badge, ~0 ms);
the 3 sample questions are pre-answered at boot (`PREWARM_SAMPLES=1` — disclosed
here, not hidden: caching is engineering, and the p50/p95 above were measured
over 16 distinct questions in a fresh process).

## Hardening log (external audit → fixes)

An independent static audit of this repo found real defects; all were fixed
rather than debated (each has a regression test or a verified behavior change):

- **Metrics**: NDCG used a non-standard IDCG (perfect retrieval scored 0.34) →
  textbook doc-deduped NDCG; faithfulness gained a polarity guard for negations.
- **Security**: `/query/stream` bypassed the injection check; unauthenticated
  calls burned rate-limit budget (middleware order); CORS wildcard + credentials;
  rate-limiter memory unbounded; PII regex missed domestic formats. All fixed;
  indirect-injection delimiters added to the prompt with scope honestly noted.
- **Retrieval**: parents were searchable in dense but invisible to BM25 (contract
  violation) → role-filtered; `XK-7` excluded from its own exact-code boost
  (`\d{2,}` → `\d+`); Qdrant failures now log + emit a gauge instead of silent fallback.
- **Agent**: retry re-embeds the rewrite (both branches see it); graph hits merge
  into candidates instead of trace decoration; entity linking replaces raw
  `query[:60]` (which always returned empty).
- **Deploy**: `/health` returns 503 when degraded; k8s manifest includes Qdrant;
  portable `make clean`; `curl` fallback chain in fetch; `scikit-learn` added to
  requirements; all paths anchored to repo root (works from any cwd).
- **Honest facades removed**: pgvector was advertised with zero application code —
  removed from compose/requirements/docs instead of documented around (it may
  return only with a driver module + parity test, like qdrant-local has).
