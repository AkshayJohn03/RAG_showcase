# Operations Guide — Senior RAG Showcase

## SLOs
| Signal | Target | Where to see it |
|---|---|---|
| Warm query latency p95 | < 800 ms | `GET /metrics` → `rag_request_ms_p95{route="/query"}` |
| Eval gate | PASS on every deploy | `POST /eval`, `GET /eval/history`, CI `eval.yml` |
| Faithfulness floor | ≥ 0.6 (drift alert at −0.1 vs baseline) | `scripts/evaluate.py --compare-baseline` |
| User feedback | ≥ 80% thumbs-up weekly | `GET` feedback stats via dashboard / `data/eval/feedback.jsonl` |

## Daily / weekly cadence
- **Daily**: glance at `/metrics` p95 + error counts; any 429 spike → raise `RATE_LIMIT_PER_MIN` or add gateway.
- **Weekly**: sample 20 `feedback.jsonl` downs → add the misses to `data/eval/golden_qa.json` → re-run eval → `--save-baseline` if legitimately improved.
- **On every doc change**: `python scripts/ingest.py` (incremental: unchanged docs reuse vectors), then `--compare-baseline`. changed strategy → full re-embed is automatic.

## Auth & rate limits
- Set `API_KEY` env on the server; clients send `X-API-Key`. Unset = open mode (dev only).
- `/health`, `/metrics`, `/docs` stay open by design (load-balancer + scraper need them). In locked-down VPCs, restrict `/metrics` at the gateway.
- Behind ingress/LB set `TRUST_PROXY=1` so rate limiting keys on
  `X-Forwarded-For` instead of the proxy IP (which would share one 30/min
  bucket across the whole company). Leave unset on direct exposure — XFF is
  client-spoofable.
- In-memory rate limiter is per-process: fine for 1 replica, use the cloud
  gateway limiter with 2+ replicas (see `k8s/deployment.yaml`).
- Multi-replica + `/ingest`: pods must share the index volume (RWX); a pod
  with a stale local copy serves stale answers until restart.

## Kubernetes notes
- `deployment.yaml` holds long-lived services (repeatable `kubectl apply`).
  `provision-job.yaml` is one-shot bootstrap — apply once per fresh cluster,
  never on every deploy (Job specs are immutable; re-applying fails).
- The provision Job waits for Qdrant readiness itself (`--wait 600`: TCP then
  `/readyz`), so StatefulSet slowness just delays it.

## Backups & DR
- Local mode: back up `data/04_vectors/` (vectors + bm25 + hashes + manifest + graph) alongside `data/01_raw/`. Restore = copy back + restart (mtime cache self-invalidates).
- Qdrant mode: snapshot via Qdrant API on a cron. RTO < 15 min:
  redeploy image (index is baked in) and re-ingest.

## Secrets
`.env` locally only. Prod: vault/SealedSecrets → env (`API_KEY`, `OPENAI_API_KEY`, `QDRANT_URL`). Never commit.

## Scaling notes
- Embeddings are CPU-heavy: keep `--workers 1` per pod (torch + fork don't mix), scale pods horizontally.
- Repeat questions are cached twice: embedding LRU (512) + clients should cache `GET /query/stream` by question hash at the CDN for public corpora.
- Next bottleneck after 100k chunks: move fully to server Qdrant
  (`VECTOR_BACKEND=qdrant`), enable HNSW quantization, shard by tenant.

## Incident quick-links
- Retrieval quality drop → `docs/runbooks/retrieval_drift.md`
- API 5xx after deploy → `kubectl rollout undo`, then check `/health` checks block (tells you index vs model vs qdrant).

## Security scope (what the regexes are and aren't)
- PII redaction and injection detection in `security/guardrails.py` are a fast
  deterministic first layer. They do not replace Microsoft Presidio (PII),
  Rebuff-style scoring, or an LLM judge (injection) — budget those before
  indexing customer or HR data. Retrieved context is wrapped in
  `<retrieved-context>` tags with a do-not-follow-instructions directive as the
  cheap structural defense that works with any model.
