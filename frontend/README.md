# Frontend — Meridian RAG Console (Nuxt 3 + Nuxt UI)

AI-slop-free editorial dashboard: solid paper background, ink header, moss-green
primary, Fraunces display + Inter body. No gradients, no emoji icons (inline SVG),
44px touch targets, visible focus rings, `prefers-reduced-motion` respected.

## Run

```powershell
npm install
npm run dev   # http://localhost:3000 (API via same-origin /api proxy)
```

For split hosting (frontend and API on different machines):
`$env:NUXT_PUBLIC_API_BASE="http://api-host:8000"` before `npm run dev`.

API must be running: `uvicorn backend.app.main:app --port 8000` from repo root.

## What to demo (2-minute recruiter walkthrough)

1. Click sample: **"Which supplier provides the component used in Product X?"**
   → point at Retrieval trace: plan → hybrid (dense=10 sparse=6) → graph_lookup (3 triples) → rerank.
2. Click a **[supplier_registry.md]** citation chip → exact chunk shown in Source context.
3. Ask **"What does SAF-114 require?"** → exact-code win for BM25; mention dense-only would confuse SAF-118.
4. Hit **Run eval** → gate badge + P@5 / R@5 / MRR / NDCG / faithfulness table.
