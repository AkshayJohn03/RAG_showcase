# Changelog

All notable changes, newest first. Format: Keep a Changelog. Versions: SemVer.

## [1.0.0] — 2026-09-18
First public release. Apache-2.0.
- Retrieval: hybrid BM25 + dense (RRF), FlashRank/cross-encoder/heuristic rerank
  cascade, parent-child + sliding + semantic chunking, knowledge-graph + ReAct agent.
- Quality: 16-question golden set, CI eval gate with drift baseline, ablation +
  BEIR SciFact harness, Langfuse tracing, thumbs feedback loop.
- Ops: FastAPI + Nuxt dashboard, SSE streaming, auth + rate limits, Prometheus
  metrics, JSON logs, Dockerfile, k8s manifests, runbooks.
- Measured: p50 33ms warm queries; BEIR SciFact nDCG@10 0.659 (≈ ColBERT 0.671).
