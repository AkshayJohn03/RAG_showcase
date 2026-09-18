# Runbook: Retrieval-Quality Drift

**Symptom**: eval gate FAILs, faithfulness/recall drops, or user thumbs-down spikes —
but the API is up and `/health` is green.

## 1. Confirm (5 min)
```powershell
python scripts/evaluate.py --fail-under 0.6 --compare-baseline
GET /eval/history   # when did the trend break?
```
If only ONE question regressed → likely a doc edit. If ALL regressed → pipeline/infra change.

## 2. Triage questions (10 min)
- **Retrieval or generation?** Check per-question row: low `r@5`/`ndcg` = retrieval (chunking/index),
  low `faithfulness` with good retrieval = generation/prompt.
- **What changed?** `git log` on `data/01_raw/` + `backend/` since last green run in history.

## 3. Common causes & fixes
| Cause | Signal | Fix |
|---|---|---|
| Bad doc edit (deleted key paragraph) | 1 question drops | Restore paragraph, re-ingest, re-run eval |
| Strategy switch without re-baseline | all `ndcg` shift |compare against the right baseline; `--save-baseline` only when improvement is real |
| Embedding model version changed | dense branch degrades, BM25 fine | Re-ingest `--full` (vectors must match the model), re-baseline |
| Stale index (ingest not re-run) | new docs unanswerable | Run ingest; check manifest doc count |
| Junk feedback loop | thumbs-down spike, eval green | Sample feedback, extend golden set — eval was blind to it |

## 4. Roll back (if deploy-caused)
```powershell
kubectl rollout undo deployment/rag-showcase   # or: redeploy previous image tag
```
Index is baked into the image, so rollback restores vectors too.

## 5. Close out
- Record the new green run: `--save-baseline` with a commit message saying why.
- Add the missed question(s) to `golden_qa.json` so this drift is caught next time.
