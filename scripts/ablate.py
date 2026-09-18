"""Ablation study: dense-only vs BM25-only vs hybrid vs hybrid+rerank.

Produces the numbers behind the README claim that hybrid+rerank wins —
the table senior reviewers ask for. Saves data/eval/ablation.json.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.eval.run_eval import run_all

CONFIGS = [("dense", False), ("bm25", False), ("hybrid", False), ("hybrid", True)]

results = {}
for mode, rerank in CONFIGS:
    res = run_all(mode=mode, use_rerank=rerank)
    results[res["summary"]["config"]] = res["summary"]
    print(f"{res['summary']['config']:>15}: " + "  ".join(f"{k}={v}" for k, v in res["summary"].items() if k in ("p@5", "r@5", "mrr", "ndcg@5", "faith", "rel")))

(ROOT / "data" / "eval" / "ablation.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print("saved → data/eval/ablation.json")
