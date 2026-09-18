## Summary
<!-- one line -->

## Evidence checklist
- [ ] `python -m pytest tests/ -q` green
- [ ] `python scripts/evaluate.py --fail-under 0.5 --compare-baseline` green
- [ ] README numbers match `data/eval/*.json` (if retrieval/eval touched)
- [ ] Regression test added for any bugfix
- [ ] No silent fallbacks added (or metric/log documents the degradation)
