# Contributing

## Ground rules
1. **Numbers before adjectives.** Any retrieval/generation change must report
   `python scripts/evaluate.py` before/after. No metric, no merge.
2. **Regression tests for fixes.** Every bugfix ships with a failing-first test
   (`tests/test_round<N>.py` convention documents which audit round found it).
3. **No silent fallbacks.** Degraded paths must log + expose a metric/gauge.
4. **Docs follow code.** README numbers must match `data/eval/*.json` artifacts.

## Workflow
```powershell
python scripts/ingest.py --strategy parent_child
python -m pytest tests/ -q
python scripts/evaluate.py --fail-under 0.5 --compare-baseline
```
- New documents go in `data/01_raw/` (enterprise) — never commit scale corpora
  (`scale_20news/`, `data/beir/` are git-ignored; fetch via scripts).
- New golden questions need `answer_keywords` + `relevant_docs`, and must pass.
- Re-baseline only with a commit message explaining *why* numbers moved.

## Agent skills (`.agents/` is git-ignored — restore with)
```powershell
npx skills experimental_install   # restores from skills-lock.json
```
Pinned skills: `ui-ux-pro-max`, `nuxt-ui`, `hybrid-search-implementation`,
`rag-implementation`, `evaluate-rag`, `qdrant-search-quality`,
`postgres-hybrid-text-search`, `brag`, `hyperframes-*` (see `skills-lock.json`).

## License
By contributing you agree your work is Apache-2.0 (see LICENSE).
